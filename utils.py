# SPDX-License-Identifier: GPL-3.0-only

import os
from typing import Optional
from logutils import get_logger

logger = get_logger(__name__)


def obfuscate_email(email: str) -> str:
    """Obfuscate email addresses.

    Args:
        email (str): The email address to obfuscate

    Returns:
        str: Obfuscated email (e.g., "us***@example.com")
    """
    if not email or "@" not in email:
        return email

    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local}***@{domain}"
    return f"{local[:2]}***@{domain}"


def get_env_var(key: str, default_value: Optional[str] = None, strict: bool = False):
    """Retrieves the value of a configuration from the environment variables."""
    try:
        value = os.environ[key] if strict else os.getenv(key) or default_value
        if strict and (value is None or value.strip() == ""):
            raise ValueError(f"Configuration '{key}' is missing or empty.")
        return value
    except KeyError as error:
        logger.error(
            "Configuration '%s' not found in environment variables: %s", key, error
        )
        raise
    except ValueError as error:
        logger.error("Configuration '%s' is empty: %s", key, error)
        raise
