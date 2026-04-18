"""
CSV / Excel parser for the FasttrackrAI financial advisor system.

Supports variable column names through fuzzy (case-insensitive, partial)
column matching.  Returns a list of household dicts ready to be persisted.
"""

import re
from typing import Any, Optional
import pandas as pd


# ---------------------------------------------------------------------------
# Money / value helpers
# ---------------------------------------------------------------------------

def _parse_money(value: Any) -> Optional[float]:
    """Convert "$1,000,000" or "1000000" to a float.  Returns None on failure."""
    if value is None:
        return None
    s = str(value).strip()
    if s in ("", "nan", "NaN", "N/A", "n/a"):
        return None
    # Strip currency symbols, spaces, commas
    s = re.sub(r"[\$,\s]", "", s)
    # Remove trailing % if present (for percentages used as money – unlikely, but safe)
    s = s.rstrip("%")
    try:
        return float(s)
    except ValueError:
        return None


def _str_or_none(value: Any) -> Optional[str]:
    """Return a clean string or None for empty / NaN values."""
    if value is None:
        return None
    s = str(value).strip()
    if s in ("", "nan", "NaN", "N/A", "n/a", "None"):
        return None
    return s


# ---------------------------------------------------------------------------
# Fuzzy column matching
# ---------------------------------------------------------------------------

def _fuzzy_find(columns: list[str], *candidates: str) -> Optional[str]:
    """
    Find a column name from the file that best matches any of the candidate keywords.
    Returns None if nothing matches.

    WHY THIS EXISTS
    ───────────────
    Different clients send CSV files with different column headers for the same
    logical field.  E.g. the "phone number" column might arrive as:
        "Phone", "Phone #", "Phone Number", "Client Phone", "phone number"
    This function lets us describe the field with multiple candidate strings and
    find whichever variant the file actually used.

    ──────────────────────────────────────────────────────────────────────────
    INPUT
    ──────────────────────────────────────────────────────────────────────────
    columns    : list[str]  — the actual column headers found in the uploaded file
                             e.g. ["Household Name", "firstname", "yearly income",
                                   "bank/custodian", "Phone #", "risk level"]

    *candidates: str        — one or more keywords we want to match against,
                             listed in priority order (first match wins)
                             e.g. "annual income", "income", "yearly income"

    ──────────────────────────────────────────────────────────────────────────
    OUTPUT
    ──────────────────────────────────────────────────────────────────────────
    Returns the ORIGINAL column name (preserving original casing) from `columns`
    that matched, or None if nothing matched.

        _fuzzy_find(["Phone #", "First Name"], "phone", "phone number")
        → "Phone #"   ← the original string from the file, not our candidate

        _fuzzy_find(["First Name", "Annual Income"], "ssn", "social security")
        → None        ← no column contains "ssn" or "social security"

    ──────────────────────────────────────────────────────────────────────────
    HOW THE MATCHING WORKS  (step-by-step with real data)
    ──────────────────────────────────────────────────────────────────────────
    Setup: everything is lowercased so "Phone #" and "phone #" compare equal.

        columns   = ["Household Name", "firstname", "yearly income", "bank/custodian"]
        lower_cols = {
            "household name" : "Household Name",   # key=lower, value=original
            "firstname"      : "firstname",
            "yearly income"  : "yearly income",
            "bank/custodian" : "bank/custodian",
        }

    Call: _fuzzy_find(columns, "annual income", "income", "yearly income")
    Candidates are tried IN ORDER. For each candidate:

      ① candidate = "annual income"  →  cand_lower = "annual income"
         EXACT match?  "annual income" in lower_cols?  → NO
         PARTIAL match?
           "annual income" in "household name"? NO  |  "household name" in "annual income"? NO
           "annual income" in "firstname"?      NO  |  "firstname" in "annual income"?      NO
           "annual income" in "yearly income"?  NO  |  "yearly income" in "annual income"?  NO
           "annual income" in "bank/custodian"? NO  |  "bank/custodian" in "annual income"? NO
         → no match, move to next candidate

      ② candidate = "income"  →  cand_lower = "income"
         EXACT match?  "income" in lower_cols?  → NO
         PARTIAL match?
           "income" in "household name"? NO
           "income" in "firstname"?      NO
           "income" in "yearly income"?  YES! ✓  ("income" is a substring of "yearly income")
         → MATCH FOUND → return lower_cols["yearly income"] = "yearly income"

    The function never reaches candidate ③ ("yearly income") because ② matched first.

    ──────────────────────────────────────────────────────────────────────────
    THE TWO-WAY SUBSTRING CHECK  →  `cand_lower in lc  or  lc in cand_lower`
    ──────────────────────────────────────────────────────────────────────────
    We check BOTH directions because the file column and our candidate can be
    subsets of each other in either direction:

      Direction A — candidate is shorter (contained IN the column):
        candidate  = "income"         ← short keyword
        column     = "yearly income"  ← longer column header
        "income" in "yearly income"   → True  ✓

      Direction B — column is shorter (contained IN the candidate):
        candidate  = "phone number"   ← longer candidate
        column     = "phone"          ← short column header
        "phone" in "phone number"     → True  ✓  (lc in cand_lower)

    Without the reverse check, "phone" would NOT match our candidate "phone number".
    """
    lower_cols = {c.lower(): c for c in columns}
    for candidate in candidates:
        cand_lower = candidate.lower()
        # Exact match first
        if cand_lower in lower_cols:
            return lower_cols[cand_lower]
        # Partial / substring match (both directions – see docstring)
        for lc, orig in lower_cols.items():
            if cand_lower in lc or lc in cand_lower:
                return orig
    return None


def _get(row: pd.Series, columns: list[str], *candidates: str) -> Any:
    """Retrieve a cell value using fuzzy column lookup. Returns None if not found."""
    col = _fuzzy_find(columns, *candidates)
    if col is None:
        return None
    val = row.get(col)
    return None if pd.isna(val) else val


# ---------------------------------------------------------------------------
# Beneficiary helpers
# ---------------------------------------------------------------------------

def _extract_beneficiaries(row: pd.Series, columns: list[str]) -> list[dict]:
    """Extract up to 5 beneficiaries from columns like 'Beneficiary 1 Name', etc."""
    beneficiaries = []
    for i in range(1, 6):
        name_col = _fuzzy_find(columns, f"beneficiary {i} name", f"benef{i} name")
        pct_col = _fuzzy_find(columns, f"beneficiary {i} %", f"beneficiary {i} percent")
        dob_col = _fuzzy_find(columns, f"beneficiary {i} dob", f"beneficiary {i} date")

        name = _str_or_none(row.get(name_col)) if name_col else None
        if not name:
            break  # No more beneficiaries

        pct_raw = row.get(pct_col) if pct_col else None
        pct = None
        if pct_raw is not None and not pd.isna(pct_raw):
            try:
                pct = float(str(pct_raw).replace("%", "").strip())
            except ValueError:
                pct = None

        dob = _str_or_none(row.get(dob_col)) if dob_col else None
        beneficiaries.append({"name": name, "percentage": pct, "dob": dob})
    return beneficiaries


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_file(file_path: str) -> list[dict]:
    """
    Parse a CSV or Excel file and return a list of household dicts ready for DB upsert.

    ──────────────────────────────────────────────────────────────────────────────
    INPUT
    ──────────────────────────────────────────────────────────────────────────────
    A flat, row-per-account CSV/Excel file where EVERY row represents one account
    belonging to one member of one household.  Column names are matched fuzzily
    (case-insensitive substring match), so "Yearly Income", "annual income", and
    "income" all resolve to the same logical field.

    Example input (3 rows → 1 household, 2 members, 3 accounts):

        Household Name        | First Name | Last Name | Account Type | Custodian | Annual Income | Risk Tolerance
        ──────────────────────┼────────────┼───────────┼──────────────┼───────────┼───────────────┼────────────────
        Raj and Priya Sharma  | Raj        | Sharma    | Roth IRA     | Fidelity  | 200000        | Aggressive
        Raj and Priya Sharma  | Raj        | Sharma    | 401k         | Vanguard  |               |
        Raj and Priya Sharma  | Priya      | Sharma    | Joint RMA    | Schwab    |               |

    ──────────────────────────────────────────────────────────────────────────────
    WHAT IT DOES INTERNALLY
    ──────────────────────────────────────────────────────────────────────────────
    1. Loads the file into a DataFrame (pandas), normalises column name whitespace.
    2. Detects the "household name" column via fuzzy match.
    3. Groups rows by household name.  For each household:
       - Household-level fields (net worth, income, risk …) are taken from the
         FIRST row that has a non-null value for each field.
       - Members are deduplicated by (first_name, last_name).  A member dict is
         created once; subsequent rows for the same member only ADD new accounts
         or bank details to the existing member dict.
       - Beneficiaries are deduplicated by name across rows.
    4. Strips the internal `_member_keys` dedup set before returning.

    ──────────────────────────────────────────────────────────────────────────────
    OUTPUT — list[dict]
    ──────────────────────────────────────────────────────────────────────────────
    Returns one dict per unique household.  Shape of each dict:

    [
      {
        "household_name":               "Raj and Priya Sharma",   # str
        "estimated_liquid_net_worth":   3_000_000.0,              # float | None
        "estimated_total_net_worth":    5_500_000.0,              # float | None
        "annual_income":                200_000.0,                # float | None
        "tax_bracket":                  "32%",                    # str | None
        "primary_investment_objective": "Growth",                 # str | None
        "risk_tolerance":               "Aggressive",             # str | None
        "time_horizon":                 "Long-term",              # str | None
        "source_of_funds":              "Employment",             # str | None
        "primary_use_of_funds":         "Retirement",             # str | None
        "liquidity_needs":              "Low",                    # str | None
        "account_decision_making":      "Joint",                  # str | None

        "members": [
          {
            "first_name":                 "Raj",                  # str | None
            "last_name":                  "Sharma",               # str | None
            "dob":                        "1978-04-12",           # str | None
            "phone":                      "555-100-2000",         # str | None
            "email":                      "raj@example.com",      # str | None
            "address":                    "123 Main St, NY",      # str | None
            "ssn":                        "123-45-6789",          # str | None
            "occupation":                 "Engineer",             # str | None
            "employer":                   "Acme Corp",            # str | None
            "marital_status":             "Married",              # str | None
            "drivers_license_no":         "D1234567",             # str | None
            "drivers_license_state":      "CA",                   # str | None
            "drivers_license_issue_date": "2018-06-01",           # str | None
            "drivers_license_exp_date":   "2026-06-01",           # str | None

            "accounts": [
              {
                "account_type":   "Roth IRA",   # str | None
                "custodian":      "Fidelity",   # str | None
                "account_number": "ACC-001",    # str | None
              },
              {
                "account_type":   "401k",
                "custodian":      "Vanguard",
                "account_number": None,
              },
            ],

            "bank_details": [
              {
                "bank_name":      "Chase",      # str | None
                "bank_type":      "Checking",   # str | None
                "account_number": "CHK-9921",   # str | None
              }
            ],

            "beneficiaries": [
              {
                "name":       "Priya Sharma",   # str
                "percentage": 100.0,            # float | None
                "dob":        "1980-02-20",     # str | None
              }
            ],
          },
          # … more members
        ],
      },
      # … more households
    ]

    Raises ValueError if no household-name column can be found in the file.
    """
    # ---- Load file --------------------------------------------------------
    if file_path.lower().endswith((".xlsx", ".xls")):
        # read_excel defaults to sheet_name=0 (first sheet only).
        # sheet_name=None returns an OrderedDict of {sheet_name: DataFrame}.
        # We concat all sheets so data spread across multiple sheets is captured.
        # If sheets have different columns, pd.concat fills missing cells with NaN.
        all_sheets: dict = pd.read_excel(file_path, sheet_name=None, dtype=str)
        df = pd.concat(all_sheets.values(), ignore_index=True)
    else:
        df = pd.read_csv(file_path, dtype=str)

    # Normalise: strip leading/trailing whitespace from column names and values
    df.columns = [str(c).strip() for c in df.columns]
    df = df.where(pd.notna(df), None)

    columns = list(df.columns)

    # ---- Group by household -----------------------------------------------
    household_col = _fuzzy_find(columns, "household name", "household")
    if household_col is None:
        raise ValueError("Could not locate a 'Household Name' column in the file.")

    households: dict[str, dict] = {}

    for _, row in df.iterrows():
        hh_name = _str_or_none(row.get(household_col))
        if not hh_name:
            continue

        # ---- Household-level data (take first non-null across rows) --------
        if hh_name not in households:
            households[hh_name] = {
                "household_name": hh_name,
                "estimated_liquid_net_worth": _parse_money(_get(row, columns, "estimated liquid net worth", "liquid net worth")),
                "estimated_total_net_worth": _parse_money(_get(row, columns, "estimated total net worth", "total net worth")),
                "annual_income": _parse_money(_get(row, columns, "annual income", "income")),
                "tax_bracket": _str_or_none(_get(row, columns, "tax bracket", "client tax bracket")),
                "primary_investment_objective": _str_or_none(_get(row, columns, "primary investment objective", "investment objective")),
                "risk_tolerance": _str_or_none(_get(row, columns, "risk tolerance")),
                "time_horizon": _str_or_none(_get(row, columns, "time horizon")),
                "source_of_funds": _str_or_none(_get(row, columns, "source of funds")),
                "primary_use_of_funds": _str_or_none(_get(row, columns, "primary use of funds", "use of funds")),
                "liquidity_needs": _str_or_none(_get(row, columns, "liquidity needs")),
                "account_decision_making": _str_or_none(_get(row, columns, "account decision making", "decision making")),
                "members": [],
                "_member_keys": set(),  # internal dedup key (first+last name)
            }
        else:
            # Fill missing household-level fields from subsequent rows
            hh = households[hh_name]
            if hh["estimated_liquid_net_worth"] is None:
                hh["estimated_liquid_net_worth"] = _parse_money(_get(row, columns, "estimated liquid net worth", "liquid net worth"))
            if hh["estimated_total_net_worth"] is None:
                hh["estimated_total_net_worth"] = _parse_money(_get(row, columns, "estimated total net worth", "total net worth"))
            if hh["annual_income"] is None:
                hh["annual_income"] = _parse_money(_get(row, columns, "annual income", "income"))

        hh = households[hh_name]

        # ---- Member data --------------------------------------------------
        first_name = _str_or_none(_get(row, columns, "first name", "firstname"))
        last_name = _str_or_none(_get(row, columns, "last name", "lastname"))

        if not first_name and not last_name:
            # Row has no member info – skip member/account extraction
            continue

        member_key = f"{(first_name or '').lower()}|{(last_name or '').lower()}"

        # Account for this row (may be None if no account type)
        account_type = _str_or_none(_get(row, columns, "account type", "acct type"))
        custodian = _str_or_none(_get(row, columns, "custodian"))
        account_number_acct = _str_or_none(_get(row, columns, "account number", "account no", "acct no", "acct number"))

        bank_name = _str_or_none(_get(row, columns, "bank name"))
        bank_type = _str_or_none(_get(row, columns, "bank type", "checking/savings"))
        bank_account_no = _str_or_none(_get(row, columns, "account no", "account number"))

        beneficiaries = _extract_beneficiaries(row, columns)

        if member_key not in hh["_member_keys"]:
            # New member
            member = {
                "first_name": first_name,
                "last_name": last_name,
                "dob": _str_or_none(_get(row, columns, "dob", "date of birth")),
                "phone": _str_or_none(_get(row, columns, "phone", "phone #", "phone number")),
                "email": _str_or_none(_get(row, columns, "email")),
                "address": _str_or_none(_get(row, columns, "address")),
                "ssn": _str_or_none(_get(row, columns, "ssn", "ssn#", "social security")),
                "occupation": _str_or_none(_get(row, columns, "occupation")),
                "employer": _str_or_none(_get(row, columns, "employer")),
                "marital_status": _str_or_none(_get(row, columns, "marital status")),
                "drivers_license_no": _str_or_none(_get(row, columns, "drivers license/id #", "drivers license", "license no", "dl #")),
                "drivers_license_state": _str_or_none(_get(row, columns, "drivers license/id state", "license state", "dl state")),
                "drivers_license_issue_date": _str_or_none(_get(row, columns, "drivers license/id issue date", "license issue date", "dl issue")),
                "drivers_license_exp_date": _str_or_none(_get(row, columns, "drivers license/id expiration date", "license exp date", "dl exp")),
                "accounts": [],
                "bank_details": [],
                "beneficiaries": beneficiaries,
            }
            hh["members"].append(member)
            hh["_member_keys"].add(member_key)
        else:
            # Existing member – just append new account/bank detail below
            member = next(
                m for m in hh["members"]
                if f"{(m['first_name'] or '').lower()}|{(m['last_name'] or '').lower()}" == member_key
            )

        # Append account if present
        if account_type:
            member["accounts"].append({
                "account_type": account_type,
                "custodian": custodian,
                "account_number": account_number_acct,
            })

        # Append bank detail if present
        if bank_name:
            member["bank_details"].append({
                "bank_name": bank_name,
                "bank_type": bank_type,
                "account_number": bank_account_no,
            })

        # Append beneficiaries for this row to the member (avoid dupes by name)
        existing_bene_names = {b["name"] for b in member["beneficiaries"]}
        for b in beneficiaries:
            if b["name"] not in existing_bene_names:
                member["beneficiaries"].append(b)
                existing_bene_names.add(b["name"])

    # ---- Clean up internal keys and return --------------------------------
    result = []
    for hh in households.values():
        hh.pop("_member_keys", None)
        result.append(hh)

    return result
