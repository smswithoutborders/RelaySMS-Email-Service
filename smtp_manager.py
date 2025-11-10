# SPDX-License-Identifier: GPL-3.0-only

import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional, Set, Tuple, Any
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, meta
from logutils import get_logger
from utils import get_env_var, obfuscate_email

logger = get_logger(__name__)


class SMTPConfig:
    """Configuration for an SMTP account."""

    def __init__(
        self,
        from_email: str,
        host: str,
        port: int,
        username: str,
        password: str,
        enable_tls: bool = True,
    ):
        self.from_email = from_email
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_tls = enable_tls


class SMTPManager:
    """Manager for multiple SMTP configurations and email sending."""

    def __init__(self, creds_file: str | None = None):
        """Initialize SMTP manager with credentials file."""
        self.creds_file = creds_file or get_env_var(
            "SMTP_CREDS_FILE", "smtp_creds.json"
        )
        self.smtp_accounts: Dict[str, SMTPConfig] = {}
        self.template_dir = get_env_var("EMAIL_TEMPLATE_DIR", "email_templates")
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=True,
        )
        self._load_credentials()

    def _load_credentials(self):
        """Load SMTP credentials from JSON file."""
        try:
            with open(self.creds_file, "r") as f:
                data = json.load(f)
                smtp_accounts = data.get("smtp_accounts", [])

                for account in smtp_accounts:
                    from_email = account.get("from_email")
                    if not from_email:
                        logger.warning("SMTP account missing 'from_email', skipping")
                        continue

                    config = SMTPConfig(
                        from_email=from_email,
                        host=account.get("host"),
                        port=account.get("port", 587),
                        username=account.get("username"),
                        password=account.get("password"),
                        enable_tls=account.get("enable_tls", True),
                    )
                    self.smtp_accounts[from_email] = config
                    logger.info(
                        "Loaded SMTP config for: %s", obfuscate_email(from_email)
                    )

                if not self.smtp_accounts:
                    logger.warning("No SMTP accounts loaded from %s", self.creds_file)
        except FileNotFoundError:
            logger.error("SMTP credentials file not found: %s", self.creds_file)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in SMTP credentials file: %s", e)
        except Exception as e:
            logger.error("Error loading SMTP credentials: %s", e)

    def get_smtp_config(self, from_email: str) -> Optional[SMTPConfig]:
        """Get SMTP configuration for a specific email address."""
        config = self.smtp_accounts.get(from_email)
        if not config:
            logger.error(
                "No SMTP configuration found for: %s", obfuscate_email(from_email)
            )
        return config

    def has_config(self, from_email: str) -> bool:
        """Check if SMTP configuration exists for email address."""
        return from_email in self.smtp_accounts

    def render_text(self, text: str, substitutions: Dict[str, Any]) -> str:
        """Render text with Jinja2 substitutions."""
        try:
            template = self.jinja_env.from_string(text)
            return template.render(substitutions)
        except Exception as e:
            logger.warning("Error rendering text: %s", e)
            return text

    def get_template_variables(self, template_name: str) -> Tuple[bool, Set[str]]:
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
            return False, set([f"Template {template_name} not found"])
        except Exception as e:
            logger.error(
                "Error extracting variables from template %s: %s", template_name, e
            )
            return False, set(
                [f"Failed to extract variables from template {template_name}"]
            )

    def validate_template_variables(
        self, template_name: str, substitutions: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Validate that all required template variables are provided."""
        extraction_success, required_variables = self.get_template_variables(
            template_name
        )

        if not extraction_success:
            error_msg = required_variables.pop()
            logger.error(error_msg)
            return False, error_msg

        provided_variables = set(substitutions.keys())
        missing_variables = list(required_variables - provided_variables)
        error_msg = ""
        is_valid = len(missing_variables) == 0

        if not is_valid:
            logger.warning(
                "Template %s missing required variables: %s",
                template_name,
                missing_variables,
            )
            error_msg = (
                f"Missing required template variables: {', '.join(missing_variables)}"
            )
        else:
            logger.info(
                "All required variables provided for template %s", template_name
            )

        return is_valid, error_msg

    def load_and_render_template(
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
        except Exception as e:
            logger.error("Error loading/rendering template %s: %s", template_name, e)
            return None

    def send_email(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        sender_name: Optional[str] = None,
    ) -> None:
        """Send email via SMTP using configuration for from_email."""
        config = self.get_smtp_config(from_email)
        if not config:
            raise ValueError(
                f"No SMTP configuration found for {obfuscate_email(from_email)}"
            )

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

        with smtplib.SMTP(config.host, config.port) as server:
            if config.enable_tls:
                server.starttls()
            server.login(config.username, config.password)
            server.sendmail(from_email, [to_email], msg.as_string())

        logger.info(
            "Email sent via SMTP from %s to %s",
            obfuscate_email(from_email),
            obfuscate_email(to_email),
        )
