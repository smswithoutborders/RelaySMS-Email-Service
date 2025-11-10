# SPDX-License-Identifier: GPL-3.0-only
"""SimpleLogin API client for email alias management.

The API endpoints referenced are from the official SimpleLogin API documentation:
https://github.com/simple-login/app/blob/master/docs/api.md
"""

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional, Tuple, Any, Set

import requests
from logutils import get_logger
from utils import get_env_var, obfuscate_email
from smtp_manager import SMTPManager

logger = get_logger(__name__)


class SimpleLoginClient:
    """Client for interacting with SimpleLogin API to manage email aliases."""

    def __init__(self, smtp_manager: SMTPManager = None):
        """Initialize SimpleLogin client with API configuration."""
        self.api_base_url = get_env_var(
            "SIMPLELOGIN_API_BASE_URL", "https://app.simplelogin.io/api"
        )
        self.api_key = get_env_var("SIMPLELOGIN_API_KEY", strict=False)
        self.smtp_manager = smtp_manager

    def _get_headers(self, include_content_type: bool = True) -> Dict[str, str]:
        """Generate API request headers with authentication."""
        headers = {"Authentication": self.api_key}
        if include_content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def _make_request(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        """Make HTTP request with error handling and JSON response parsing."""
        try:
            response = requests.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, "response") and e.response:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except (ValueError, AttributeError):
                    pass
            logger.error("Request failed: %s", error_msg)
            return None

    def get_alias_options(self, hostname: Optional[str] = None) -> Optional[Dict]:
        """Get alias creation options including signed suffixes for domain."""
        url = f"{self.api_base_url}/v5/alias/options"
        if hostname:
            url += f"?hostname={hostname}"
        response = self._make_request("GET", url, headers=self._get_headers(False))
        if response:
            logger.info("Retrieved alias options")
        return response

    def get_signed_suffix(self, domain: str) -> Optional[str]:
        """Get cryptographically signed suffix for domain from SimpleLogin API."""
        options = self.get_alias_options(hostname=domain)
        if not options or "suffixes" not in options:
            return None

        for suffix_data in options["suffixes"]:
            if suffix_data["suffix"] == f"@{domain}":
                return suffix_data["signed_suffix"]

        logger.error("No signed suffix found for domain: %s", domain)
        return None

    def list_aliases(self, query: Optional[str] = None) -> Optional[List[Dict]]:
        """Fetch user's aliases, optionally filtered by query string."""
        url = f"{self.api_base_url}/v2/aliases?enabled&page_id=0"
        data = {"query": query} if query else {}
        response = self._make_request(
            "POST", url, json=data, headers=self._get_headers()
        )
        return response["aliases"] if response else None

    def get_or_create_alias(
        self, prefix: str, domain: str, mailbox_email: str
    ) -> Optional[str]:
        """Get existing alias or create new one with prefix@domain format."""
        alias_email = f"{prefix}@{domain}"
        aliases = self.list_aliases(query=alias_email)
        if aliases:
            existing_alias = next(
                (a for a in aliases if a["email"] == alias_email), None
            )
            if existing_alias:
                logger.info("Using existing alias: %s", obfuscate_email(alias_email))
                return alias_email
        return self.create_alias(prefix, domain, mailbox_email)

    def create_alias(
        self, prefix: str, domain: str, mailbox_email: str
    ) -> Optional[str]:
        """Create new email alias using signed suffix and mailbox ID."""
        url = f"{self.api_base_url}/v3/alias/custom/new"

        mailbox = self.get_mailbox_by_email(mailbox_email)
        if not mailbox:
            logger.error("Mailbox not found: %s", obfuscate_email(mailbox_email))
            return None

        signed_suffix = self.get_signed_suffix(domain)
        if not signed_suffix:
            logger.error("No signed suffix available for domain: %s", domain)
            return None

        data = {
            "alias_prefix": prefix,
            "signed_suffix": signed_suffix,
            "mailbox_ids": [mailbox["id"]],
            "note": f"Created by RelaySMS Email Service on {datetime.now().isoformat()}",
            "name": "RelaySMS Team",
        }

        response = self._make_request(
            "POST", url, json=data, headers=self._get_headers()
        )

        if not response:
            return None

        logger.info(
            "Alias created successfully: %s", obfuscate_email(response.get("email"))
        )
        return response.get("email")

    def get_alias_by_email(self, alias_email: str) -> Optional[Dict]:
        """Find alias details by email address."""
        aliases = self.list_aliases(query=alias_email)
        if not aliases:
            return None
        alias = next((a for a in aliases if a["email"] == alias_email), None)
        if alias:
            logger.info("Found alias: %s", obfuscate_email(alias_email))
        return alias

    def add_contact_to_alias(
        self, alias_email: str, recipient_email: str
    ) -> Optional[Dict]:
        """Add recipient as contact to alias and return contact with reverse alias."""
        alias = self.get_alias_by_email(alias_email)
        if not alias:
            logger.error("Alias not found: %s", obfuscate_email(alias_email))
            return None

        alias_id = alias["id"]
        contact = self.create_contact(alias_id, recipient_email)
        if not contact:
            logger.error(
                "Failed to create contact for %s", obfuscate_email(recipient_email)
            )
            return None

        return contact

    def list_mailboxes(self) -> Optional[List[Dict]]:
        """Get all available mailboxes for the authenticated user."""
        url = f"{self.api_base_url}/mailboxes"
        response = self._make_request("GET", url, headers=self._get_headers(False))
        return response["mailboxes"] if response else None

    def get_mailbox_by_email(self, email: str) -> Optional[Dict]:
        """Find mailbox details by email address."""
        mailboxes = self.list_mailboxes()
        if not mailboxes:
            return None
        mailbox = next((mb for mb in mailboxes if mb.get("email") == email), None)
        if mailbox:
            logger.info("Found mailbox for: %s", obfuscate_email(email))
        return mailbox

    def create_contact(self, alias_id: int, email: str) -> Optional[Dict]:
        """Create or retrieve contact for alias, returns contact with reverse alias."""
        url = f"{self.api_base_url}/aliases/{alias_id}/contacts"
        data = {"contact": f"<{email}>"}
        response = self._make_request(
            "POST", url, json=data, headers=self._get_headers()
        )
        if response:
            action = "retrieved" if response["existed"] else "created"
            logger.info("Contact %s: %s", action, obfuscate_email(response["contact"]))
        return response

    def send_via_alias(
        self,
        mailbox: str,
        from_email: str,
        to_email: str,
        subject: str,
        body: Optional[str] = None,
        template: Optional[str] = None,
        substitutions: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """Send email via SimpleLogin alias.

        Args:
            mailbox: Mailbox email with SMTP credentials
            from_email: Email address for alias (prefix@domain)
            to_email: Recipient email address
            subject: Email subject
            body: Email body (if not using template)
            template: Template name (if not using body)
            substitutions: Variables for template/subject rendering
        """
        try:
            if substitutions is None:
                substitutions = {}

            if not self.api_key:
                return False, "SimpleLogin API key not configured"

            if not self.smtp_manager:
                return False, "SMTP manager not configured"

            if not self.smtp_manager.has_config(mailbox):
                return (
                    False,
                    f"No SMTP configuration found for mailbox {obfuscate_email(mailbox)}",
                )

            if "@" not in from_email:
                return False, "Invalid from_email format"

            alias_prefix, alias_domain = from_email.split("@", 1)

            rendered_subject = self.smtp_manager.render_text(subject, substitutions)

            if template:
                rendered_body = self.smtp_manager.load_and_render_template(
                    template, substitutions
                )
                if not rendered_body:
                    return False, f"Failed to load or render template: {template}"
            elif body:
                rendered_body = self.smtp_manager.render_text(body, substitutions)
            else:
                return False, "Either 'template' or 'body' must be provided"

            alias_email = self.get_or_create_alias(alias_prefix, alias_domain, mailbox)
            if not alias_email:
                return False, "Failed to create or get alias"

            contact = self.add_contact_to_alias(alias_email, to_email)
            if not contact:
                return False, "Failed to add recipient as contact"

            reverse_alias = contact.get("reverse_alias")
            if not reverse_alias:
                return False, "No reverse alias found for contact"

            project_name = substitutions.get("project_name", "")
            sender_name = f"{project_name} Team" if project_name else None

            self.smtp_manager.send_email(
                mailbox,
                reverse_alias,
                rendered_subject,
                rendered_body,
                sender_name,
            )

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                "Email sent via SimpleLogin from %s (mailbox: %s) to %s via %s at %s",
                obfuscate_email(alias_email),
                obfuscate_email(mailbox),
                obfuscate_email(to_email),
                obfuscate_email(reverse_alias),
                timestamp,
            )
            return True, f"Email sent successfully at {timestamp}"

        except (smtplib.SMTPException, ConnectionError) as e:
            logger.exception("Failed to send email: %s", e)
            return False, "Failed to send email. Please try again later."
