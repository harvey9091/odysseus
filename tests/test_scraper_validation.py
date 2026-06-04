"""Tests for the Generic Discovery Agent."""
import pytest
from services.scraper.discovery_agent import DiscoveryAgent, ExtractedLead
from services.scraper.service import ScraperService


@pytest.fixture
def agent():
    return DiscoveryAgent(headless=True, timeout=10)


@pytest.fixture
def service():
    return ScraperService()


class TestExtractedLead:
    """Unit tests for lead data structure."""

    def test_to_dict(self, agent):
        lead = ExtractedLead(
            company_name="Acme Inc",
            website="https://acme.io",
            description="A SaaS platform",
            founders=[{"name": "John Doe", "role": "founder"}],
            emails=["hello@acme.io", "john@acme.io"],
            linkedin="https://linkedin.com/company/acme",
            twitter="https://twitter.com/acme",
            github="https://github.com/acme",
            contact_page="https://acme.io/contact",
            industry="saas",
            source_url="https://producthunt.com/posts/acme",
        )
        result = lead.to_dict()
        assert result["name"] == "Acme Inc"
        assert result["website"] == "https://acme.io"
        assert result["domain"] == "acme.io"
        assert len(result["founders"]) == 1
        assert len(result["emails"]) == 2
        assert result["industry"] == "saas"

    def test_domain_extraction(self, agent):
        lead = ExtractedLead(website="https://www.example.com/path")
        assert lead._extract_domain("https://www.example.com/path") == "example.com"


class TestDiscoveryAgentExtraction:
    """Unit tests for content extraction methods."""

    def test_is_valid_name(self, agent):
        assert agent._is_valid_name("Acme Inc") is True
        assert agent._is_valid_name("") is False
        assert agent._is_valid_name("A") is False
        assert agent._is_valid_name("Advertisement Banner") is False

    def test_is_valid_email(self, agent):
        assert agent._is_valid_email("hello@acme.io") is True
        assert agent._is_valid_email("john.doe@acme.io") is True
        assert agent._is_valid_email("noreply@example.com") is False
        assert agent._is_valid_email("test@sentry.io") is False

    def test_is_valid_startup(self, agent):
        lead = ExtractedLead(company_name="Acme", website="https://acme.io")
        assert agent._is_valid_startup(lead) is True

        lead.website = "https://medium.com/@user/post"
        assert agent._is_valid_startup(lead) is False


class TestDiscoveryAgentExtractionMethods:
    """Test HTML extraction methods."""

    def test_extract_company_name_from_html(self, agent):
        html = "<html><head><title>Acme - Product Hunt</title></head><body><h1>Acme</h1></body></html>"
        result = agent._extract_company_name(html, "https://example.com")
        assert result == "Acme"

    def test_extract_description(self, agent):
        html = '<html><head><meta property="og:description" content="A test company for all your needs."></head><body></body></html>'
        result = agent._extract_description(html)
        assert "test company" in result.lower()

    def test_extract_industry(self, agent):
        html = "We build artificial intelligence tools for developers"
        result = agent._extract_industry(html)
        assert "ai_ml" in result

    def test_extract_social_profiles(self, agent):
        html = '<a href="https://twitter.com/acme">Twitter</a><a href="https://github.com/acme/repo">GitHub</a>'
        result = agent._extract_social_profiles(html)
        assert "twitter" in result or "github" in result

    def test_extract_emails_from_content(self, agent):
        html = "Contact us at hello@acme.io or john.doe@acme.io"
        result = agent._extract_emails_from_content(html)
        emails = [e for e in result]
        assert "hello@acme.io" in emails or "john.doe@acme.io" in emails


class TestURLValidation:
    """Tests for URL validation logic."""

    def test_valid_urls_accepted(self, service):
        assert service._is_valid_url("https://www.producthunt.com/leaderboard/daily/2026/6/3?ref=header_nav") is True
        assert service._is_valid_url("https://www.producthunt.com/leaderboard/daily") is True
        assert service._is_valid_url("https://betalist.com") is True
        assert service._is_valid_url("https://betalist.com/browse/productivity/saas") is True

    def test_invalid_urls_rejected(self, service):
        assert service._is_valid_url("") is False
        assert service._is_valid_url("not-a-url") is False
        assert service._is_valid_url("ftp://example.com") is False
        assert service._is_valid_url("httpx://example.com") is False

    def test_empty_url_rejected(self, service):
        assert service._is_valid_url(None) is False