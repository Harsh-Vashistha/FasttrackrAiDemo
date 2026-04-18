"""
Review Agent — uses Claude to propose field-level DB changes from a transcript,
and to revise individual rejected changes based on reviewer feedback.

Mock mode: when ANTHROPIC_API_KEY is not set, all functions return realistic stub
responses so the review queue workflow is fully exercisable without an API key.
"""

import json
import os
import re
from difflib import SequenceMatcher

import anthropic
from sqlalchemy.orm import Session

import models


# ---------------------------------------------------------------------------
# Key / mock helpers
# ---------------------------------------------------------------------------

def _api_key() -> str | None:
    return os.getenv("ANTHROPIC_API_KEY") or None


def _mock_mode() -> bool:
    return not _api_key()


def _is_benjamin_transcript(transcript: str) -> bool:
    return "Benjamin Walter Thompson" in transcript or (
        "Benjamin Walter" in transcript and "Dell Technologies" in transcript
    )


def _find_matching_household(name: str, db: Session):
    """Fuzzy-match a name against existing households."""
    households = db.query(models.Household).all()
    best_id, best_score = None, 0.0
    for hh in households:
        score = SequenceMatcher(None, hh.name.lower(), name.lower()).ratio()
        if score > best_score:
            best_id, best_score = hh.id, score
    return best_id if best_score >= 0.55 else None


# ---------------------------------------------------------------------------
# Hardcoded demo mock — Benjamin Walter Thompson Jr.
# ---------------------------------------------------------------------------

def _benjamin_proposed_changes(matched_id, is_new: bool) -> list:
    et_hh  = "new_household" if is_new else "household"
    et_mem = "new_member"    if is_new else "member"
    et_acc = "new_account"   if is_new else "account"
    lbl    = "Benjamin Walter Thompson Jr."

    return [
        # ── Household fields ─────────────────────────────────────────────
        {
            "entity_type": et_hh, "entity_id": matched_id, "entity_label": lbl,
            "field_name": "name",
            "proposed_value": "Benjamin Walter Thompson Jr.",
            "source_quote": "His full legal name is actually Benjamin Walter Thompson Jr.",
            "confidence": 0.99,
            "reasoning": "Full legal name explicitly stated by wealth manager.",
        },
        {
            "entity_type": et_hh, "entity_id": matched_id, "entity_label": lbl,
            "field_name": "risk_tolerance",
            "proposed_value": "Conservative to Moderate",
            "source_quote": "Risk tolerance is conservative to moderate. The divorce made him more cautious about aggressive investments.",
            "confidence": 0.97,
            "reasoning": "Risk tolerance explicitly stated and contextualised with post-divorce caution.",
        },
        {
            "entity_type": et_hh, "entity_id": matched_id, "entity_label": lbl,
            "field_name": "primary_investment_objective",
            "proposed_value": "Retirement & Wealth Preservation",
            "source_quote": "He's targeting retirement at 62-65, wanting to ensure he can maintain his lifestyle while meeting his ongoing family obligations.",
            "confidence": 0.93,
            "reasoning": "Primary goal is retirement income while preserving post-divorce lifestyle.",
        },
        {
            "entity_type": et_hh, "entity_id": matched_id, "entity_label": lbl,
            "field_name": "time_horizon",
            "proposed_value": "10–15 years (retirement at age 62–65)",
            "source_quote": "He's targeting retirement at 62-65",
            "confidence": 0.95,
            "reasoning": "Client is 51 and targeting retirement at 62–65, giving a 10–15 year horizon.",
        },
        {
            "entity_type": et_hh, "entity_id": matched_id, "entity_label": lbl,
            "field_name": "source_of_funds",
            "proposed_value": "Employment (Dell Technologies) + rental income ($2,400/mo)",
            "source_quote": "He owns a small rental property in downtown Austin that generates about $2,400 monthly income",
            "confidence": 0.91,
            "reasoning": "Two income sources identified: W-2 employment and rental property.",
        },
        {
            "entity_type": et_hh, "entity_id": matched_id, "entity_label": lbl,
            "field_name": "primary_use_of_funds",
            "proposed_value": "Retirement savings, college planning, estate planning, cash flow optimisation",
            "source_quote": "Current financial priorities include rebuilding retirement savings post divorce. Tax-efficient investment strategies. College planning for two teenagers. Estate planning updates. Cash flow optimization given alimony payments.",
            "confidence": 0.97,
            "reasoning": "Five explicit financial priorities enumerated by the advisor.",
        },
        {
            "entity_type": et_hh, "entity_id": matched_id, "entity_label": lbl,
            "field_name": "liquidity_needs",
            "proposed_value": "Moderate — constrained by alimony and child support",
            "source_quote": "he's paying substantial alimony and child support, which impacts his cash flow significantly",
            "confidence": 0.90,
            "reasoning": "Ongoing obligations reduce available liquidity; moderate need implied.",
        },
        {
            "entity_type": et_hh, "entity_id": matched_id, "entity_label": lbl,
            "field_name": "account_decision_making",
            "proposed_value": "Individual",
            "source_quote": "Completed my first meeting with a new client prospect, Benjamin Walter.",
            "confidence": 0.80,
            "reasoning": "No joint account holder mentioned; individual decision-making assumed.",
        },

        # ── Member fields ────────────────────────────────────────────────
        {
            "entity_type": et_mem, "entity_id": None, "entity_label": lbl,
            "field_name": "first_name",
            "proposed_value": "Benjamin",
            "source_quote": "His full legal name is actually Benjamin Walter Thompson Jr.",
            "confidence": 0.99,
            "reasoning": "First name explicitly stated.",
        },
        {
            "entity_type": et_mem, "entity_id": None, "entity_label": lbl,
            "field_name": "last_name",
            "proposed_value": "Thompson",
            "source_quote": "His full legal name is actually Benjamin Walter Thompson Jr.",
            "confidence": 0.99,
            "reasoning": "Last name explicitly stated.",
        },
        {
            "entity_type": et_mem, "entity_id": None, "entity_label": lbl,
            "field_name": "dob",
            "proposed_value": "December 3 (age 51)",
            "source_quote": "Jack is 51 years old, with his birthday falling on December 3.",
            "confidence": 0.72,
            "reasoning": "Age and birthday stated but Whisper transcribed 'Jack' — likely a mishearing of 'He'. Verify with client.",
        },
        {
            "entity_type": et_mem, "entity_id": None, "entity_label": lbl,
            "field_name": "phone",
            "proposed_value": "512-555-3847",
            "source_quote": "His main phone is 5125553847, and he's fine with calls during business hours.",
            "confidence": 0.96,
            "reasoning": "Phone number explicitly stated as continuous digits; formatted to standard.",
        },
        {
            "entity_type": et_mem, "entity_id": None, "entity_label": lbl,
            "field_name": "email",
            "proposed_value": "BenjaminWalter.atx@gmail.com",
            "source_quote": "he prefers his personal Gmail, BenjaminWalter.atx.atgmail.com for our communications",
            "confidence": 0.84,
            "reasoning": "Personal Gmail preferred for advisor communications. Whisper may have garbled '@gmail.com' as 'atgmail.com' — verify.",
        },
        {
            "entity_type": et_mem, "entity_id": None, "entity_label": lbl,
            "field_name": "address",
            "proposed_value": "4821 West Lake Drive, Austin, Texas 78746",
            "source_quote": "Currently residing in Austin, Texas at 48-21 West Lake Drive, Austin, Texas 7-8-7-4-6.",
            "confidence": 0.85,
            "reasoning": "Address stated. Whisper hyphenated the numbers — parsed to 4821 and ZIP 78746.",
        },
        {
            "entity_type": et_mem, "entity_id": None, "entity_label": lbl,
            "field_name": "occupation",
            "proposed_value": "Vice President of Business Development",
            "source_quote": "Benjamin is a vice president of business development at Dell Technologies",
            "confidence": 0.99,
            "reasoning": "Job title explicitly stated.",
        },
        {
            "entity_type": et_mem, "entity_id": None, "entity_label": lbl,
            "field_name": "employer",
            "proposed_value": "Dell Technologies",
            "source_quote": "Benjamin is a vice president of business development at Dell Technologies, where he's worked for the past 12 years.",
            "confidence": 0.99,
            "reasoning": "Current employer and tenure explicitly stated.",
        },
        {
            "entity_type": et_mem, "entity_id": None, "entity_label": lbl,
            "field_name": "marital_status",
            "proposed_value": "Divorced",
            "source_quote": "He's divorced as of two years ago, though he mentioned the settlement was amicable.",
            "confidence": 0.99,
            "reasoning": "Marital status explicitly stated.",
        },

        # ── Account fields ───────────────────────────────────────────────
        {
            "entity_type": et_acc, "entity_id": None, "entity_label": "401K — Dell Technologies",
            "field_name": "account_type",
            "proposed_value": "401K",
            "source_quote": "He kept about 60% of their joint assets, including his 401K",
            "confidence": 0.96,
            "reasoning": "401K explicitly mentioned as a retained post-divorce asset.",
        },
        {
            "entity_type": et_acc, "entity_id": None, "entity_label": "Individual Stocks Portfolio",
            "field_name": "account_type",
            "proposed_value": "Individual Stocks",
            "source_quote": "a portfolio of individual stocks",
            "confidence": 0.93,
            "reasoning": "Individual stocks portfolio explicitly stated as a retained asset.",
        },
        {
            "entity_type": et_acc, "entity_id": None, "entity_label": "Rental Property — Downtown Austin",
            "field_name": "account_type",
            "proposed_value": "Real Estate — Rental Property",
            "source_quote": "He owns a small rental property in downtown Austin that generates about $2,400 monthly income",
            "confidence": 0.95,
            "reasoning": "Rental property with known monthly income explicitly mentioned. Client considering selling.",
        },
    ]


def _benjamin_mock_agent(db: Session) -> dict:
    matched_id = _find_matching_household("Benjamin Walter Thompson Jr.", db)
    is_new = matched_id is None
    return {
        "matched_household_id": matched_id,
        "proposed_household_name": "Benjamin Walter Thompson Jr.",
        "is_new_client": str(is_new).lower(),
        "agent_summary": (
            "New client: Benjamin Walter Thompson Jr., VP of Business Development at Dell Technologies (Austin, TX). "
            "Post-divorce financial restructuring — retained ~60% of joint assets (401K, stocks, real estate). "
            "Risk tolerance Conservative-to-Moderate; 10–15 year retirement horizon targeting age 62–65. "
            "Cash flow constrained by alimony and child support. "
            "⚠️ Note: Whisper transcribed 'Jack is 51' — likely a mishearing; verify age with client."
        ),
        "proposed_changes": _benjamin_proposed_changes(matched_id, is_new),
    }


# ---------------------------------------------------------------------------
# Generic fallback mock (non-Benjamin transcripts)
# ---------------------------------------------------------------------------

def _generic_mock_agent(transcript: str, db: Session) -> dict:
    patterns = [
        r'(?:client|prospect|meeting with|named?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
    ]
    name = "New Client"
    for pat in patterns:
        m = re.search(pat, transcript)
        if m:
            name = m.group(1).strip()
            break

    matched_id = _find_matching_household(name, db)
    is_new = matched_id is None
    return {
        "matched_household_id": matched_id,
        "proposed_household_name": name,
        "is_new_client": str(is_new).lower(),
        "agent_summary": (
            f"⚠️  MOCK MODE — ANTHROPIC_API_KEY not set. "
            f"Detected client: '{name}'. Add API key to backend/.env for real AI analysis."
        ),
        "proposed_changes": [],
    }


def _mock_run_agent(transcript: str, db: Session) -> dict:
    if _is_benjamin_transcript(transcript):
        return _benjamin_mock_agent(db)
    return _generic_mock_agent(transcript, db)


def _mock_revise_single_change(
    change: "models.ProposedChange",
    reviewer_feedback: str,
) -> dict:
    """
    Simulated per-change revision for the Benjamin demo.
    Gives a contextually relevant response based on the field being revised.
    """
    field = change.field_name
    feedback_lower = reviewer_feedback.lower()

    # Field-aware revision responses
    if field == "dob":
        return {
            "action": "revise",
            "revised_value": "December 3, 1974 (age 51)",
            "revised_source_quote": "Jack is 51 years old, with his birthday falling on December 3.",
            "revised_confidence": 0.78,
            "agent_response": (
                "Agreed — Whisper transcribed 'Jack' but context clearly refers to Benjamin. "
                "Revised to include estimated birth year (1974) based on age 51 at time of meeting. "
                "Recommend verifying exact year with client."
            ),
        }
    if field == "email":
        return {
            "action": "revise",
            "revised_value": "BenjaminWalter.atx@gmail.com",
            "revised_source_quote": "he prefers his personal Gmail, BenjaminWalter.atx.atgmail.com for our communications",
            "revised_confidence": 0.80,
            "agent_response": (
                "Whisper likely misheard '@gmail.com' as 'atgmail.com'. "
                "Revised to BenjaminWalter.atx@gmail.com — please confirm with client at next meeting."
            ),
        }
    if field == "address":
        return {
            "action": "revise",
            "revised_value": "4821 West Lake Drive, Austin, TX 78746",
            "revised_source_quote": "Currently residing in Austin, Texas at 48-21 West Lake Drive, Austin, Texas 7-8-7-4-6.",
            "revised_confidence": 0.88,
            "agent_response": (
                "Whisper hyphenated '4821' as '48-21' and '78746' as '7-8-7-4-6'. "
                "Revised to standard postal format. Recommend verifying against a signed client form."
            ),
        }
    if field in ("risk_tolerance",):
        if "moderate" in feedback_lower and "conservative" not in feedback_lower:
            return {
                "action": "revise",
                "revised_value": "Moderate",
                "revised_source_quote": "though he understands the need for growth given his timeline to retirement",
                "revised_confidence": 0.82,
                "agent_response": (
                    "Revised to 'Moderate' based on your feedback. "
                    "The transcript does say 'conservative to moderate' but the growth acknowledgement "
                    "could indicate the advisor interpreted the net stance as Moderate. Confirm with client."
                ),
            }

    # Generic revision incorporating reviewer's feedback
    original_value = change.revised_value or change.proposed_value or ""
    return {
        "action": "revise",
        "revised_value": reviewer_feedback[:120] if len(reviewer_feedback) < 120 else original_value,
        "revised_source_quote": change.revised_source_quote or change.source_quote,
        "revised_confidence": 0.70,
        "agent_response": (
            f"Thank you for the correction. I've updated '{field}' based on your feedback. "
            f"The transcript for this field reads: \"{(change.source_quote or '')[:100]}\". "
            f"If my revision is still not accurate, please provide the correct value directly."
        ),
    }


# ---------------------------------------------------------------------------
# Code fence stripper
# ---------------------------------------------------------------------------

def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ``` or ``` ... ```) from a string."""
    text = text.strip()
    # Remove opening fence with optional language tag
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    # Remove closing fence
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _build_db_context(db: Session) -> str:
    """
    Build a full snapshot of the current DB state for injection into the LLM prompt.

    Why inject the full state (not just names)?
    - Claude needs current field values to avoid proposing unchanged data
    - Claude needs member/account IDs to generate correct entity_id for updates
    - Claude needs to see what is NULL vs populated to know what still needs filling
    """
    households = db.query(models.Household).all()
    if not households:
        return "DATABASE IS EMPTY — no existing households. All clients in this transcript are new."

    lines = []
    for hh in households:
        lines.append(f"\n┌─ Household  id:{hh.id}")
        lines.append(f"│  name:                        {hh.name}")
        lines.append(f"│  risk_tolerance:               {hh.risk_tolerance or '—'}")
        lines.append(f"│  annual_income:                {hh.annual_income or '—'}")
        lines.append(f"│  estimated_total_net_worth:    {hh.estimated_total_net_worth or '—'}")
        lines.append(f"│  estimated_liquid_net_worth:   {hh.estimated_liquid_net_worth or '—'}")
        lines.append(f"│  tax_bracket:                  {hh.tax_bracket or '—'}")
        lines.append(f"│  primary_investment_objective: {hh.primary_investment_objective or '—'}")
        lines.append(f"│  time_horizon:                 {hh.time_horizon or '—'}")
        lines.append(f"│  source_of_funds:              {hh.source_of_funds or '—'}")
        lines.append(f"│  primary_use_of_funds:         {hh.primary_use_of_funds or '—'}")
        lines.append(f"│  liquidity_needs:              {hh.liquidity_needs or '—'}")
        lines.append(f"│  account_decision_making:      {hh.account_decision_making or '—'}")

        members = db.query(models.Member).filter(models.Member.household_id == hh.id).all()
        for m in members:
            lines.append(f"│")
            lines.append(f"│  ├─ Member  id:{m.id}  name: {m.first_name} {m.last_name}")
            lines.append(f"│  │  email:          {m.email or '—'}")
            lines.append(f"│  │  phone:          {m.phone or '—'}")
            lines.append(f"│  │  dob:            {m.dob or '—'}")
            lines.append(f"│  │  address:        {m.address or '—'}")
            lines.append(f"│  │  occupation:     {m.occupation or '—'}")
            lines.append(f"│  │  employer:       {m.employer or '—'}")
            lines.append(f"│  │  marital_status: {m.marital_status or '—'}")

        accounts = db.query(models.Account).filter(models.Account.household_id == hh.id).all()
        for a in accounts:
            lines.append(f"│  ├─ Account  id:{a.id}  type:{a.account_type}  custodian:{a.custodian or '—'}  value:{a.account_value or '—'}")

    return "\n".join(lines)


# ── Prompt constants ─────────────────────────────────────────────────────────

_SCHEMA_REFERENCE = """
## Database Schema — Exact Field Names and Types

### HOUSEHOLD  (one record per client family or individual)
  name                        String   Full legal household name.       e.g. "John and Jane Smith"
  annual_income               Float    Total gross annual income (USD). e.g. 175000.0
  estimated_total_net_worth   Float    All assets minus liabilities.    e.g. 2500000.0
  estimated_liquid_net_worth  Float    Liquid/accessible assets only.   e.g. 800000.0
  tax_bracket                 String   Federal tax bracket.             e.g. "32%", "24%"
  risk_tolerance              String   Investment risk posture.         e.g. "Conservative", "Moderate", "Aggressive", "Conservative to Moderate"
  primary_investment_objective String  Main goal for the portfolio.     e.g. "Retirement", "Growth", "Income", "Capital Preservation"
  time_horizon                String   Investment timeline.             e.g. "10–15 years", "Long-term", "Short-term (under 5 years)"
  source_of_funds             String   Where money comes from.         e.g. "Employment", "Business sale", "Inheritance", "Rental income"
  primary_use_of_funds        String   What money will be used for.    e.g. "Retirement, College planning, Estate planning"
  liquidity_needs             String   How much cash access needed.    e.g. "Low", "Moderate", "High — funds needed within 2 years"
  account_decision_making     String   Who decides on accounts.        e.g. "Individual", "Joint", "Trust", "POA"

### MEMBER  (one record per person in the household)
  first_name                  String   Legal first name.   (REQUIRED)
  last_name                   String   Legal last name.    (REQUIRED)
  dob                         String   Date of birth.                   e.g. "1974-12-03", "December 3, 1974"
  phone                       String   Primary phone number.            e.g. "512-555-3847"
  email                       String   Email address.                   e.g. "john.doe@gmail.com"
  address                     String   Full mailing address.            e.g. "4821 West Lake Dr, Austin TX 78746"
  ssn                         String   Social security — ONLY if clearly and fully spoken aloud
  occupation                  String   Current job title.               e.g. "Vice President of Business Development"
  employer                    String   Current company.                 e.g. "Dell Technologies"
  marital_status              String   "Single" | "Married" | "Divorced" | "Widowed" | "Separated"
  drivers_license_no          String   DL number — only if explicitly stated

### ACCOUNT  (one record per financial account)
  account_type                String   Account category.  e.g. "401K", "Roth IRA", "Individual Stocks", "Real Estate", "529 Plan", "Brokerage"
  custodian                   String   Broker or bank.    e.g. "Fidelity", "Vanguard", "Schwab", "Chase"
  account_number              String   Account identifier — only if explicitly stated
  account_value               Float    Current market value in USD — only if explicitly stated as a number
  ownership_type              String   "Individual" | "Joint" | "Trust"
"""

_ENTITY_RULES = """
## Entity Resolution Rules

### Matching existing clients
If the transcript clearly refers to someone already in the database above:
  - entity_type = "household"  → use entity_id = <household.id from DB>
  - entity_type = "member"     → use entity_id = <member.id from DB>
  - entity_type = "account"    → use entity_id = <account.id from DB>
  CRITICAL: Only propose a change if the new value DIFFERS from what is already in the DB.
  Do NOT propose setting risk_tolerance = "Moderate" if it already says "Moderate" in the DB snapshot above.

### Creating new clients
If the person is NOT in the database:
  - entity_type = "new_household"  entity_id = null
  - entity_type = "new_member"     entity_id = null
  - entity_type = "new_account"    entity_id = null

### Grouping rule — IMPORTANT
All field changes for the same person or account MUST share the exact same entity_label.
Example: every field for "Benjamin Thompson" must have entity_label = "Benjamin Thompson".
This is how the apply step knows to create one Member record from multiple field proposals.

### Do NOT propose:
  - Fields whose current DB value already matches what the transcript says
  - Fields with no clear transcript support
  - SSN unless spoken out digit-by-digit and unambiguously clear
  - Dollar amounts stated as vague ("substantial", "significant") — these are null
"""

_WHISPER_AWARENESS = """
## Whisper Transcription Artifacts to Watch For
The transcript was generated by OpenAI Whisper, which has known error patterns:
  - Numbers spoken digit-by-digit get hyphenated:  "78746" → "7-8-7-4-6",  "4821" → "48-21"
  - Email domains get phonetically mangled:         "@gmail.com" → "atgmail.com"
  - Names can be misheard when the speaker changes topic mid-sentence
  - Phone numbers run together may be split inconsistently

When you see these patterns:
  - Propose your best-interpretation value  (e.g. fix "7-8-7-4-6" → "78746")
  - Set confidence ≤ 0.85 for any value that shows clear Whisper artifacts
  - Explain the artifact in the reasoning field so the reviewer knows to verify
"""

_FEW_SHOT = """
## Example Output (for a different client — illustrates correct format)

Transcript snippet: "Sarah Johnson called. She's moved to 230 Park Avenue, New York. Still at Morgan Stanley, risk appetite remains moderate."

Assuming Sarah Johnson is already in the DB as Household id:7, Member id:12 with address currently null:
{
  "matched_household_id": 7,
  "proposed_household_name": "Sarah Johnson",
  "is_new_client": "false",
  "agent_summary": "Existing client Sarah Johnson provided an updated address and confirmed her role at Morgan Stanley. Risk tolerance unchanged.",
  "proposed_changes": [
    {
      "entity_type": "member",
      "entity_id": 12,
      "entity_label": "Sarah Johnson",
      "field_name": "address",
      "proposed_value": "230 Park Avenue, New York",
      "source_quote": "She's moved to 230 Park Avenue, New York.",
      "confidence": 0.96,
      "reasoning": "Address change explicitly stated. Previous address was null, so this is new information."
    }
  ]
}
Note: risk_tolerance was NOT proposed because it already matches the DB value.
Note: employer was NOT proposed because it already matches the DB value.
"""


def run_agent(transcript: str, db: Session) -> dict:
    """
    Analyze a transcript against the current DB state and propose field-level changes.

    Context strategy (why each piece is injected):
      1. Full DB snapshot   — so Claude knows current field values and can avoid re-proposing
                              unchanged data, and can find correct entity IDs for updates
      2. Typed schema       — so Claude uses exact field names and understands valid value formats
      3. Entity rules       — so Claude correctly decides new_household vs household, etc.
      4. Whisper awareness  — so Claude flags artifacts and doesn't blindly trust mishearings
      5. Few-shot example   — so Claude understands the expected output structure

    Falls back to a mock response when ANTHROPIC_API_KEY is not configured.
    """
    if _mock_mode():
        return _mock_run_agent(transcript, db)

    db_context = _build_db_context(db)

    prompt = f"""You are a financial CRM assistant for a wealth management firm.
Your job is to analyze advisor meeting notes and propose precise, field-level database changes.

{_SCHEMA_REFERENCE}

{_ENTITY_RULES}

{_WHISPER_AWARENESS}

{_FEW_SHOT}

## Current Database State (read carefully before proposing changes)
{db_context}

## Transcript to Analyze
{transcript}

## Your Output
Return ONLY a valid JSON object — no markdown, no explanation, no code fences.
{{
  "matched_household_id": <integer id from DB above, or null if new client>,
  "proposed_household_name": "<full name extracted from transcript>",
  "is_new_client": "<'true' or 'false' as string>",
  "agent_summary": "<2-3 sentences: who is this client, did you match them to existing DB, key financial facts, any Whisper artifacts to flag>",
  "proposed_changes": [
    {{
      "entity_type": "<household|member|account|new_household|new_member|new_account>",
      "entity_id": <integer or null>,
      "entity_label": "<consistent human-readable label for this entity>",
      "field_name": "<exact field name from schema above>",
      "proposed_value": "<string value>",
      "source_quote": "<verbatim words from transcript supporting this>",
      "confidence": <0.0–1.0>,
      "reasoning": "<one sentence: why this value, any caveats or Whisper corrections>"
    }}
  ]
}}"""

    client = anthropic.Anthropic(api_key=_api_key())
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text
    cleaned = _strip_code_fences(raw_text)

    try:
        result = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        result = {
            "matched_household_id": None,
            "proposed_household_name": "Unknown",
            "is_new_client": "true",
            "agent_summary": "Agent could not parse the transcript.",
            "proposed_changes": [],
        }

    result.setdefault("matched_household_id", None)
    result.setdefault("proposed_household_name", "Unknown")
    result.setdefault("is_new_client", "true")
    result.setdefault("agent_summary", "")
    result.setdefault("proposed_changes", [])
    return result


def revise_single_change(
    transcript: str,
    change: models.ProposedChange,
    reviewer_feedback: str,
) -> dict:
    """
    Ask Claude to revise or dismiss a single rejected proposed change.

    Returns a dict with keys:
        action ("revise" or "dismiss"),
        revised_value, revised_source_quote, revised_confidence, agent_response

    Falls back to a mock response when ANTHROPIC_API_KEY is not configured.
    """
    if _mock_mode():
        return _mock_revise_single_change(change, reviewer_feedback)

    # Rebuild conversation history so Claude has full context of this back-and-forth
    try:
        history = json.loads(change.conversation_history or "[]")
    except (json.JSONDecodeError, TypeError):
        history = []

    history_text = ""
    if history:
        lines = ["\n## Full Conversation History for This Change"]
        for entry in history:
            role = entry.get("role", "unknown")
            if role == "reviewer":
                lines.append(f"  Reviewer [{entry.get('action','feedback')}]: {entry.get('feedback') or entry.get('action','')}")
            elif role == "agent":
                lines.append(f"  Agent [{entry.get('action','response')}]: {entry.get('agent_response','')}")
        history_text = "\n".join(lines)

    # Use revised values if this change has already gone through one round
    current_proposed = change.revised_value or change.proposed_value or ""
    current_quote    = change.revised_source_quote or change.source_quote or "N/A"

    prompt = f"""You are a financial CRM assistant for a wealth management firm.
A human reviewer rejected one of your proposed database changes and gave feedback.
Your job is to re-examine the original transcript and either revise your proposal or agree it should be dismissed.

{_SCHEMA_REFERENCE}

{_WHISPER_AWARENESS}

## Original Transcript
{transcript}

## The Change Being Disputed
- Entity:          {change.entity_label or change.entity_type}
- Field:           {change.field_name}
- Current DB value (before any change): {change.current_value or '— (null/empty)'}
- Your last proposed value:  {current_proposed}
- Your last source quote:    "{current_quote}"
- Your original reasoning:   {change.reasoning or 'N/A'}
{history_text}

## Latest Reviewer Feedback
"{reviewer_feedback}"

## Your Task
Re-read the transcript carefully in light of the reviewer's feedback. Then decide:

  "revise"  — You found a better value OR the reviewer told you the correct one.
              Use this even if the reviewer just told you the right answer directly.

  "dismiss" — The reviewer is correct that no change should be made to this field,
              OR the transcript genuinely does not support any value for this field.

Return ONLY a valid JSON object — no markdown, no explanation:
{{
  "action": "revise" | "dismiss",
  "revised_value": "<corrected value as string, or null if dismissing>",
  "revised_source_quote": "<the transcript passage that now supports this, or null if dismissing>",
  "revised_confidence": <0.0–1.0, or null if dismissing>,
  "agent_response": "<1-2 sentences: what you changed and why, or why you agreed to dismiss>"
}}"""

    client = anthropic.Anthropic(api_key=_api_key())
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text
    cleaned = _strip_code_fences(raw_text)

    try:
        result = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        result = {
            "action": "dismiss",
            "revised_value": None,
            "revised_source_quote": None,
            "revised_confidence": None,
            "agent_response": "Agent failed to parse response. Dismissing change.",
        }

    result.setdefault("action", "dismiss")
    result.setdefault("revised_value", None)
    result.setdefault("revised_source_quote", None)
    result.setdefault("revised_confidence", None)
    result.setdefault("agent_response", "")

    return result
