"""Tests for the scraper lead validator."""
import pytest
from services.scraper.validators import LeadValidator, ValidationResult


@pytest.fixture
def validator():
    return LeadValidator()


class TestLeadValidator:
    """Unit tests for lead quality validation."""

    def test_valid_startup_domain(self, validator):
        result = validator.validate({
            "name": "Acme SaaS",
            "website": "https://acme.io",
            "description": "A project management platform for teams",
            "source_provider": "producthunt",
        })
        assert result.is_valid is True
        assert result.is_startup is True

    def test_rejects_medium_article(self, validator):
        result = validator.validate({
            "name": "How We Scaled to 10K Users",
            "website": "https://medium.com/@founder/how-we-scaled",
            "description": "A deep dive into our growth strategy...",
            "source_provider": "hackernews",
        })
        assert result.is_article is True or result.is_valid is False

    def test_rejects_platform_domain(self, validator):
        result = validator.validate({
            "name": "Some Post",
            "website": "https://news.ycombinator.com/item?id=123",
            "description": "A discussion post",
            "source_provider": "hackernews",
        })
        assert result.is_platform_page is True

    def test_rejects_techcrunch(self, validator):
        result = validator.validate({
            "name": "Startup Raises $10M",
            "website": "https://techcrunch.com/2024/startup-raises-10m/",
            "description": "Article about a startup",
            "source_provider": "hackernews",
        })
        assert result.is_platform_page is True

    def test_valid_show_hn_post(self, validator):
        result = validator.validate({
            "name": "My New App",
            "website": "https://mynewapp.co",
            "description": "Show HN: I built a task manager",
            "source_provider": "hackernews",
        })
        assert result.is_valid is True
        assert result.startup_likelihood >= 25

    def test_domain_quality_scoring(self, validator):
        # Good TLD
        r1 = validator._score_domain("example.io", "https://example.io")
        assert r1 >= 50

        # Low-quality TLD
        r2 = validator._score_domain("example.tk", "http://example.tk")
        assert r2 < 50

        # Short suspicious domain
        r3 = validator._score_domain("ab.co", "https://ab.co")
        assert r3 < 50

    def test_rejects_generic_domain(self, validator):
        result = validator.validate({
            "name": "Top 10 Free Tools",
            "website": "https://top-free-tools.tk",
            "description": "List of free tools",
            "source_provider": "hackernews",
        })
        assert result.is_valid is False

    def test_no_domain_rejected(self, validator):
        result = validator.validate({
            "name": "Mysterious",
            "website": "",
            "description": "No website",
            "source_provider": "hackernews",
        })
        assert result.is_valid is False
        assert "No domain found" in result.rejection_reasons

    def test_article_headline_penalized(self, validator):
        result = validator.validate({
            "name": "Why We Chose to Build with Rust: A Comprehensive Guide",
            "website": "https://blog.example.com/rust-guide",
            "description": "Our journey with Rust",
            "source_provider": "hackernews",
        })
        assert result.is_valid is False or result.startup_likelihood < 35

    def test_valid_short_brand_name(self, validator):
        result = validator.validate({
            "name": "Flow",
            "website": "https://flow.app",
            "description": "Workflow automation",
            "source_provider": "producthunt",
        })
        assert result.is_valid is True

    def test_producthunt_boost(self, validator):
        result = validator.validate({
            "name": "New Tool",
            "website": "https://newtool.dev",
            "description": "A developer tool",
            "source_provider": "producthunt",
        })
        assert result.startup_likelihood >= 40

    def test_validation_result_dataclass(self, validator):
        result = validator.validate({
            "name": "Test",
            "website": "https://test.co",
            "description": "Test description",
        })
        assert isinstance(result, ValidationResult)
        assert hasattr(result, "is_valid")
        assert hasattr(result, "domain_quality_score")
        assert hasattr(result, "startup_likelihood")
        assert hasattr(result, "rejection_reasons")
