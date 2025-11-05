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
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, meta
from logutils import get_logger
from utils import get_env_var, obfuscate_email

logger = get_logger(__name__)


class SimpleLoginClient:
    """Client for interacting with SimpleLogin API to manage email aliases."""

    def __init__(self):
        """Initialize SimpleLogin client with API and SMTP configuration."""
        self.api_base_url = get_env_var(
            "SIMPLELOGIN_API_BASE_URL", "https://app.simplelogin.io/api"
        )
        self.api_key = get_env_var("SIMPLELOGIN_API_KEY", strict=True)
        self.smtp_server = get_env_var("SMTP_SERVER", strict=True)
        self.smtp_port = int(get_env_var("SMTP_PORT", 587))
        self.smtp_username = get_env_var("SMTP_USERNAME", strict=True)
        self.smtp_password = get_env_var("SMTP_PASSWORD", strict=True)
        self.smtp_enable_tls = get_env_var("SMTP_ENABLE_TLS", True)
        self.template_dir = get_env_var("EMAIL_TEMPLATE_DIR", "email_templates")

        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=True,
        )

    def _get_template_variables(self, template_name: str) -> Tuple[bool, Set[str]]:
        """Extract all variable names used in a Jinja2 template."""
        try:
            template_path = f"{self.template_dir}/{template_name}.html"
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()

            ast = self.jinja_env.parse(template_content)
            variables = meta.find_undeclared_variables(ast)
            logger.debug("Found variables in template %s: %s", template_name, variables)
            return True, variables
        except FileNotFoundError:
            logger.error("Template not found: %s.html", template_name)
            return False, set()
        except Exception as e:
            logger.error(
                "Error extracting variables from template %s: %s", template_name, e
            )
            return False, set()

    def validate_template_variables(
        self, template_name: str, substitutions: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate that all required template variables are provided in substitutions."""
        extraction_success, required_variables = self._get_template_variables(
            template_name
        )

        if not extraction_success:
            error_msg = f"Failed to extract variables from template: {template_name}"
            logger.error(error_msg)
            return False, [error_msg]

        provided_variables = set(substitutions.keys())
        missing_variables = list(required_variables - provided_variables)

        is_valid = len(missing_variables) == 0

        if not is_valid:
            logger.warning(
                "Template %s missing required variables: %s",
                template_name,
                missing_variables,
            )
        else:
            logger.info(
                "All required variables provided for template %s", template_name
            )

        return is_valid, missing_variables

    def _load_and_render_template(
        self, template_name: str, substitutions: Dict[str, Any]
    ) -> Optional[str]:
        """Load and render HTML email template with provided substitutions."""
        try:
            template = self.jinja_env.get_template(f"{template_name}.html")
            rendered_content = template.render(substitutions)
            logger.info("Template %s loaded and rendered successfully", template_name)
            return rendered_content
        except TemplateNotFound:
            logger.error("Template not found: %s.html", template_name)
            return None
        except OSError as e:
            logger.error("Error loading/rendering template %s: %s", template_name, e)
            return None

    def _render_subject(
        self, subject_template: str, substitutions: Dict[str, Any]
    ) -> str:
        """Render subject template with provided substitutions."""
        try:
            template = self.jinja_env.from_string(subject_template)
            return template.render(substitutions)
        except (TemplateNotFound, OSError) as e:
            logger.warning("Error rendering subject template: %s", e)
            return subject_template

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
            logger.info("Contact %s: %s", action, response["contact"])
        return response

    def send_via_smtp(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        sender_name: str = None,
    ) -> None:
        """Send email via configured SMTP server with HTML support."""
        msg = MIMEMultipart("alternative")

        if sender_name:
            msg["From"] = f"{sender_name} <{from_email}>"
        else:
            msg["From"] = from_email

        msg["To"] = to_email
        msg["Subject"] = subject

        is_html = body.strip().startswith("<") and ">" in body
        mime_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, mime_type))

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            if self.smtp_enable_tls:
                server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(from_email, [to_email], msg.as_string())

    def send_email(
        self,
        alias_config: Dict[str, str],
        email_config: Dict[str, str],
        substitutions: Dict[str, Any] = None,
    ) -> Tuple[bool, str]:
        """Send email using prefix@domain alias with template support.

        Args:
            alias_config: Dict with 'prefix', 'domain', 'mailbox' keys
            email_config: Dict with 'recipient', 'subject', 'template' or 'body' keys
            substitutions: Dict with key-value pairs for template substitutions
        """
        try:
            if substitutions is None:
                substitutions = {}

            alias_prefix = alias_config["prefix"]
            alias_domain = alias_config["domain"]
            sender_mailbox = alias_config["mailbox"]
            recipient_email = email_config["recipient"]
            subject = email_config["subject"]
            template_name = email_config.get("template")
            body = email_config.get("body")

            rendered_subject = self._render_subject(subject, substitutions)

            if template_name:
                rendered_body = self._load_and_render_template(
                    template_name, substitutions
                )
                if not rendered_body:
                    return False, f"Failed to load or render template: {template_name}"
            elif body:
                rendered_body = self._render_subject(body, substitutions)
            else:
                return (
                    False,
                    "Either 'template' or 'body' must be provided in email_config",
                )

            alias_email = self.get_or_create_alias(
                alias_prefix, alias_domain, sender_mailbox
            )
            if not alias_email:
                return False, "Failed to create or get alias"

            contact = self.add_contact_to_alias(alias_email, recipient_email)
            if not contact:
                return False, "Failed to add recipient as contact"

            reverse_alias = contact.get("reverse_alias")
            if not reverse_alias:
                return False, "No reverse alias found for contact"

            project_name = substitutions.get("project_name", "")
            sender_name = f"{project_name} Team" if project_name else None

            self.send_via_smtp(
                self.smtp_username,
                reverse_alias,
                rendered_subject,
                rendered_body,
                sender_name,
            )

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                "Email sent successfully from %s to %s via %s at %s",
                obfuscate_email(alias_email),
                obfuscate_email(recipient_email),
                obfuscate_email(reverse_alias),
                timestamp,
            )
            return True, f"Email sent successfully at {timestamp}"

        except (smtplib.SMTPException, ConnectionError) as e:
            logger.exception("Failed to send email: %s", e)
            return False, "Failed to send email. Please try again later."
