# SPDX-License-Identifier: GPL-3.0-only

from typing import Optional
from pydantic import BaseModel


class AliasConfig(BaseModel):
    """Configuration for SimpleLogin alias."""

    mailbox: str


class SendEmailRequest(BaseModel):
    """Request model for sending emails."""

    from_email: str
    to_email: str
    subject: str
    body: Optional[str] = None
    from_name: Optional[str] = None
    template: Optional[str] = None
    substitutions: Optional[dict] = None
    alias: Optional[AliasConfig] = None


class SendEmailResponse(BaseModel):
    """Response model for email sending."""

    success: bool
    message: str
