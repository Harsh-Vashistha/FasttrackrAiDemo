"""
Audio parser: transcription via OpenAI Whisper + data extraction via Claude.

Whisper is an optional heavy dependency (requires PyTorch).
Install with: pip install openai-whisper
If not installed, a helpful error is raised when audio transcription is attempted.

Mock mode: when ANTHROPIC_API_KEY is not set in the environment, all Claude calls
return realistic stub responses so the full upload → review workflow can be exercised
without an API key.  The real call path is unchanged once a key is provided.
"""

import json
import os
import re

import anthropic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_key() -> str | None:
    return os.getenv("ANTHROPIC_API_KEY") or None


def _mock_mode() -> bool:
    """Return True when no Anthropic API key is configured."""
    return not _api_key()


def _is_benjamin_transcript(transcription: str) -> bool:
    """Detect the Benjamin Walter Thompson Jr. demo transcript."""
    return "Benjamin Walter Thompson" in transcription or (
        "Benjamin Walter" in transcription and "Dell Technologies" in transcription
    )


# ---------------------------------------------------------------------------
# Hardcoded demo mock — Benjamin Walter Thompson Jr.
# ---------------------------------------------------------------------------

_BENJAMIN_EXTRACTION: dict = {
    "household_name": "Benjamin Walter Thompson Jr.",
    "updates": {
        "annual_income": None,                          # stated as "substantial" — no figure given
        "estimated_liquid_net_worth": None,
        "estimated_total_net_worth": None,
        "risk_tolerance": "Conservative to Moderate",
        "primary_investment_objective": "Retirement & Wealth Preservation",
        "time_horizon": "10–15 years (retirement at age 62–65)",
        "liquidity_needs": "Moderate — constrained by alimony and child support obligations",
    },
    "member_updates": [
        {
            "name": "Benjamin Walter Thompson Jr.",
            "updates": {
                "first_name": "Benjamin",
                "last_name": "Thompson",
                "dob": "December 3 (age 51)",
                "phone": "512-555-3847",
                "email": "BenjaminWalter.atx@gmail.com",
                "address": "4821 West Lake Drive, Austin, Texas 78746",
                "occupation": "Vice President of Business Development",
                "employer": "Dell Technologies",
                "marital_status": "Divorced",
            },
        }
    ],
    "new_accounts": [
        {
            "member_name": "Benjamin Walter Thompson Jr.",
            "account_type": "401K",
            "custodian": None,
            "account_value": None,
        },
        {
            "member_name": "Benjamin Walter Thompson Jr.",
            "account_type": "Individual Stocks Portfolio",
            "custodian": None,
            "account_value": None,
        },
        {
            "member_name": "Benjamin Walter Thompson Jr.",
            "account_type": "Real Estate — Rental Property",
            "custodian": None,
            "account_value": None,
        },
    ],
    "key_insights": [
        "New client: Benjamin Walter Thompson Jr. (VP of Business Development, Dell Technologies). "
        "Referred by divorce attorney Sarah Mitchell for post-divorce wealth restructuring.",

        "Retained ~60% of joint marital assets post-divorce: 401K, individual stocks portfolio, "
        "and real estate investments. Paying substantial alimony and child support that constrains cash flow.",

        "Risk tolerance shifted to Conservative-to-Moderate following divorce — more cautious but "
        "understands need for growth given 10–15 year retirement timeline (targeting age 62–65).",

        "Rental property in downtown Austin generates $2,400/month but client is evaluating a sale "
        "to diversify. Potential career change in 2–3 years (consulting / smaller tech firm) may "
        "significantly alter compensation structure.",

        "Note: Whisper transcribed 'Jack is 51' — this appears to be a mishearing of 'He is 51'. "
        "Confirm age (51) and DOB (December 3) with client at next meeting.",
    ],
    "action_items": [
        "Next meeting scheduled June 10 — review complete financial picture and build comprehensive "
        "post-divorce wealth management strategy.",
        "Model retirement projections for age 62 vs. 65 target scenarios.",
        "Design tax-efficient investment strategy to rebuild retirement savings.",
        "Create 529 or alternative college savings plan for two teenage children.",
        "Update estate planning documents (beneficiaries, will, POA) post-divorce.",
        "Evaluate rental property: sell-to-diversify model vs. continue holding.",
        "Stress-test cash flow impact of alimony + child support on investment capacity.",
        "Prepare contingency plan for potential career/compensation change in 2–3 years.",
    ],
}


# ---------------------------------------------------------------------------
# Generic fallback mock (non-Benjamin transcripts)
# ---------------------------------------------------------------------------

def _generic_mock_extraction(transcription: str, household_name: str | None) -> dict:
    name = household_name or "New Client"
    return {
        "household_name": name,
        "updates": {k: None for k in [
            "annual_income", "estimated_liquid_net_worth", "estimated_total_net_worth",
            "risk_tolerance", "primary_investment_objective", "time_horizon", "liquidity_needs",
        ]},
        "member_updates": [],
        "new_accounts": [],
        "key_insights": [
            "⚠️  MOCK MODE — add ANTHROPIC_API_KEY to backend/.env for real AI extraction.",
            f"Transcript received ({len(transcription.split())} words). Client: {name}.",
        ],
        "action_items": ["Set ANTHROPIC_API_KEY in backend/.env to enable real extraction."],
    }


def _mock_extract_financial_data(transcription: str, household_name: str | None) -> dict:
    if _is_benjamin_transcript(transcription):
        return _BENJAMIN_EXTRACTION
    return _generic_mock_extraction(transcription, household_name)


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe_audio(file_path: str) -> str:
    """Transcribe audio using OpenAI Whisper locally."""
    try:
        import whisper  # lazy import — heavy dependency
    except ImportError:
        raise RuntimeError(
            "openai-whisper is not installed. Run: pip install openai-whisper\n"
            "Note: This also requires PyTorch. See https://pytorch.org/get-started/"
        )
    model = whisper.load_model("base")
    result = model.transcribe(file_path)
    return result["text"]


# ---------------------------------------------------------------------------
# Financial data extraction
# ---------------------------------------------------------------------------

def extract_financial_data(transcription: str, household_name: str = None) -> dict:
    """
    Extract structured financial data from a transcription using Claude.
    Falls back to a mock response when ANTHROPIC_API_KEY is not configured.
    """
    if _mock_mode():
        return _mock_extract_financial_data(transcription, household_name)

    client = anthropic.Anthropic(api_key=_api_key())

    household_context = (
        f"The conversation is about the household/client named: {household_name}.\n"
        if household_name
        else ""
    )

    prompt = f"""You are analyzing a conversation between a wealth manager and their client.
{household_context}
Conversation transcript:
{transcription}

Extract any financial information mentioned. Return a JSON object with these fields (use null for not mentioned):
{{
    "household_name": "string or null",
    "updates": {{
        "annual_income": "number or null",
        "estimated_liquid_net_worth": "number or null",
        "estimated_total_net_worth": "number or null",
        "risk_tolerance": "string or null",
        "primary_investment_objective": "string or null",
        "time_horizon": "string or null",
        "liquidity_needs": "string or null"
    }},
    "member_updates": [
        {{
            "name": "string",
            "updates": {{}}
        }}
    ],
    "new_accounts": [
        {{
            "member_name": "string",
            "account_type": "string",
            "custodian": "string or null",
            "account_value": "number or null"
        }}
    ],
    "key_insights": ["string array of important points from the conversation"],
    "action_items": ["string array of follow-up actions mentioned"]
}}

Return only valid JSON, no other text."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text
    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, IndexError, AttributeError):
        return {
            "raw_response": raw_text,
            "key_insights": [],
            "action_items": [],
        }
