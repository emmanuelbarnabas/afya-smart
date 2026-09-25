"""Notification service — SMS via Africa's Talking (ikiwa imepangwa), la sivyo log.

USSD inatosha kwa mwingiliano wa papo hapo; SMS hutumwa kwa uthibitisho wa
booking na miongozo ya self-care. Bila API credentials, tunalog tu (dev).
"""
from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("afyasmart.notify")


def send_sms(to: str, message: str) -> bool:
    """Tuma SMS kwa namba moja. Return True kama imetumwa (au imesimuliwa dev)."""
    if not settings.at_api_key or settings.at_username == "sandbox":
        logger.info("[dev-sms] to=%s message=%r", to, message)
        return True

    try:
        import africastalking

        africastalking.initialize(settings.at_username, settings.at_api_key)
        sms = africastalking.SMS
        response = sms.send(message, [to], sender_id=settings.at_phone_number or None)
        logger.info("SMS sent to %s: %s", to, response)
        return True
    except Exception:
        logger.exception("Imeshindikana kutuma SMS kwa %s", to)
        return False


def notify_booking_confirmed(to: str, when_label: str, facility_name: str) -> bool:
    return send_sms(
        to,
        f"Afya Smart: Miadi yako imethibitishwa {when_label} katika {facility_name}. "
        "Fika dakika 10 kabla. Kubadilisha: piga *384*123#.",
    )


def notify_self_care_guidance(to: str, guidance: str) -> bool:
    return send_sms(to, f"Afya Smart: {guidance}")
