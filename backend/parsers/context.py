"""
Client identification and DB context building.

These functions run before any LLM call — no API key needed.

Responsibilities:
  1. Extract a likely client name from the transcript via regex
  2. Fuzzy-match that name against existing household names in the DB
  3. Build a scoped DB snapshot for the matched household (or a new-client message)

Scoping the context to one household ensures:
  - Other clients' PII never enters the LLM prompt (privacy)
  - Prompt size stays small regardless of firm size (token efficiency)
  - No risk of Claude confusing fields across different households (accuracy)
"""

import re
from difflib import SequenceMatcher
from sqlalchemy.orm import Session

import models


def extract_client_name_hint(transcript: str) -> str | None:
    """
    Regex pre-scan to extract the most likely client name from a transcript.

    Tries patterns in priority order — explicit legal-name statements first,
    then meeting/call context, then generic client references.

    Returns:
        Best-guess name string, or None if no pattern matches.
    """
    patterns = [
        # "His full legal name is actually Benjamin Walter Thompson Jr."
        r'(?:full legal name is(?:\s+actually)?|name is actually)\s+'
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}(?:\s+(?:Jr\.|Sr\.|II|III|IV))?)',

        # "new client prospect, Benjamin Walter"
        r'(?:client prospect|new client)[,\s]+'
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',

        # "meeting with / spoke with / call with <Name>"
        r'(?:meeting with|spoke with|call with)\s+'
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',

        # "client <Name>" / "named <Name>"
        r'(?:client|named?)\s+'
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript)
        if match:
            return match.group(1).strip()
    return None


def find_matching_household(name: str, db: Session) -> int | None:
    """
    Fuzzy-match a candidate name against all household names in the DB.

    Uses SequenceMatcher (difflib) — no embedding needed for low record counts.
    Returns the household ID if best similarity score >= 0.55, else None.
    """
    if not name:
        return None

    households = db.query(models.Household).all()
    best_id, best_score = None, 0.0

    for hh in households:
        score = SequenceMatcher(None, hh.name.lower(), name.lower()).ratio()
        if score > best_score:
            best_id, best_score = hh.id, score

    return best_id if best_score >= 0.55 else None


def build_client_context(household_id: int | None, db: Session) -> str:
    """
    Build a DB snapshot for injection into the LLM prompt, scoped to one household.

    Args:
        household_id: ID of the matched household. Pass None for new clients.
        db: Active SQLAlchemy session.

    Returns:
        A formatted string showing all current field values, member IDs, and
        account IDs for the matched household — or a new-client instruction
        if household_id is None.
    """
    if household_id is None:
        return (
            "No matching household found in the database.\n"
            "Treat this as a NEW CLIENT — use entity_type 'new_household', "
            "'new_member', 'new_account' and set entity_id = null for all changes."
        )

    hh = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not hh:
        return (
            "No matching household found in the database.\n"
            "Treat this as a NEW CLIENT — use entity_type 'new_household', "
            "'new_member', 'new_account' and set entity_id = null for all changes."
        )

    lines = [f"\n┌─ Household id:{hh.id}  ← use for entity_id when entity_type='household'"]
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
        lines.append(f"│  ├─ Member id:{m.id}  ← use for entity_id when entity_type='member'")
        lines.append(f"│  │  name:           {m.first_name} {m.last_name}")
        lines.append(f"│  │  email:          {m.email or '—'}")
        lines.append(f"│  │  phone:          {m.phone or '—'}")
        lines.append(f"│  │  dob:            {m.dob or '—'}")
        lines.append(f"│  │  address:        {m.address or '—'}")
        lines.append(f"│  │  occupation:     {m.occupation or '—'}")
        lines.append(f"│  │  employer:       {m.employer or '—'}")
        lines.append(f"│  │  marital_status: {m.marital_status or '—'}")

    accounts = db.query(models.Account).filter(models.Account.household_id == hh.id).all()
    for a in accounts:
        lines.append(
            f"│  ├─ Account id:{a.id}  ← use for entity_id when entity_type='account'  "
            f"type:{a.account_type}  custodian:{a.custodian or '—'}  value:{a.account_value or '—'}"
        )

    return "\n".join(lines)
