# SPDX-License-Identifier: GPL-3.0-only

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends
from auth import authenticate_api_key
from logutils import get_logger
from schemas.v1.models import SendEmailRequest, SendEmailResponse
from simplelogin import SimpleLoginClient
from smtp_manager import SMTPManager
from utils import obfuscate_email

logger = get_logger(__name__)

router = APIRouter()

smtp_manager = SMTPManager()


def verify_api_key(authorization: Optional[str] = Header(None)):
    """Dependency to verify API key from Authorization header."""
    if not authorization:
        logger.warning("Missing Authorization header")
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    api_key = authorization
    if authorization.startswith("Bearer "):
        api_key = authorization[7:]

    if not authenticate_api_key(api_key):
        logger.warning("Invalid API key provided")
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key


@router.post("/send", response_model=SendEmailResponse)
def send_email(request: SendEmailRequest, _: str = Depends(verify_api_key)):
    """Send a single email."""

    substitutions = request.substitutions or {}

    if request.alias:
        if not request.from_email:
            error_msg = "'from_email' is required when using 'alias'"
            logger.error(error_msg)
            return SendEmailResponse(success=False, message=error_msg)

        logger.info(
            "Using SimpleLogin with mailbox: %s", obfuscate_email(request.alias.mailbox)
        )

        client = SimpleLoginClient(smtp_manager=smtp_manager)

        if request.template:
            is_valid, error_msg = smtp_manager.validate_template_variables(
                request.template, substitutions
            )
            if not is_valid:
                logger.error(
                    "Template validation failed for %s: %s", request.template, error_msg
                )
                return SendEmailResponse(success=False, message=error_msg)

        success, message = client.send_via_alias(
            mailbox=request.alias.mailbox,
            from_email=request.from_email,
            to_email=request.to_email,
            subject=request.subject,
            body=request.body,
            template=request.template,
            substitutions=substitutions,
        )

    elif request.from_email:
        logger.info(
            "Using plain SMTP with from_email: %s", obfuscate_email(request.from_email)
        )

        if not smtp_manager.has_config(request.from_email):
            error_msg = (
                f"No SMTP configuration found for {obfuscate_email(request.from_email)}"
            )
            logger.error(error_msg)
            return SendEmailResponse(success=False, message=error_msg)

        subject = smtp_manager.render_text(request.subject, substitutions)

        if request.template:
            is_valid, error_msg = smtp_manager.validate_template_variables(
                request.template, substitutions
            )
            if not is_valid:
                logger.error(
                    "Template validation failed for %s: %s", request.template, error_msg
                )
                return SendEmailResponse(success=False, message=error_msg)

            body = smtp_manager.load_and_render_template(
                request.template, substitutions
            )
            if not body:
                error_msg = f"Failed to load or render template: {request.template}"
                logger.error(error_msg)
                return SendEmailResponse(success=False, message=error_msg)
        elif request.body:
            body = smtp_manager.render_text(request.body, substitutions)
        else:
            error_msg = "Either 'template' or 'body' must be provided"
            logger.error(error_msg)
            return SendEmailResponse(success=False, message=error_msg)

        project_name = substitutions.get("project_name", "")
        sender_name = f"{project_name} Team" if project_name else request.from_name

        try:
            smtp_manager.send_email(
                from_email=request.from_email,
                to_email=request.to_email,
                subject=subject,
                body=body,
                sender_name=sender_name,
            )
            success = True
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"Email sent successfully at {timestamp}"
            logger.info(
                "Email sent via plain SMTP from %s to %s at %s",
                obfuscate_email(request.from_email),
                obfuscate_email(request.to_email),
                timestamp,
            )
        except Exception as e:
            logger.exception("Failed to send email: %s", e)
            success = False
            message = "Failed to send email. Please try again later."

    else:
        error_msg = "Either 'alias' or 'from_email' must be provided"
        logger.error(error_msg)
        return SendEmailResponse(success=False, message=error_msg)

    if not success:
        logger.error(
            "Failed to send email to %s: %s", obfuscate_email(request.to_email), message
        )
        return SendEmailResponse(success=False, message=message)

    logger.info("Email sent successfully to %s", obfuscate_email(request.to_email))
    return SendEmailResponse(success=True, message=message)
