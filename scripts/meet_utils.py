"""
meet_utils.py — Google Meet PSTN dial-in utilities.

Provides:
  - extract_meet_code(text)    : detect a Meet URL in any text string
  - fetch_meet_dialin(code)    : fetch the Meet page and extract phone + PIN
"""

import re
import logging

import httpx

logger = logging.getLogger(__name__)

# Pattern: meet.google.com/abc-defg-hij  (3-4-3 lowercase letters)
MEET_URL_PATTERN = re.compile(
    r"https?://meet\.google\.com/([a-z]{3}-[a-z]{4}-[a-z]{3})"
)


def extract_meet_code(text: str) -> str | None:
    """
    Return the meeting code (e.g. 'abc-defg-hij') if *text* contains a
    Google Meet URL, otherwise return None.
    """
    m = MEET_URL_PATTERN.search(text)
    return m.group(1) if m else None


async def fetch_meet_dialin(meet_code: str) -> dict | None:
    """
    Fetch the Google Meet page for *meet_code* and extract the PSTN
    dial-in phone number and PIN.

    Returns a dict ``{"phone": "+16176754444", "pin": "123456789"}``
    or ``None`` if the information cannot be found (redirect, no PSTN
    info, network error, etc.).
    """
    url = f"https://meet.google.com/{meet_code}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NiaAgent/1.0)"}

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=10) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code in (301, 302, 303, 307, 308):
            logger.warning(f"Meet {meet_code}: got redirect {resp.status_code}")
            return None

        html = resp.text

        # Phone number: international format like "+1 617-675-4444"
        phone_match = re.search(r"(\+\d[\d\s\-\(\)]{7,15}\d)", html)
        # PIN: "PIN: 123 456 789#" or similar
        pin_match = re.search(
            r"PIN[:\s]+(\d[\d\s]{5,12}\d)\s*#?", html, re.IGNORECASE
        )

        if not phone_match or not pin_match:
            logger.warning(
                f"Could not find dial-in info for Meet {meet_code} "
                f"(phone={'found' if phone_match else 'missing'}, "
                f"pin={'found' if pin_match else 'missing'})"
            )
            return None

        # Strip formatting characters
        phone = re.sub(r"[\s\-\(\)]", "", phone_match.group(1))
        pin = re.sub(r"[\s#]", "", pin_match.group(1))

        logger.info(f"Meet {meet_code}: dial-in extracted (phone={phone[:6]}***)")
        return {"phone": phone, "pin": pin}

    except Exception as e:
        logger.warning(f"fetch_meet_dialin error for {meet_code}: {e}")
        return None
