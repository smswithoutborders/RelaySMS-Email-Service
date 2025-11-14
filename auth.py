# SPDX-License-Identifier: GPL-3.0-only

import hmac

from logutils import get_logger
from utils import get_env_var

logger = get_logger(__name__)

API_KEY = get_env_var("API_KEY", strict=True)


def authenticate_api_key(api_key: str) -> bool:
    """
    Authenticate API key for email sending endpoint.

    Args:
        api_key (str): The API key to authenticate.

    Return:
        bool: True if valid, False otherwise.
    """
    return hmac.compare_digest(api_key, API_KEY)
