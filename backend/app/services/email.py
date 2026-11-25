"""Email service for password reset codes.

Free mailer compatible:
- Development (no SMTP configured): logs reset code to console + reset_codes.log
- Production: configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS in .env
  Works with any free SMTP service (Ethereal.email, Mailtrap, SendGrid, Mailgun, etc.)
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

RESET_CODES_LOG = os.path.join(os.getcwd(), "reset_codes.log")


def _generate_code() -> str:
    """Generate a 6-digit numeric reset code."""
    import random

    return f"{random.randint(100000, 999999)}"


async def send_reset_code(email: str, code: str, expires_in_minutes: int | None = None) -> bool:
    """Send a password reset code to the given email address.

    Returns True if the code was sent (or logged in dev mode).
    """
    expires_in = expires_in_minutes or settings.EMAIL_RESET_CODE_EXPIRE_MINUTES

    # Dev mode: no SMTP configured -> log to console + file
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.info(
            "=" * 60
        )
        logger.info("PASSWORD RESET CODE (dev mode - no SMTP configured)")
        logger.info("To: %s", email)
        logger.info("Code: %s", code)
        logger.info("Expires in: %d minutes", expires_in)
        logger.info("=" * 60)

        # Also write to a file so it's easy to find
        try:
            with open(RESET_CODES_LOG, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.now(timezone.utc).isoformat()} | "
                    f"to={email} | code={code} | expires_in={expires_in}min\n"
                )
        except OSError:
            logger.warning("Could not write to reset_codes.log")

        return True

    # Production: send via SMTP
    try:
        import aiosmtplib

        message = EmailMessage()
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = email
        message["Subject"] = "Your AI Gen Post password reset code"
        message.set_content(
            f"Your password reset code is: {code}\n"
            f"This code expires in {expires_in} minutes.\n"
            f"If you didn't request this, please ignore this email."
        )

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASS,
            start_tls=settings.SMTP_PORT == 587,
        )
        logger.info("Reset code sent via SMTP to %s", email)
        return True
    except ImportError:
        logger.exception("aiosmtplib not installed; falling back to dev logging")
        # Fall back to dev logging
        with open(RESET_CODES_LOG, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now(timezone.utc).isoformat()} | "
                f"to={email} | code={code} | expires_in={expires_in}min\n"
            )
        return True
    except Exception:
        logger.exception("Failed to send reset email via SMTP to %s", email)
        return False
