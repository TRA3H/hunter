import uuid

import pytest

from app.models.profile import UserProfile
from app.services.autofill import (
    CONFIDENCE_THRESHOLD,
    detect_field_type,
    has_captcha,
    needs_human_review,
    _get_profile_value,
)


@pytest.fixture
def profile():
    return UserProfile(
        id=uuid.uuid4(),
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone="555-123-4567",
        linkedin_url="https://linkedin.com/in/janedoe",
        website_url="https://janedoe.dev",
        us_citizen=True,
        sponsorship_needed=False,
        veteran_status="no",
        gender="Female",
        ethnicity="Prefer not to say",
    )


class TestDetectFieldType:
    def test_first_name_detection(self):
        field_key, confidence = detect_field_type("input", "text", "First Name", "first_name", "", "")
        assert field_key == "first_name"
        assert confidence > 0.7

    def test_email_detection(self):
        field_key, confidence = detect_field_type("input", "email", "", "email", "Enter your email", "")
        assert field_key == "email"

    def test_phone_detection(self):
        field_key, confidence = detect_field_type("input", "tel", "Phone Number", "", "", "")
        assert field_key == "phone"

    def test_linkedin_detection(self):
        field_key, confidence = detect_field_type("input", "url", "LinkedIn URL", "linkedin_url", "", "")
        assert field_key == "linkedin_url"

    def test_citizenship_detection(self):
        field_key, confidence = detect_field_type("select", "", "Are you authorized to work in the US?", "", "", "")
        assert field_key == "us_citizen"

    def test_sponsorship_detection(self):
        field_key, confidence = detect_field_type("select", "", "Do you require visa sponsorship?", "", "", "")
        assert field_key == "sponsorship_needed"

    def test_unknown_field(self):
        field_key, confidence = detect_field_type("input", "text", "", "", "", "")
        assert field_key == "unknown"
        assert confidence < CONFIDENCE_THRESHOLD

    def test_resume_file_upload(self):
        field_key, confidence = detect_field_type("input", "file", "Upload Resume", "", "", "")
        assert field_key == "resume"

    def test_veteran_detection(self):
        field_key, confidence = detect_field_type("select", "", "Veteran Status", "veteran", "", "")
        assert field_key == "veteran_status"

    def test_gender_detection(self):
        field_key, confidence = detect_field_type("select", "", "Gender", "gender", "", "")
        assert field_key == "gender"


class TestGetProfileValue:
    def test_full_name(self, profile):
        value, confidence = _get_profile_value(profile, "full_name")
        assert value == "Jane Doe"
        assert confidence > 0.9

    def test_email(self, profile):
        value, confidence = _get_profile_value(profile, "email")
        assert value == "jane@example.com"

    def test_us_citizen_yes(self, profile):
        value, confidence = _get_profile_value(profile, "us_citizen")
        assert value == "Yes"

    def test_sponsorship_no(self, profile):
        value, confidence = _get_profile_value(profile, "sponsorship_needed")
        assert value == "No"

    def test_missing_field(self, profile):
        profile.website_url = ""
        value, confidence = _get_profile_value(profile, "website_url")
        assert value == ""
        assert confidence == 0.0

    def test_us_citizen_none(self, profile):
        profile.us_citizen = None
        value, confidence = _get_profile_value(profile, "us_citizen")
        assert value == ""
        assert confidence == 0.0


class TestHasCaptcha:
    def test_recaptcha_detected(self):
        assert has_captcha('<div class="g-recaptcha" data-sitekey="abc"></div>') is True

    def test_hcaptcha_detected(self):
        assert has_captcha('<div class="h-captcha"></div>') is True

    def test_turnstile_detected(self):
        assert has_captcha('<div class="cf-turnstile"></div>') is True

    def test_no_captcha(self):
        assert has_captcha("<form><input type='text'/></form>") is False

    def test_captcha_in_script(self):
        assert has_captcha('<script src="recaptcha/api.js"></script>') is True


class TestNeedsHumanReview:
    def test_all_filled(self):
        fields = [
            {"status": "filled", "field_name": "name"},
            {"status": "filled", "field_name": "email"},
        ]
        assert needs_human_review(fields) is False

    def test_some_need_input(self):
        fields = [
            {"status": "filled", "field_name": "name"},
            {"status": "needs_input", "field_name": "cover_letter"},
        ]
        assert needs_human_review(fields) is True

    def test_empty_fields(self):
        assert needs_human_review([]) is False
