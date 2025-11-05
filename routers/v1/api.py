# SPDX-License-Identifier: GPL-3.0-only

from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends
from auth import authenticate_api_key
from logutils import get_logger
from schemas.v1.models import SendEmailRequest, SendEmailResponse
from simplelogin import SimpleLoginClient
from utils import obfuscate_email

logger = get_logger(__name__)

router = APIRouter()


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
    client = SimpleLoginClient()

    alias_config = {
        "prefix": request.alias_prefix,
        "domain": request.alias_domain,
        "mailbox": request.sender_mailbox,
    }

    email_config = {
        "recipient": request.to_email,
        "subject": request.subject,
    }

    if request.template:
        email_config["template"] = request.template
        substitutions = request.substitutions or {}

        is_valid, missing_vars = client.validate_template_variables(
            request.template, substitutions
        )
        if not is_valid:
            error_msg = (
                f"Missing required template variables: {', '.join(missing_vars)}"
            )
            logger.error(
                "Template validation failed for %s: %s", request.template, error_msg
            )
            return SendEmailResponse(success=False, message=error_msg)
    else:
        email_config["body"] = request.body
        substitutions = request.substitutions or {}

    success, message = client.send_email(
        alias_config=alias_config,
        email_config=email_config,
        substitutions=substitutions,
    )

    if not success:
        logger.error(
            "Failed to send email to %s: %s", obfuscate_email(request.to_email), message
        )
        return SendEmailResponse(success=False, message=message)

    logger.info("Email sent successfully to %s", obfuscate_email(request.to_email))
    return SendEmailResponse(success=True, message=message)
