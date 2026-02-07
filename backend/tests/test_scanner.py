import pytest

from app.services.scanner import compute_dedup_hash, parse_salary


class TestComputeDedupHash:
    def test_url_based_dedup(self):
        hash1 = compute_dedup_hash("https://example.com/jobs/123", "Engineer", "Corp")
        hash2 = compute_dedup_hash("https://example.com/jobs/123", "Different Title", "Different Corp")
        assert hash1 == hash2  # Same URL = same hash

    def test_different_urls_different_hashes(self):
        hash1 = compute_dedup_hash("https://example.com/jobs/123", "", "")
        hash2 = compute_dedup_hash("https://example.com/jobs/456", "", "")
        assert hash1 != hash2

    def test_url_normalization(self):
        hash1 = compute_dedup_hash("https://example.com/jobs/123/", "", "")
        hash2 = compute_dedup_hash("https://example.com/jobs/123", "", "")
        assert hash1 == hash2  # Trailing slash stripped

    def test_case_insensitive_url(self):
        hash1 = compute_dedup_hash("https://Example.COM/Jobs/123", "", "")
        hash2 = compute_dedup_hash("https://example.com/jobs/123", "", "")
        assert hash1 == hash2

    def test_fallback_to_title_company(self):
        hash1 = compute_dedup_hash("", "Senior Engineer", "TechCorp")
        hash2 = compute_dedup_hash("", "Senior Engineer", "TechCorp")
        assert hash1 == hash2

    def test_title_company_case_insensitive(self):
        hash1 = compute_dedup_hash("", "Senior Engineer", "TechCorp")
        hash2 = compute_dedup_hash("", "senior engineer", "techcorp")
        assert hash1 == hash2


class TestParseSalary:
    def test_range_with_dollar_sign(self):
        assert parse_salary("$80,000 - $120,000") == (80000, 120000)

    def test_range_with_k_notation(self):
        assert parse_salary("$100K - $150K") == (100000, 150000)

    def test_range_with_lowercase_k(self):
        assert parse_salary("100k - 150k") == (100000, 150000)

    def test_single_value(self):
        assert parse_salary("$120,000") == (120000, 120000)

    def test_single_k_value(self):
        assert parse_salary("120K") == (120000, 120000)

    def test_empty_string(self):
        assert parse_salary("") == (None, None)

    def test_no_salary(self):
        assert parse_salary("Competitive") == (None, None)

    def test_range_with_to(self):
        assert parse_salary("$80,000 to $120,000") == (80000, 120000)

    def test_range_with_dash(self):
        assert parse_salary("80000–120000") == (80000, 120000)
