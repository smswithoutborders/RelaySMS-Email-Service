# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel


class SendEmailRequest(BaseModel):
    """Request model for sending emails."""

    to_email: str
    subject: str
    alias_prefix: str
    alias_domain: str
    sender_mailbox: str
    body: str = None
    from_name: str = None
    template: str = None
    substitutions: dict = None


class SendEmailResponse(BaseModel):
    """Response model for email sending."""

    success: bool
    message: str
