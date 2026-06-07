"""
Odysseus Universal Integrations Platform
========================================
Versioned integration registry with dynamic presets, category grouping,
agent tool discovery, and backward-compatible storage.
"""

import json
import os
import uuid
import logging
import re
from typing import Dict, List, Optional, Any

import httpx

from core.atomic_io import atomic_write_json
from core.platform_compat import safe_chmod
from src.secret_storage import decrypt, encrypt, is_encrypted

log = logging.getLogger(__name__)

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "integrations.json")
STORAGE_VERSION = 2


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

INTEGRATION_CATEGORIES: Dict[str, Dict[str, str]] = {
    "ai":            {"label": "AI Providers",     "icon": "🤖"},
    "lead":          {"label": "Lead Generation",  "icon": "🎯"},
    "crm":           {"label": "CRM",              "icon": "💼"},
    "automation":    {"label": "Automation",        "icon": "⚡"},
    "communication": {"label": "Communication",     "icon": "💬"},
    "productivity":  {"label": "Productivity",      "icon": "📋"},
    "search":        {"label": "Search / Research", "icon": "🔍"},
    "email":         {"label": "Email Marketing",   "icon": "📧"},
    "database":      {"label": "Databases",         "icon": "🗄️"},
}


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

INTEGRATION_PRESETS: Dict[str, Dict[str, Any]] = {
    # ---- AI Providers ----
    "openrouter": {
        "name": "OpenRouter",
        "category": "ai",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "OpenRouter unified LLM API gateway. Key endpoints:\n"
            "  GET /api/v1/models — list available models\n"
            "  POST /api/v1/chat/completions — chat completion\n"
            "  POST /api/v1/completions — text completion\n"
            "Auth: Include 'Bearer ' prefix in your API key value."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/v1/models",
    },

    # ---- Lead Generation ----
    "apollo": {
        "name": "Apollo",
        "category": "lead",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Apollo sales intelligence API. Key endpoints:\n"
            "  POST /api/v1/mixed_companies/search — search companies\n"
            "  GET /api/v1/people/match — match people\n"
            "  GET /api/v1/organizations/enrich — enrich org data\n"
            "  POST /api/v1/people/enrich — enrich people data"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/v1/auth/health",
    },
    "hunter": {
        "name": "Hunter.io",
        "category": "lead",
        "auth_type": "header",
        "auth_header": "X-Hunter-Key",
        "description": (
            "Hunter.io email finding and verification API. Key endpoints:\n"
            "  GET /v2/email-verifier — verify email\n"
            "  GET /v2/domain-search — find emails at a domain\n"
            "  GET /v2/email-count — count emails at a domain\n"
            "  GET /v2/people — find people at a company"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v2/domain-search?domain=example.com",
    },
    "snov": {
        "name": "Snov.io",
        "category": "lead",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Snov.io email finder and verifier API. Key endpoints:\n"
            "  GET /v1/email/find — find emails by name/domain\n"
            "  GET /v1/email/verify — verify email\n"
            "  POST /v1/domain/search — search domain emails\n"
            "  GET /v1/profile — get profile by email"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v1/account/info",
    },
    "clearbit": {
        "name": "Clearbit",
        "category": "lead",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Clearbit company and person enrichment API. Key endpoints:\n"
            "  GET /v1/companies/domain:{domain} — company lookup\n"
            "  POST /v1/people/find — find people at company\n"
            "  GET /v1/people/email:{email} — person by email\n"
            "  GET /v1/companies/search — search companies"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v1/companies/search",
    },
    "clay": {
        "name": "Clay",
        "category": "lead",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Clay enrichment API. Key endpoints:\n"
            "  POST /v1/enrichments/person — enrich person data\n"
            "  POST /v1/enrichments/company — enrich company data\n"
            "  GET /v1/workbooks/{id} — get workbook\n"
            "  POST /v1/workbooks/{id}/run — run workbook"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v1/account",
    },
    "peopledatalabs": {
        "name": "PeopleDataLabs",
        "category": "lead",
        "auth_type": "header",
        "auth_header": "X-Api-Key",
        "description": (
            "PeopleDataLabs people/company enrichment API. Key endpoints:\n"
            "  GET /v5/person/enrich — enrich person by email/linkedin\n"
            "  GET /v5/company/enrich — enrich company by domain\n"
            "  GET /v5/emails/enrich — enrich email\n"
            "  GET /v5/person/search — search people"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v5/person/enrich",
    },
    "serper": {
        "name": "Serper.dev",
        "category": "search",
        "auth_type": "header",
        "auth_header": "X-API-KEY",
        "description": (
            "Serper.dev Google search API wrapper. Key endpoints:\n"
            "  POST / — Google search (JSON body: {q, num, gl, hl})\n"
            "  POST /images — image search\n"
            "  POST /news — news search\n"
            "  POST /places — local/places search"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/",
    },

    # ---- CRM ----
    "hubspot": {
        "name": "HubSpot",
        "category": "crm",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "HubSpot CRM API. Key endpoints:\n"
            "  GET /crm/v3/objects/contacts — list contacts\n"
            "  POST /crm/v3/objects/contacts — create contact\n"
            "  GET /crm/v3/objects/companies — list companies\n"
            "  POST /crm/v3/objects/deals — create deal\n"
            "  GET /crm/v3/objects/tickets — list tickets"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/crm/v3/objects/contacts",
    },
    "salesforce": {
        "name": "Salesforce",
        "category": "crm",
        "auth_type": "oauth2",
        "description": (
            "Salesforce CRM API. Key endpoints:\n"
            "  GET /services/data/v57.0/sobjects — list objects\n"
            "  GET /services/data/v57.0/query?q=SELECT... — SOQL query\n"
            "  POST /services/data/v57.0/sobjects/Account — create record\n"
            "  PATCH /services/data/v57.0/sobjects/Account/{id} — update\n"
            "Note: Supports OAuth2 JWT Bearer or Username-Password flow."
        ),
        "required_fields": ["base_url", "client_id", "client_secret"],
        "optional_fields": ["username", "password", "security_token"],
        "test_endpoint": "/services/data/v57.0/sobjects",
    },
    "pipedrive": {
        "name": "Pipedrive",
        "category": "crm",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Pipedrive sales CRM API. Key endpoints:\n"
            "  GET /v1/users/me — current user\n"
            "  GET /v1/persons — list persons\n"
            "  POST /v1/persons — create person\n"
            "  GET /v1/deals — list deals\n"
            "  POST /v1/deals — create deal\n"
            "  GET /v1/organizations — list orgs"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v1/users/me",
    },
    "zoho": {
        "name": "Zoho CRM",
        "category": "crm",
        "auth_type": "oauth2",
        "description": (
            "Zoho CRM API. Key endpoints:\n"
            "  GET /crm/v2/Leads — list leads\n"
            "  POST /crm/v2/Leads — create lead\n"
            "  GET /crm/v2/Contacts — list contacts\n"
            "  PUT /crm/v2/Leads/{id} — update lead\n"
            "Note: Requires OAuth2 client credentials."
        ),
        "required_fields": ["base_url", "client_id", "client_secret"],
        "optional_fields": ["refresh_token"],
        "test_endpoint": "/crm/v2/Leads",
    },

    # ---- Automation ----
    "n8n": {
        "name": "N8N",
        "category": "automation",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "N8N workflow automation API. Key endpoints:\n"
            "  GET /api/v1/workflows — list workflows\n"
            "  POST /api/v1/workflows — create workflow\n"
            "  POST /api/v1/workflows/{id}/execute — execute workflow\n"
            "  GET /api/v1/executions — list executions\n"
            "  POST /api/v1/credentials — create credential"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/v1/workflows",
    },
    "make": {
        "name": "Make.com",
        "category": "automation",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Make.com (Integromat) automation API. Key endpoints:\n"
            "  GET /v1/scenarios — list scenarios\n"
            "  POST /v1/scenarios/{id}/run — execute scenario\n"
            "  GET /v1/hooks/{id}/scenarios — list hook scenarios\n"
            "  POST /v1/hooks/{id}/execute — execute hook\n"
            "Auth: Use API token from Make account settings."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v1/scenarios",
    },
    "zapier": {
        "name": "Zapier",
        "category": "automation",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Zapier automation platform. Key endpoints:\n"
            "  GET /v1/zaps — list zaps\n"
            "  POST /v1/zaps/{id}/run — execute zap\n"
            "  GET /v1/accounts/{id}/templates — list templates\n"
            "Note: Zapier API access requires Zapier Platform account."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v1/zaps",
    },

    # ---- Communication ----
    "slack": {
        "name": "Slack",
        "category": "communication",
        "auth_type": "bearer",
        "description": (
            "Slack team messaging API. Key endpoints:\n"
            "  GET /api/auth.test — test auth\n"
            "  POST /api/chat.postMessage — send message\n"
            "  GET /api/conversations.list — list channels\n"
            "  POST /api/files.upload — upload file\n"
            "  GET /api/users.list — list users"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": ["channel"],
        "test_endpoint": "/api/auth.test",
    },
    "discord": {
        "name": "Discord",
        "category": "communication",
        "auth_type": "bearer",
        "description": (
            "Discord community messaging API. Key endpoints:\n"
            "  GET /api/v10/users/@me — get bot user\n"
            "  POST /api/v10/channels/{id}/messages — send message\n"
            "  GET /api/v10/guilds/{id}/channels — list channels\n"
            "  POST /api/v10/webhooks/{id}/{token} — webhook delivery"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": ["webhook_url"],
        "test_endpoint": "/api/v10/users/@me",
    },
    "telegram": {
        "name": "Telegram Bot",
        "category": "communication",
        "auth_type": "bearer",
        "description": (
            "Telegram Bot API. Key endpoints:\n"
            "  GET /bot{token}/getMe — get bot info\n"
            "  POST /bot{token}/sendMessage — send message\n"
            "  GET /bot{token}/getUpdates — get updates\n"
            "  POST /bot{token}/sendPhoto — send photo\n"
            "  POST /bot{token}/answerCallbackQuery — answer callback"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": ["chat_id"],
        "test_endpoint": "/bot{BOT_TOKEN}/getMe",  # BOT_TOKEN replaced by api_key
    },
    "twilio": {
        "name": "Twilio",
        "category": "communication",
        "auth_type": "basic",
        "description": (
            "Twilio SMS/voice API. Key endpoints:\n"
            "  GET /2010-04-01/Accounts/{AccountSid}.json — account info\n"
            "  POST /2010-04-01/Accounts/{AccountSid}/Messages.json — send SMS\n"
            "  POST /2010-04-01/Accounts/{AccountSid}/Calls.json — make call\n"
            "Note: api_key stores AccountSid, AuthToken goes in password."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": ["password"],
        "test_endpoint": "/2010-04-01/Accounts/{AccountSid}.json",
    },
    "whatsapp": {
        "name": "WhatsApp Business",
        "category": "communication",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "WhatsApp Business Cloud API. Key endpoints:\n"
            "  GET /v17.0/{PHONE_NUMBER_ID} — get number info\n"
            "  POST /v17.0/{PHONE_NUMBER_ID}/messages — send message\n"
            "  GET /v17.0/{PHONE_NUMBER_ID}/templates — list templates\n"
            "Auth: Include 'Bearer ' prefix in your API key value."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": ["phone_number_id"],
        "test_endpoint": "/v17.0/{PHONE_NUMBER_ID}",
    },

    # ---- Productivity ----
    "notion": {
        "name": "Notion",
        "category": "productivity",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Notion knowledge base API. Key endpoints:\n"
            "  GET /v1/users/me — get current user\n"
            "  POST /v1/search — search pages/databases\n"
            "  POST /v1/pages — create page\n"
            "  PATCH /v1/pages/{id} — update page\n"
            "  POST /v1/databases/{id}/query — query database\n"
            "Auth: Include 'Bearer ' prefix in your API key value."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v1/users/me",
    },
    "clickup": {
        "name": "ClickUp",
        "category": "productivity",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "ClickUp project management API. Key endpoints:\n"
            "  GET /api/v2/team — list teams\n"
            "  GET /api/v2/team/{id}/space — list spaces\n"
            "  GET /api/v2/list/{id}/task — list tasks\n"
            "  POST /api/v2/list/{id}/task — create task\n"
            "  PUT /api/v2/task/{id} — update task"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/v2/team",
    },
    "trello": {
        "name": "Trello",
        "category": "productivity",
        "auth_type": "query",
        "auth_param": "key",
        "description": (
            "Trello kanban board API. Key endpoints:\n"
            "  GET /1/members/me — get current user\n"
            "  GET /1/boards/{id}/lists — list lists\n"
            "  GET /1/lists/{id}/cards — list cards\n"
            "  POST /1/cards — create card\n"
            "  PUT /1/cards/{id} — update card\n"
            "Auth: api_key is your Trello key; api_secret is your token."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": ["api_secret"],
        "test_endpoint": "/1/members/me",
    },
    "asana": {
        "name": "Asana",
        "category": "productivity",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Asana project management API. Key endpoints:\n"
            "  GET /api/v1/workspaces — list workspaces\n"
            "  GET /api/v1/projects — list projects\n"
            "  GET /api/v1/tasks — list tasks\n"
            "  POST /api/v1/tasks — create task\n"
            "  PUT /api/v1/tasks/{id} — update task"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/v1/workspaces",
    },

    # ---- Search / Research ----
    "tavily": {
        "name": "Tavily",
        "category": "search",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Tavily AI search API. Key endpoints:\n"
            "  POST /v1/search — web search (JSON body: {query, max_results, topic})\n"
            "  POST /v1/search/image — image search\n"
            "  POST /v1/search/news — news search\n"
            "  POST /v1/crawl — crawl a URL\n"
            "Auth: Include 'Bearer ' prefix in your API key value."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v1/search",
    },
    "brave": {
        "name": "Brave Search",
        "category": "search",
        "auth_type": "header",
        "auth_header": "X-Subscription-Token",
        "description": (
            "Brave Search API (privacy-focused). Key endpoints:\n"
            "  GET /api/v1/web/search — web search\n"
            "  GET /api/v1/images/search — image search\n"
            "  GET /api/v1/news/search — news search\n"
            "  GET /api/v1/suggest — query suggestions\n"
            "Auth: X-Subscription-Token header."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/v1/web/search",
    },

    # ---- Email Marketing ----
    "listmonk": {
        "name": "Listmonk",
        "category": "email",
        "auth_type": "basic",
        "description": (
            "Listmonk newsletter/email marketing API. Key endpoints:\n"
            "  GET /api/v1/health — health check\n"
            "  GET /api/v1/subscribers — list subscribers\n"
            "  POST /api/v1/subscribers — create subscriber\n"
            "  GET /api/v1/campaigns — list campaigns\n"
            "  POST /api/v1/campaigns — create campaign\n"
            "  POST /api/v1/campaigns/{id}/start — launch campaign\n"
            "  POST /api/v1/campaigns/{id}/pause — pause campaign\n"
            "  GET /api/v1/campaigns/{id}/stats — campaign statistics\n"
            "Auth: Username + password (basic auth) OR admin token."
        ),
        "required_fields": ["base_url"],
        "optional_fields": ["username", "password", "admin_token"],
        "test_endpoint": "/api/v1/health",
        "actions": [
            {
                "name": "sync_subscribers",
                "description": "Sync subscribers from external source",
                "method": "POST",
                "path": "/api/v1/subscribers/sync",
                "params": {
                    "list_id": {"type": "integer", "description": "Target mailing list ID"},
                },
            },
            {
                "name": "create_campaign",
                "description": "Create a new email campaign",
                "method": "POST",
                "path": "/api/v1/campaigns",
                "params": {
                    "name": {"type": "string", "description": "Campaign name"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "list_id": {"type": "integer", "description": "Target mailing list ID"},
                    "template_id": {"type": "integer", "description": "Template ID (optional)"},
                },
            },
            {
                "name": "launch_campaign",
                "description": "Launch a scheduled campaign immediately",
                "method": "POST",
                "path": "/api/v1/campaigns/{campaign_id}/start",
                "params": {
                    "campaign_id": {"type": "integer", "description": "Campaign ID to launch"},
                },
            },
            {
                "name": "pause_campaign",
                "description": "Pause a running campaign",
                "method": "POST",
                "path": "/api/v1/campaigns/{campaign_id}/pause",
                "params": {
                    "campaign_id": {"type": "integer", "description": "Campaign ID to pause"},
                },
            },
            {
                "name": "get_statistics",
                "description": "Get campaign statistics",
                "method": "GET",
                "path": "/api/v1/campaigns/{campaign_id}/stats",
                "params": {
                    "campaign_id": {"type": "integer", "description": "Campaign ID"},
                },
            },
        ],
    },
    "mailchimp": {
        "name": "Mailchimp",
        "category": "email",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Mailchimp email marketing API. Key endpoints:\n"
            "  GET /3.0/lists — list audiences\n"
            "  GET /3.0/lists/{id}/members — list members\n"
            "  POST /3.0/lists/{id}/members — add member\n"
            "  POST /3.0/campaigns — create campaign\n"
            "  POST /3.0/campaigns/{id}/actions/send — send campaign\n"
            "Auth: Include 'Bearer ' prefix in your API key value."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/3.0/lists",
    },
    "brevo": {
        "name": "Brevo",
        "category": "email",
        "auth_type": "header",
        "auth_header": "api-key",
        "description": (
            "Brevo (formerly Sendinblue) email/marketing API. Key endpoints:\n"
            "  GET /v3/smtp/statistics — email stats\n"
            "  GET /v3/contacts — list contacts\n"
            "  POST /v3/contacts — create contact\n"
            "  POST /v3/smtp/email — send email\n"
            "  GET /v3/lists — list contact lists"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v3/smtp/statistics",
    },
    "sendgrid": {
        "name": "SendGrid",
        "category": "email",
        "auth_type": "bearer",
        "description": (
            "SendGrid email delivery API. Key endpoints:\n"
            "  GET /v3/marketing/contacts — list contacts\n"
            "  POST /v3/marketing/contacts — add contacts\n"
            "  POST /v3/mail/send — send email\n"
            "  GET /v3/templates — list templates\n"
            "  GET /v3/templates/{id} — get template"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v3/marketing/contacts",
    },
    "postmark": {
        "name": "Postmark",
        "category": "email",
        "auth_type": "header",
        "auth_header": "X-Postmark-Server-Token",
        "description": (
            "Postmark email delivery API. Key endpoints:\n"
            "  GET /v1/email — send email\n"
            "  GET /v1/servers/{id}/statistics — server stats\n"
            "  GET /v1/messages — list messages\n"
            "  GET /v1/templates — list templates\n"
            "  POST /v1/batch — batch send"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v1/servers",
    },
    "mailgun": {
        "name": "Mailgun",
        "category": "email",
        "auth_type": "basic",
        "description": (
            "Mailgun email delivery API. Key endpoints:\n"
            "  GET /v3/{domain}/messages — list messages\n"
            "  POST /v3/{domain}/messages — send email\n"
            "  GET /v3/{domain}/events — list events\n"
            "  GET /v3/{domain}/routes — list routes\n"
            "  POST /v3/{domain}/routes — create route\n"
            "Auth: api_key is 'api:MAILGUN_API_KEY' for basic auth."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v3/domains",
    },

    # ---- Databases ----
    "postgres": {
        "name": "PostgreSQL",
        "category": "database",
        "auth_type": "basic",
        "description": (
            "PostgreSQL direct database connection. Uses psycopg2/binary driver.\n"
            "Connection format: postgresql://USER:PASSWORD@HOST:PORT/DB\n"
            "Supported operations: query, insert, update, delete, schema introspection.\n"
            "Auth: Username + password in api_key field as 'user:password'."
        ),
        "required_fields": ["base_url"],
        "optional_fields": ["username", "password", "api_key"],
        "test_endpoint": "/",
    },
    "mysql": {
        "name": "MySQL",
        "category": "database",
        "auth_type": "basic",
        "description": (
            "MySQL direct database connection. Uses mysql-connector-python driver.\n"
            "Connection format: mysql://USER:PASSWORD@HOST:PORT/DB\n"
            "Supported operations: query, insert, update, delete, schema introspection.\n"
            "Auth: Username + password in api_key field as 'user:password'."
        ),
        "required_fields": ["base_url"],
        "optional_fields": ["username", "password", "api_key"],
        "test_endpoint": "/",
    },
    "supabase": {
        "name": "Supabase",
        "category": "database",
        "auth_type": "header",
        "auth_header": "apikey",
        "description": (
            "Supabase Postgres + APIs. Key endpoints:\n"
            "  GET /rest/v1/{table} — query table (PostgREST)\n"
            "  POST /rest/v1/{table} — insert row\n"
            "  PATCH /rest/v1/{table} — update rows\n"
            "  DELETE /rest/v1/{table} — delete rows\n"
            "  GET /auth/v1/user — get current user\n"
            "Auth: anon key for public access, service_role key for admin."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/rest/v1/",
    },
    "qdrant": {
        "name": "Qdrant",
        "category": "database",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Qdrant vector database API. Key endpoints:\n"
            "  GET /collections — list collections\n"
            "  PUT /collections/{name} — create collection\n"
            "  POST /collections/{name}/points — upsert points\n"
            "  POST /collections/{name}/search — search points\n"
            "  GET /collections/{name}/points/{id} — get point\n"
            "Auth: Include 'Bearer ' prefix in your API key value."
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/healthz",
    },
    "chroma": {
        "name": "Chroma",
        "category": "database",
        "auth_type": "none",
        "description": (
            "Chroma vector database API. Key endpoints:\n"
            "  GET /api/v1/collections — list collections\n"
            "  POST /api/v1/collections — create collection\n"
            "  POST /api/v1/collections/{id}/add — add documents\n"
            "  POST /api/v1/collections/{id}/query — query\n"
            "  POST /api/v1/collections/{id}/delete — delete\n"
            "No auth required for local instances."
        ),
        "required_fields": ["base_url"],
        "optional_fields": ["api_key"],
        "test_endpoint": "/api/v1/heartbeat",
    },

    # ---- Existing presets (backward compat) ----
    "miniflux": {
        "name": "Miniflux",
        "category": "rss",
        "auth_type": "header",
        "auth_header": "X-Auth-Token",
        "description": (
            "Miniflux RSS reader (v1 API). Key endpoints:\n"
            "  GET /v1/feeds — list all feeds\n"
            "  GET /v1/feeds/{id} — get feed details\n"
            "  POST /v1/feeds — create feed\n"
            "  PUT /v1/feeds/{id} — update feed\n"
            "  DELETE /v1/feeds/{id} — delete feed\n"
            "  GET /v1/feeds/{id}/entries — list entries\n"
            "  GET /v1/entries — list all entries\n"
            "  GET /v1/categories — list categories\n"
            "  POST /v1/categories — create category"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/v1/me",
    },
    "gitea": {
        "name": "Gitea",
        "category": "developer",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Gitea git forge API (v1). Auth header value format: 'token YOUR_TOKEN'. Key endpoints:\n"
            "  GET /api/v1/repos/search — search repositories\n"
            "  GET /api/v1/repos/{owner}/{repo} — get repo details\n"
            "  GET /api/v1/repos/{owner}/{repo}/issues — list issues\n"
            "  POST /api/v1/repos/{owner}/{repo}/issues — create issue\n"
            "  GET /api/v1/repos/{owner}/{repo}/pulls — list pull requests\n"
            "  GET /api/v1/repos/{owner}/{repo}/commits — list commits"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/v1/version",
    },
    "linkding": {
        "name": "Linkding",
        "category": "productivity",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Linkding bookmark manager API. Auth header value format: 'Token YOUR_TOKEN'. Key endpoints:\n"
            "  GET /api/bookmarks/ — list bookmarks\n"
            "  GET /api/bookmarks/{id}/ — get bookmark\n"
            "  POST /api/bookmarks/ — create bookmark\n"
            "  PUT /api/bookmarks/{id}/ — update bookmark\n"
            "  DELETE /api/bookmarks/{id}/ — delete bookmark\n"
            "  GET /api/tags/ — list tags"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/tags/",
    },
    "homeassistant": {
        "name": "Home Assistant",
        "category": "iot",
        "auth_type": "bearer",
        "description": (
            "Home Assistant smart home API. Key endpoints:\n"
            "  GET /api/ — API status check\n"
            "  GET /api/states — list all entity states\n"
            "  POST /api/states/{entity_id} — update entity state\n"
            "  POST /api/services/{domain}/{service} — call service\n"
            "  GET /api/history/period/{timestamp} — state history\n"
            "  GET /api/config — get configuration"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/",
    },
    "ntfy": {
        "name": "ntfy",
        "category": "communication",
        "auth_type": "none",
        "description": (
            "ntfy push notification service. Key endpoints:\n"
            "  POST /{topic} — send notification\n"
            "  POST / — send JSON notification\n"
            "  GET /{topic}/json?poll=1 — poll for messages"
        ),
        "required_fields": ["base_url"],
        "optional_fields": ["api_key"],
        "test_endpoint": "/",
    },
    "vaultwarden": {
        "name": "Vaultwarden",
        "category": "security",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "Vaultwarden (Bitwarden-compatible) password manager API. Auth header: 'Bearer ACCESS_TOKEN'.\n"
            "  GET /api/ciphers — list vault items\n"
            "  GET /api/ciphers/{id} — get single item\n"
            "  POST /api/ciphers — create vault item\n"
            "  PUT /api/ciphers/{id} — update item\n"
            "  DELETE /api/ciphers/{id} — delete item\n"
            "  GET /api/folders — list folders\n"
            "  POST /api/folders — create folder\n"
            "  GET /api/sends — list Send items\n"
            "  POST /api/sends — create Send"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/status",
    },
    "freshrss": {
        "name": "FreshRSS",
        "category": "rss",
        "auth_type": "header",
        "auth_header": "Authorization",
        "description": (
            "FreshRSS RSS reader (GReader API). Auth header value format: 'GoogleLogin auth=YOUR_TOKEN'.\n"
            "  GET /api/greader.php/reader/api/0/subscription/list?output=json — list feeds\n"
            "  GET /api/greader.php/reader/api/0/stream/contents/feed/{feed_id}?output=json — entries\n"
            "  GET /api/greader.php/reader/api/0/tag/list?output=json — tags\n"
            "  POST /api/greader.php/reader/api/0/edit-tag — mark read/starred\n"
            "  GET /api/greader.php/reader/api/0/unread-count?output=json — unread counts"
        ),
        "required_fields": ["base_url", "api_key"],
        "optional_fields": [],
        "test_endpoint": "/api/greader.php/reader/api/0/user/info?output=json",
    },
}


# ---------------------------------------------------------------------------
# Storage — versioned with backward-compat migration
# ---------------------------------------------------------------------------

def _ensure_data_dir() -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)


def _encrypt_integration_secrets(integrations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    safe: List[Dict[str, Any]] = []
    for item in integrations:
        copy = dict(item)
        api_key = copy.get("api_key", "")
        if api_key and not is_encrypted(str(api_key)):
            copy["api_key"] = encrypt(str(api_key))
        safe.append(copy)
    return safe


def _decrypt_integration_secrets(integrations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    decoded: List[Dict[str, Any]] = []
    for item in integrations:
        copy = dict(item)
        api_key = copy.get("api_key", "")
        if api_key and is_encrypted(str(api_key)):
            copy["api_key"] = decrypt(str(api_key))
        decoded.append(copy)
    return decoded


def _has_plaintext_api_key(integrations: List[Dict[str, Any]]) -> bool:
    return any(
        bool(item.get("api_key")) and not is_encrypted(str(item.get("api_key")))
        for item in integrations
    )


def mask_integration_secret(integration: Dict[str, Any]) -> Dict[str, Any]:
    safe = dict(integration)
    api_key = safe.get("api_key", "")
    if api_key:
        masked = str(api_key)
        if len(masked) > 8:
            safe["api_key"] = f"{masked[:4]}****{masked[-4:]}"
        else:
            safe["api_key"] = f"{masked[:2]}****"
    return safe


def _migrate_integrations_file(path: str) -> None:
    """Upgrade integrations.json from any legacy format to current version."""
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Already current version
    if isinstance(data, dict) and data.get("version") == STORAGE_VERSION:
        return

    # v1: plain list → wrap in versioned container
    if isinstance(data, list):
        migrated: Dict[str, Any] = {
            "version": STORAGE_VERSION,
            "integrations": [],
        }
        for item in data:
            integ = dict(item)
            integ.setdefault("status", "unknown")
            integ.setdefault("last_tested", None)
            integ.setdefault("last_test_result", None)
            migrated["integrations"].append(integ)

        atomic_write_json(path, migrated, indent=2)
        safe_chmod(path, 0o600)
        log.info("Migrated integrations.json from legacy list format to version %d", STORAGE_VERSION)
        return

    # Unknown format — reset to empty
    if isinstance(data, dict) and data.get("version") != STORAGE_VERSION:
        log.warning("Unknown integrations.json version %s, resetting to empty", data.get("version"))
        atomic_write_json(path, {"version": STORAGE_VERSION, "integrations": []}, indent=2)
        safe_chmod(path, 0o600)


def load_integrations() -> List[Dict[str, Any]]:
    """Load all integrations from disk with secrets decrypted and v1 auto-migrated."""
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # v1: plain array — migrate then reload
        if isinstance(data, list):
            _migrate_integrations_file(DATA_FILE)
            return load_integrations()

        # v2+: dict with 'integrations' key
        if isinstance(data, dict):
            integrations = data.get("integrations", [])
            if not isinstance(integrations, list):
                log.error("Invalid integrations array in versioned file")
                return []
            if _has_plaintext_api_key(integrations):
                save_integrations(_decrypt_integration_secrets(integrations))
                return _decrypt_integration_secrets(integrations)
            return _decrypt_integration_secrets(integrations)

        log.error("Invalid integrations file shape")
        return []

    except (json.JSONDecodeError, IOError) as exc:
        log.error("Failed to load integrations: %s", exc)
        return []


def save_integrations(integrations: List[Dict[str, Any]]) -> None:
    """Persist integrations list to disk with API keys encrypted, wrapped in versioned container."""
    _ensure_data_dir()
    encrypted = _encrypt_integration_secrets(integrations)
    wrapper: Dict[str, Any] = {
        "version": STORAGE_VERSION,
        "integrations": encrypted,
    }
    atomic_write_json(DATA_FILE, wrapper, indent=2)
    safe_chmod(DATA_FILE, 0o600)


def get_integration(integration_id: str) -> Optional[Dict[str, Any]]:
    for item in load_integrations():
        if item.get("id") == integration_id:
            return item
    return None


def add_integration(data: Dict[str, Any]) -> Dict[str, Any]:
    integration: Dict[str, Any] = {}

    preset_key = data.get("preset", "")
    if preset_key and preset_key in INTEGRATION_PRESETS:
        preset = INTEGRATION_PRESETS[preset_key]
        integration.update({
            "preset": preset_key,
            "name": preset.get("name", preset_key),
            "category": preset.get("category", ""),
            "auth_type": preset.get("auth_type", "none"),
            "auth_header": preset.get("auth_header", ""),
            "description": preset.get("description", ""),
            "required_fields": preset.get("required_fields", []),
            "optional_fields": preset.get("optional_fields", []),
            "test_endpoint": preset.get("test_endpoint", "/"),
            "actions": preset.get("actions", []),
            "status": "unknown",
            "last_tested": None,
            "last_test_result": None,
        })

    # Override with user data (user choices take precedence)
    integration.update(data)

    # Defaults for fields not in preset
    integration.setdefault("id", uuid.uuid4().hex[:12])
    integration.setdefault("enabled", True)
    integration.setdefault("auth_type", "none")
    integration.setdefault("auth_header", "")
    integration.setdefault("auth_param", "")
    integration.setdefault("description", "")
    integration.setdefault("api_key", "")
    integration.setdefault("name", "")
    integration.setdefault("base_url", "")
    integration.setdefault("category", "")
    integration.setdefault("status", "unknown")
    integration.setdefault("last_tested", None)
    integration.setdefault("last_test_result", None)

    # Handle Listmonk-style username/password basic auth
    username = data.get("username", integration.get("username", ""))
    password = data.get("password", integration.get("password", ""))
    if username and password and not data.get("api_key"):
        integration["api_key"] = f"{username}:{password}"

    integrations = load_integrations()
    integrations.append(integration)
    save_integrations(integrations)
    return integration


def update_integration(integration_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    integrations = load_integrations()
    for item in integrations:
        if item.get("id") == integration_id:
            data.pop("id", None)

            # Recompute basic auth if username/password changed
            username = data.get("username", item.get("username", ""))
            password = data.get("password", item.get("password", ""))
            if "username" in data or "password" in data:
                if username and password:
                    data["api_key"] = f"{username}:{password}"
                elif "api_key" not in data:
                    data.pop("api_key", None)

            item.update(data)
            item.setdefault("status", "unknown")
            save_integrations(integrations)
            return item
    return None


def delete_integration(integration_id: str) -> bool:
    integrations = load_integrations()
    original_len = len(integrations)
    integrations = [i for i in integrations if i.get("id") != integration_id]
    if len(integrations) < original_len:
        save_integrations(integrations)
        return True
    return False


# ---------------------------------------------------------------------------
# API execution
# ---------------------------------------------------------------------------

def _strip_html_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html)
    return re.sub(r"\s+", " ", text).strip()


def _find_integration(identifier: str) -> Optional[Dict[str, Any]]:
    integrations = load_integrations()
    for item in integrations:
        if item.get("id") == identifier:
            return item
    lower = identifier.lower()
    for item in integrations:
        if item.get("name", "").lower() == lower:
            return item
    return None


async def execute_api_call(
    integration_id: str,
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Any] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    integration = _find_integration(integration_id)
    if not integration:
        return {"error": f"Integration not found: {integration_id}", "exit_code": 1}

    if not integration.get("enabled", True):
        return {"error": f"Integration '{integration.get('name')}' is disabled", "exit_code": 1}

    base_url = integration.get("base_url", "").rstrip("/")
    if not base_url:
        return {"error": "Integration has no base_url configured", "exit_code": 1}

    # Normalize base URL by stripping known path suffixes per preset
    preset = (integration.get("preset") or integration.get("name", "")).lower()
    strip_suffixes = {
        "miniflux": ["/v1"],
        "gitea": ["/api/v1", "/api"],
        "linkding": ["/api"],
        "homeassistant": ["/api"],
        "apollo": ["/api"],
        "hubspot": ["/crm/v3"],
        "pipedrive": ["/v1"],
        "notion": ["/v1"],
        "airtable": ["/v0"],
        "listmonk": ["/api/v1"],
        "openrouter": ["/api/v1"],
        "salesforce": ["/services/data/v57.0"],
        "make": ["/v1"],
        "n8n": ["/api/v1"],
        "zapier": ["/v1"],
        "slack": ["/api"],
        "discord": ["/api/v10"],
        "telegram": [],
        "twilio": ["/2010-04-01"],
        "whatsapp": ["/v17.0"],
        "clickup": ["/api/v2"],
        "trello": ["/1"],
        "asana": ["/api/v1"],
        "tavily": ["/v1"],
        "brave": ["/api/v1"],
        "mailchimp": ["/3.0"],
        "brevo": ["/v3"],
        "sendgrid": ["/v3"],
        "postmark": ["/v1"],
        "mailgun": ["/v3"],
        "supabase": ["/rest/v1", "/auth/v1"],
        "qdrant": ["/v1", "/v0"],
        "chroma": ["/api/v1"],
    }
    for suf in strip_suffixes.get(preset, []):
        if base_url.endswith(suf):
            base_url = base_url[: -len(suf)]
            break

    # Validate path
    if not path.startswith("/"):
        return {"error": "Path must start with /", "exit_code": 1}
    if re.search(r"^https?://", path) or re.search(r"://", path):
        return {"error": "Path must not contain a protocol scheme", "exit_code": 1}

    url = base_url + path
    method = method.upper()

    headers: Dict[str, str] = {}
    if extra_headers:
        headers.update(extra_headers)

    api_key = integration.get("api_key", "")
    username = integration.get("username", "")
    password = integration.get("password", "")
    auth_type = integration.get("auth_type", "none")

    if auth_type == "header" and api_key:
        header_name = integration.get("auth_header") or ""
        if not header_name:
            header_defaults = {
                "miniflux": "X-Auth-Token",
                "linkding": "Authorization",
                "gitea": "Authorization",
                "hunter": "X-Hunter-Key",
                "peopledatalabs": "X-Api-Key",
                "serper": "X-API-KEY",
                "brave": "X-Subscription-Token",
                "brevo": "api-key",
                "postmark": "X-Postmark-Server-Token",
                "whatsapp": "Authorization",
            }
            header_name = header_defaults.get(preset, "Authorization")
        headers[header_name] = api_key
    elif auth_type == "bearer" and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth_type == "query" and api_key:
        if params is None:
            params = {}
        param_name = integration.get("auth_param", "api_key")
        params[param_name] = api_key

    auth = None
    if auth_type == "basic":
        if username and password:
            auth = httpx.BasicAuth(username, password)
        elif api_key and ":" in str(api_key):
            parts = str(api_key).split(":", 1)
            auth = httpx.BasicAuth(parts[0], parts[1])

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=body if body is not None else None,
                headers=headers,
                auth=auth,
            )

        content_type = response.headers.get("content-type", "")
        status = response.status_code

        if "application/json" in content_type:
            try:
                data = response.json()
                formatted = json.dumps(data, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                formatted = response.text
        elif "text/html" in content_type:
            formatted = _strip_html_tags(response.text)
        else:
            formatted = response.text

        if len(formatted) > 12000:
            formatted = formatted[:12000] + "\n... (truncated)"

        output = f"HTTP {status}\n{formatted}"
        return {"output": output, "exit_code": 0} if status < 400 else {"error": output, "exit_code": 1}

    except httpx.TimeoutException:
        return {"error": f"Request to {integration.get('name')} timed out", "exit_code": 1}
    except httpx.RequestError as exc:
        return {"error": f"Request failed: {exc}", "exit_code": 1}
    except Exception as exc:
        log.exception("Unexpected error in execute_api_call")
        return {"error": f"Unexpected error: {exc}", "exit_code": 1}


async def execute_integration_action(
    integration_id: str,
    action_name: str,
    args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a preset-specific action for an integration."""
    integration = _find_integration(integration_id)
    if not integration:
        return {"error": f"Integration not found: {integration_id}", "exit_code": 1}

    preset_key = integration.get("preset", "")
    preset = INTEGRATION_PRESETS.get(preset_key, {})
    actions = preset.get("actions", [])

    action = next((a for a in actions if a.get("name") == action_name), None)
    if not action:
        available = [a.get("name") for a in actions]
        return {
            "error": f"Action '{action_name}' not found for {integration.get('name')}. Available: {', '.join(available) if available else 'none'}",
            "exit_code": 1,
        }

    path = action.get("path", "/")
    method = action.get("method", "GET")
    body_template = action.get("body", {})
    params: Dict[str, Any] = {}

    # Merge args into params/body based on action definition
    if args:
        for key, val in args.items():
            if key in (body_template or {}):
                if body_template is None:
                    body_template = {}
                body_template[key] = val
            else:
                params[key] = val

    return await execute_api_call(
        integration_id=integration_id,
        method=method,
        path=path,
        params=params if params else None,
        body=body_template if body_template else None,
    )


# ---------------------------------------------------------------------------
# Agent integration
# ---------------------------------------------------------------------------

def get_integrations_prompt() -> str:
    """Generate system-prompt text describing all enabled integrations."""
    integrations = load_integrations()
    enabled = [i for i in integrations if i.get("enabled", True)]
    if not enabled:
        return ""

    lines = [
        "You have access to the following external API integrations.\n",
        "Use the `api_call` tool to interact with them. The tool expects:\n",
        "  - integration: the integration name or ID\n",
        "  - method: HTTP method (GET, POST, PUT, DELETE)\n",
        "  - path: API path (must start with /)\n",
        "  - params: optional query parameters\n",
        "  - body: optional JSON body for POST/PUT\n",
        "\nAvailable integrations:\n",
    ]
    for integ in enabled:
        name = integ.get("name", integ.get("id", "unknown"))
        preset_key = integ.get("preset", "")
        preset = INTEGRATION_PRESETS.get(preset_key, {})
        category = preset.get("category", "other")
        cat_label = INTEGRATION_CATEGORIES.get(category, {}).get("label", category)

        lines.append(f"[{cat_label}] {name} (id: {integ['id']})")
        desc = integ.get("description", "")
        if desc:
            lines.append(desc)
        lines.append("")

    return "\n".join(lines)


def get_integration_tools() -> List[Dict[str, Any]]:
    """Generate dynamic tool definitions from enabled integration actions."""
    integrations = load_integrations()
    tools: List[Dict[str, Any]] = []

    for integ in integrations:
        if not integ.get("enabled", True):
            continue

        preset_key = integ.get("preset", "")
        preset = INTEGRATION_PRESETS.get(preset_key, {})
        integ_name = integ.get("name", integ.get("id", "unknown"))
        actions = preset.get("actions", [])

        if not actions:
            continue

        integ_id = integ.get("id", "")
        for action in actions:
            action_name = action.get("name", "")
            tool_name = f"integ_{integ_id}_{action_name}"
            description = (
                f"[{integ_name}] {action.get('description', action_name)}. "
                f"Integration ID: {integ_id}. "
                f"HTTP {action.get('method', 'GET')} {action.get('path', '/')}"
            )
            parameters: Dict[str, Any] = {
                "type": "object",
                "properties": {},
                "required": [],
            }

            for pname, pinfo in (action.get("params") or {}).items():
                param_type = pinfo.get("type", "string") if isinstance(pinfo, dict) else "string"
                param_desc = pinfo.get("description", "") if isinstance(pinfo, dict) else ""
                parameters["properties"][pname] = {
                    "type": param_type,
                    "description": param_desc,
                }

            tools.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": description,
                    "parameters": parameters,
                },
            })

    return tools


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrate_from_settings() -> None:
    """Migrate legacy Miniflux keys from settings.json to integrations."""
    settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "settings.json")
    if not os.path.exists(settings_path):
        return

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    miniflux_url = settings.get("miniflux_url", "")
    miniflux_key = settings.get("miniflux_api_key", "")

    if not miniflux_url or not miniflux_key:
        return

    existing = load_integrations()
    for item in existing:
        if item.get("preset") == "miniflux":
            log.info("Miniflux integration already exists, skipping migration")
            return

    add_integration({
        "preset": "miniflux",
        "base_url": miniflux_url.rstrip("/"),
        "api_key": miniflux_key,
    })

    settings.pop("miniflux_url", None)
    settings.pop("miniflux_api_key", None)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    log.info("Migrated Miniflux integration from settings.json")
