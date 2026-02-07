import logging
import os
import re
import uuid
from datetime import datetime, timezone

from playwright.async_api import Page, ElementHandle

from app.models.profile import UserProfile

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "screenshots")

# Mapping of field name patterns to profile fields
FIELD_PATTERNS = {
    # Name fields
    r"first.?name|given.?name|fname": "first_name",
    r"last.?name|surname|family.?name|lname": "last_name",
    r"full.?name|your.?name|^name$": "full_name",
    # Contact
    r"e.?mail|email.?address": "email",
    r"phone|mobile|telephone|cell": "phone",
    r"linkedin": "linkedin_url",
    r"website|portfolio|personal.?site|url": "website_url",
    # EEO fields
    r"citizen|authorization|authorized|legally": "us_citizen",
    r"sponsor|visa": "sponsorship_needed",
    r"veteran|military": "veteran_status",
    r"disab": "disability_status",
    r"gender|sex": "gender",
    r"ethnic|race|demographic": "ethnicity",
}

# Confidence threshold below which we flag for human review
CONFIDENCE_THRESHOLD = 0.7


def _get_profile_value(profile: UserProfile, field_key: str) -> tuple[str, float]:
    """Get the value for a field key from the user profile, with confidence score."""
    if field_key == "full_name":
        name = f"{profile.first_name} {profile.last_name}".strip()
        return (name, 0.95) if name else ("", 0.0)

    if field_key == "us_citizen":
        if profile.us_citizen is not None:
            return ("Yes" if profile.us_citizen else "No", 0.9)
        return ("", 0.0)

    if field_key == "sponsorship_needed":
        if profile.sponsorship_needed is not None:
            return ("Yes" if profile.sponsorship_needed else "No", 0.9)
        return ("", 0.0)

    val = getattr(profile, field_key, "")
    if val:
        return (str(val), 0.9)
    return ("", 0.0)


def detect_field_type(
    element_tag: str,
    element_type: str,
    label_text: str,
    name_attr: str,
    placeholder: str,
    aria_label: str,
) -> tuple[str, float]:
    """Detect what profile field maps to this form element.

    Returns (field_key, confidence).
    """
    # Combine all text signals
    signal = f"{label_text} {name_attr} {placeholder} {aria_label}".lower().strip()

    if not signal.strip():
        return ("unknown", 0.0)

    for pattern, field_key in FIELD_PATTERNS.items():
        if re.search(pattern, signal, re.IGNORECASE):
            return (field_key, 0.85)

    # Check for resume/file upload
    if element_type == "file" or "resume" in signal or "cv " in signal:
        return ("resume", 0.9)

    # Check for cover letter
    if "cover" in signal and "letter" in signal:
        return ("cover_letter", 0.8)

    return ("unknown", 0.3)


async def analyze_form_fields(page: Page, profile: UserProfile) -> list[dict]:
    """Analyze all form fields on the current page and attempt to map them to profile data.

    Returns a list of field descriptors with fill status.
    """
    fields = []

    # Gather all input, select, and textarea elements
    elements = await page.query_selector_all("input, select, textarea")

    for elem in elements:
        try:
            tag = await elem.evaluate("el => el.tagName.toLowerCase()")
            input_type = await elem.get_attribute("type") or ""
            name = await elem.get_attribute("name") or ""
            placeholder = await elem.get_attribute("placeholder") or ""
            aria_label = await elem.get_attribute("aria-label") or ""
            elem_id = await elem.get_attribute("id") or ""

            # Skip hidden/submit fields
            if input_type in ("hidden", "submit", "button", "image"):
                continue

            # Try to find associated label
            label_text = ""
            if elem_id:
                label = await page.query_selector(f'label[for="{elem_id}"]')
                if label:
                    label_text = (await label.inner_text()).strip()

            if not label_text:
                # Try parent label
                parent_label = await elem.evaluate(
                    "el => { const l = el.closest('label'); return l ? l.textContent.trim() : ''; }"
                )
                label_text = parent_label

            # Determine field type
            field_key, confidence = detect_field_type(
                tag, input_type, label_text, name, placeholder, aria_label,
            )

            # Determine field UI type
            if tag == "select":
                field_type = "select"
                options_elems = await elem.query_selector_all("option")
                options = []
                for opt in options_elems:
                    opt_text = (await opt.inner_text()).strip()
                    if opt_text:
                        options.append(opt_text)
            elif tag == "textarea":
                field_type = "textarea"
                options = []
            elif input_type == "checkbox":
                field_type = "checkbox"
                options = []
            elif input_type == "radio":
                field_type = "radio"
                options = []
            elif input_type == "file":
                field_type = "file"
                options = []
            else:
                field_type = "text"
                options = []

            # Get value from profile
            value = ""
            if field_key != "unknown" and field_key != "resume" and field_key != "cover_letter":
                value, val_confidence = _get_profile_value(profile, field_key)
                confidence = min(confidence, val_confidence) if value else 0.0

            status = "filled" if value and confidence >= CONFIDENCE_THRESHOLD else "needs_input"

            field_desc = {
                "field_name": name or elem_id or f"unnamed_{tag}",
                "field_type": field_type,
                "label": label_text or placeholder or name or aria_label,
                "value": value,
                "confidence": round(confidence, 2),
                "status": status,
                "options": options,
                "_selector": f"[name='{name}']" if name else f"#{elem_id}" if elem_id else "",
            }
            fields.append(field_desc)

        except Exception:
            logger.exception("Error analyzing form element")
            continue

    return fields


async def fill_form_fields(page: Page, fields: list[dict]) -> list[dict]:
    """Fill form fields that have been approved (status='filled' or user-provided values).

    Returns updated field list with fill results.
    """
    filled_fields = []

    for field in fields:
        if not field.get("value") or not field.get("_selector"):
            filled_fields.append(field)
            continue

        selector = field["_selector"]
        value = field["value"]
        field_type = field["field_type"]

        try:
            elem = await page.query_selector(selector)
            if not elem:
                field["status"] = "needs_input"
                field["value"] = ""
                filled_fields.append(field)
                continue

            if field_type == "select":
                await elem.select_option(label=value)
                field["status"] = "filled"
            elif field_type == "checkbox":
                is_checked = await elem.is_checked()
                should_check = value.lower() in ("yes", "true", "1")
                if is_checked != should_check:
                    await elem.click()
                field["status"] = "filled"
            elif field_type == "file":
                if os.path.exists(value):
                    await elem.set_input_files(value)
                    field["status"] = "filled"
                else:
                    field["status"] = "needs_input"
            elif field_type in ("text", "textarea"):
                await elem.click()
                await elem.fill("")
                await elem.fill(value)
                field["status"] = "filled"
            else:
                await elem.fill(value)
                field["status"] = "filled"

        except Exception as e:
            logger.warning("Failed to fill field %s: %s", selector, e)
            field["status"] = "needs_input"

        filled_fields.append(field)

    return filled_fields


async def take_screenshot(page: Page, label: str = "") -> str:
    """Take a screenshot and save it. Returns the file path."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{ts}_{label}_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    await page.screenshot(path=filepath, full_page=True)
    return filepath


def has_captcha(page_content: str) -> bool:
    """Simple heuristic to detect CAPTCHA presence on the page."""
    captcha_indicators = [
        "captcha",
        "recaptcha",
        "hcaptcha",
        "g-recaptcha",
        "h-captcha",
        "challenge-form",
        "cf-turnstile",
        "arkose",
    ]
    content_lower = page_content.lower()
    return any(indicator in content_lower for indicator in captcha_indicators)


def needs_human_review(fields: list[dict]) -> bool:
    """Check if any fields need human review."""
    return any(f.get("status") == "needs_input" for f in fields)
