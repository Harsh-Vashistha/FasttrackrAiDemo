"""
CSV / Excel parser for the FasttrackrAI financial advisor system.

Column mapping is handled by the LangGraph agent in column_mapper.py —
an LLM reads the file headers once and returns an explicit ColumnMapping
object that tells us the exact column name for every DB field.

This module handles only data extraction: reading values from the mapped
columns, deduplicating members, grouping rows by household, and returning
a list of structured dicts ready for DB upsert.
"""

import re
from typing import Any, Optional

import pandas as pd

from parsers.column_mapper import ColumnMapping, get_column_mapping


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------

def _parse_money(value: Any) -> Optional[float]:
    """Convert "$1,000,000" or "1000000" to float. Returns None on failure."""
    if value is None:
        return None
    s = str(value).strip()
    if s in ("", "nan", "NaN", "N/A", "n/a"):
        return None
    s = re.sub(r"[\$,\s]", "", s).rstrip("%")
    try:
        return float(s)
    except ValueError:
        return None


def _str_or_none(value: Any) -> Optional[str]:
    """Return a clean string or None for empty / NaN values."""
    if value is None:
        return None
    s = str(value).strip()
    return None if s in ("", "nan", "NaN", "N/A", "n/a", "None") else s


def _col(row: pd.Series, column_name: Optional[str]) -> Any:
    """
    Read a value from a row using the exact column name from the ColumnMapping.
    Returns None if the column name is None (field wasn't mapped) or missing.
    """
    if not column_name:
        return None
    val = row.get(column_name)
    return None if pd.isna(val) else val


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_file(file_path: str) -> list[dict]:
    """
    Parse a CSV or Excel file into a list of household dicts ready for DB upsert.

    Steps:
      1. Call the LangGraph column mapping agent (one LLM call) to get an
         explicit ColumnMapping — maps every DB field to its CSV column name.
      2. Load the full file with pandas (all sheets merged for Excel).
      3. Group rows by household name.
      4. For each household: extract scalar fields, members, accounts,
         bank details, and beneficiaries — using mapped column names directly.

    Returns:
        list[dict] — one dict per unique household, shaped for _upsert_household().

    Raises:
        ValueError: if the file has no identifiable household name column.
    """
    # Step 1 — LLM maps headers to DB fields
    mapping: ColumnMapping = get_column_mapping(file_path)

    # Step 2 — Load full file
    if file_path.lower().endswith((".xlsx", ".xls")):
        all_sheets: dict = pd.read_excel(file_path, sheet_name=None, dtype=str)
        df = pd.concat(all_sheets.values(), ignore_index=True)
    else:
        df = pd.read_csv(file_path, dtype=str)

    df.columns = [str(c).strip() for c in df.columns]
    df = df.where(pd.notna(df), None)

    # Step 3 — Group by household
    households: dict[str, dict] = {}

    for _, row in df.iterrows():
        hh_name = _str_or_none(_col(row, mapping.household_name))
        if not hh_name:
            continue

        # ── Household-level fields (first non-null value across rows) ─────────
        if hh_name not in households:
            households[hh_name] = {
                "household_name":               hh_name,
                "estimated_liquid_net_worth":   _parse_money(_col(row, mapping.estimated_liquid_net_worth)),
                "estimated_total_net_worth":    _parse_money(_col(row, mapping.estimated_total_net_worth)),
                "annual_income":                _parse_money(_col(row, mapping.annual_income)),
                "tax_bracket":                  _str_or_none(_col(row, mapping.tax_bracket)),
                "primary_investment_objective": _str_or_none(_col(row, mapping.primary_investment_objective)),
                "risk_tolerance":               _str_or_none(_col(row, mapping.risk_tolerance)),
                "time_horizon":                 _str_or_none(_col(row, mapping.time_horizon)),
                "source_of_funds":              _str_or_none(_col(row, mapping.source_of_funds)),
                "primary_use_of_funds":         _str_or_none(_col(row, mapping.primary_use_of_funds)),
                "liquidity_needs":              _str_or_none(_col(row, mapping.liquidity_needs)),
                "account_decision_making":      _str_or_none(_col(row, mapping.account_decision_making)),
                "members":      [],
                "_member_keys": set(),
            }
        else:
            # Fill any still-null household fields from subsequent rows
            hh = households[hh_name]
            if hh["estimated_liquid_net_worth"] is None:
                hh["estimated_liquid_net_worth"] = _parse_money(_col(row, mapping.estimated_liquid_net_worth))
            if hh["estimated_total_net_worth"] is None:
                hh["estimated_total_net_worth"]  = _parse_money(_col(row, mapping.estimated_total_net_worth))
            if hh["annual_income"] is None:
                hh["annual_income"] = _parse_money(_col(row, mapping.annual_income))

        hh = households[hh_name]

        # ── Member fields ─────────────────────────────────────────────────────
        first_name = _str_or_none(_col(row, mapping.first_name))
        last_name  = _str_or_none(_col(row, mapping.last_name))

        if not first_name and not last_name:
            continue  # Row has no member info

        member_key = f"{(first_name or '').lower()}|{(last_name or '').lower()}"

        # ── Account / bank for this row ───────────────────────────────────────
        account_type   = _str_or_none(_col(row, mapping.account_type))
        custodian      = _str_or_none(_col(row, mapping.custodian))
        account_number = _str_or_none(_col(row, mapping.account_number))

        bank_name          = _str_or_none(_col(row, mapping.bank_name))
        bank_type          = _str_or_none(_col(row, mapping.bank_type))
        bank_account_number = _str_or_none(_col(row, mapping.bank_account_number))

        # ── Beneficiaries (LLM mapped all slots) ─────────────────────────────
        beneficiaries = []
        for bene_cols in mapping.beneficiaries:
            name = _str_or_none(_col(row, bene_cols.name))
            if not name:
                break
            pct_raw = _col(row, bene_cols.percentage)
            pct = None
            if pct_raw is not None:
                try:
                    pct = float(str(pct_raw).replace("%", "").strip())
                except ValueError:
                    pct = None
            dob = _str_or_none(_col(row, bene_cols.dob))
            beneficiaries.append({"name": name, "percentage": pct, "dob": dob})

        # ── Create or extend member ───────────────────────────────────────────
        if member_key not in hh["_member_keys"]:
            member = {
                "first_name":                 first_name,
                "last_name":                  last_name,
                "dob":                        _str_or_none(_col(row, mapping.dob)),
                "phone":                      _str_or_none(_col(row, mapping.phone)),
                "email":                      _str_or_none(_col(row, mapping.email)),
                "address":                    _str_or_none(_col(row, mapping.address)),
                "ssn":                        _str_or_none(_col(row, mapping.ssn)),
                "occupation":                 _str_or_none(_col(row, mapping.occupation)),
                "employer":                   _str_or_none(_col(row, mapping.employer)),
                "marital_status":             _str_or_none(_col(row, mapping.marital_status)),
                "drivers_license_no":         _str_or_none(_col(row, mapping.drivers_license_no)),
                "drivers_license_state":      _str_or_none(_col(row, mapping.drivers_license_state)),
                "drivers_license_issue_date": _str_or_none(_col(row, mapping.drivers_license_issue_date)),
                "drivers_license_exp_date":   _str_or_none(_col(row, mapping.drivers_license_exp_date)),
                "accounts":      [],
                "bank_details":  [],
                "beneficiaries": beneficiaries,
            }
            hh["members"].append(member)
            hh["_member_keys"].add(member_key)
        else:
            member = next(
                m for m in hh["members"]
                if f"{(m['first_name'] or '').lower()}|{(m['last_name'] or '').lower()}" == member_key
            )

        if account_type:
            member["accounts"].append({
                "account_type":   account_type,
                "custodian":      custodian,
                "account_number": account_number,
            })

        if bank_name:
            member["bank_details"].append({
                "bank_name":      bank_name,
                "bank_type":      bank_type,
                "account_number": bank_account_number,
            })

        # Deduplicate beneficiaries by name
        existing_names = {b["name"] for b in member["beneficiaries"]}
        for b in beneficiaries:
            if b["name"] not in existing_names:
                member["beneficiaries"].append(b)
                existing_names.add(b["name"])

    # Clean up internal dedup sets before returning
    result = []
    for hh in households.values():
        hh.pop("_member_keys", None)
        result.append(hh)

    return result
