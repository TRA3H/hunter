import pytest

from app.services.matcher import (
    compute_keyword_score,
    compute_location_score,
    compute_match_score,
    compute_title_similarity,
)


class TestComputeKeywordScore:
    def test_all_keywords_match(self):
        text = "Python FastAPI React PostgreSQL Docker"
        keywords = ["python", "fastapi", "react"]
        score = compute_keyword_score(text, keywords)
        assert score == 100.0

    def test_partial_match(self):
        text = "Python FastAPI PostgreSQL"
        keywords = ["python", "fastapi", "react", "typescript"]
        score = compute_keyword_score(text, keywords)
        assert score == 50.0

    def test_no_match(self):
        text = "Java Spring Boot MySQL"
        keywords = ["python", "fastapi"]
        score = compute_keyword_score(text, keywords)
        assert score == 0.0

    def test_empty_keywords(self):
        score = compute_keyword_score("some text", [])
        assert score == 0.0

    def test_case_insensitive(self):
        text = "PYTHON fastapi React"
        keywords = ["Python", "FastAPI"]
        score = compute_keyword_score(text, keywords)
        assert score == 100.0


class TestComputeTitleSimilarity:
    def test_exact_match(self):
        score = compute_title_similarity("Senior Software Engineer", "Senior Software Engineer")
        assert score == 100.0

    def test_partial_overlap(self):
        score = compute_title_similarity("Software Engineer", "Senior Software Engineer")
        # "Software" and "Engineer" match, "Senior" doesn't
        assert 50.0 <= score <= 80.0

    def test_no_overlap(self):
        score = compute_title_similarity("Product Manager", "Senior Software Engineer")
        assert score == 0.0

    def test_empty_desired(self):
        score = compute_title_similarity("Senior Engineer", "")
        assert score == 0.0


class TestComputeLocationScore:
    def test_remote_match(self):
        score = compute_location_score("Remote", "", "remote")
        assert score == 100.0

    def test_city_match(self):
        score = compute_location_score("San Francisco, CA", "San Francisco, CA", "")
        assert score == 100.0

    def test_partial_city_match(self):
        score = compute_location_score("San Francisco, CA (Hybrid)", "San Francisco", "")
        assert score == 100.0

    def test_no_match(self):
        score = compute_location_score("Chicago, IL", "San Francisco, CA", "onsite")
        assert score == 0.0

    def test_no_preference(self):
        score = compute_location_score("Anywhere", "", "")
        assert score == 50.0

    def test_remote_in_any_preference(self):
        score = compute_location_score("Remote", "", "any")
        assert score == 100.0


class TestComputeMatchScore:
    def test_high_match(self, sample_job):
        score = compute_match_score(
            sample_job,
            keywords=["python", "fastapi", "react", "postgresql", "docker"],
            desired_title="Senior Software Engineer",
            desired_locations="San Francisco, CA",
            remote_preference="remote",
        )
        assert score >= 70.0

    def test_low_match(self, sample_job):
        score = compute_match_score(
            sample_job,
            keywords=["java", "spring", "angular"],
            desired_title="Product Manager",
            desired_locations="Chicago, IL",
            remote_preference="onsite",
        )
        assert score < 30.0

    def test_score_bounds(self, sample_job):
        score = compute_match_score(sample_job, [], "", "", "")
        assert 0.0 <= score <= 100.0
