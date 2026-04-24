"""
LangGraph column mapping agent for CSV / Excel imports.

Instead of regex fuzzy-matching column headers, an LLM reads the file's
actual headers alongside a few sample rows and returns an explicit mapping
of every DB field to its corresponding CSV column name.

Why LLM over regex:
  - Handles completely novel header names ("Client Annual Gross Income" → annual_income)
  - Understands semantic equivalence, not just substring overlap
  - One call per file (not per field) — fast and cheap using Haiku
  - Returns a typed, validated ColumnMapping object — no silent misses

Graph topology:
  map_columns → validate_mapping → END
"""

import os
from typing import Optional

import pandas as pd
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class BeneficiaryColumns(BaseModel):
    """Column names for one beneficiary slot (e.g. Beneficiary 1)."""
    name:       Optional[str] = Field(default=None, description="Column containing beneficiary name.")
    percentage: Optional[str] = Field(default=None, description="Column containing beneficiary percentage.")
    dob:        Optional[str] = Field(default=None, description="Column containing beneficiary date of birth.")


class ColumnMapping(BaseModel):
    """
    Maps every DB field to the exact CSV column header that contains it.
    Fields are null when no matching column exists in the file.
    """

    # ── Household ────────────────────────────────────────────────────────────
    household_name:               Optional[str] = Field(default=None, description="Full household or client name.")
    annual_income:                Optional[str] = Field(default=None, description="Total gross annual income.")
    estimated_total_net_worth:    Optional[str] = Field(default=None, description="Total net worth (all assets minus liabilities).")
    estimated_liquid_net_worth:   Optional[str] = Field(default=None, description="Liquid / accessible net worth only.")
    tax_bracket:                  Optional[str] = Field(default=None, description="Federal tax bracket (e.g. 32%).")
    primary_investment_objective: Optional[str] = Field(default=None, description="Main investment goal.")
    risk_tolerance:               Optional[str] = Field(default=None, description="Risk tolerance / risk profile.")
    time_horizon:                 Optional[str] = Field(default=None, description="Investment time horizon.")
    source_of_funds:              Optional[str] = Field(default=None, description="Where client money comes from.")
    primary_use_of_funds:         Optional[str] = Field(default=None, description="What the money will be used for.")
    liquidity_needs:              Optional[str] = Field(default=None, description="How much liquid access the client needs.")
    account_decision_making:      Optional[str] = Field(default=None, description="Who makes account decisions (individual, joint, etc.).")

    # ── Member ───────────────────────────────────────────────────────────────
    first_name:                   Optional[str] = Field(default=None, description="Client first / given name.")
    last_name:                    Optional[str] = Field(default=None, description="Client last / family name.")
    dob:                          Optional[str] = Field(default=None, description="Date of birth.")
    phone:                        Optional[str] = Field(default=None, description="Primary phone number.")
    email:                        Optional[str] = Field(default=None, description="Email address.")
    address:                      Optional[str] = Field(default=None, description="Full mailing address.")
    ssn:                          Optional[str] = Field(default=None, description="Social security number.")
    occupation:                   Optional[str] = Field(default=None, description="Job title / occupation.")
    employer:                     Optional[str] = Field(default=None, description="Current employer / company.")
    marital_status:               Optional[str] = Field(default=None, description="Marital status.")
    drivers_license_no:           Optional[str] = Field(default=None, description="Driver's license number.")
    drivers_license_state:        Optional[str] = Field(default=None, description="Driver's license issuing state.")
    drivers_license_issue_date:   Optional[str] = Field(default=None, description="Driver's license issue date.")
    drivers_license_exp_date:     Optional[str] = Field(default=None, description="Driver's license expiration date.")

    # ── Account ──────────────────────────────────────────────────────────────
    account_type:                 Optional[str] = Field(default=None, description="Financial account type (401K, Roth IRA, etc.).")
    custodian:                    Optional[str] = Field(default=None, description="Account custodian / broker / bank.")
    account_number:               Optional[str] = Field(default=None, description="Account number or identifier.")
    account_value:                Optional[str] = Field(default=None, description="Current account value in USD.")

    # ── Bank details ─────────────────────────────────────────────────────────
    bank_name:                    Optional[str] = Field(default=None, description="Name of the bank.")
    bank_type:                    Optional[str] = Field(default=None, description="Bank account type (checking, savings).")
    bank_account_number:          Optional[str] = Field(default=None, description="Bank account number (distinct from investment account number).")

    # ── Beneficiaries (list — one entry per numbered slot found) ─────────────
    beneficiaries: list[BeneficiaryColumns] = Field(
        default_factory=list,
        description=(
            "One entry per beneficiary slot found in the file. "
            "E.g. if the file has 'Beneficiary 1 Name', 'Beneficiary 1 %', "
            "'Beneficiary 2 Name' columns, return two BeneficiaryColumns entries."
        ),
    )


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class MapperState(TypedDict):
    headers:     list[str]
    sample_rows: list[dict]
    mapping:     Optional[ColumnMapping]
    error:       Optional[str]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def _map_columns_node(state: MapperState) -> MapperState:
    """
    Node 1 — map_columns
    Sends file headers and sample data to Claude and returns a complete
    ColumnMapping with every DB field pointed at its CSV column (or null).
    Uses claude-haiku — fast and cheap for a structured mapping task.
    """
    llm = ChatAnthropic(
        model="claude-haiku-4-5",
        temperature=0,
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )
    structured_llm = llm.with_structured_output(ColumnMapping)

    headers_str  = ", ".join(f'"{h}"' for h in state["headers"])
    samples_str  = "\n".join(str(r) for r in state["sample_rows"][:3])

    system_prompt = (
        "You are a data mapping assistant for a financial CRM.\n"
        "Your job is to map CSV column headers to the correct database field names.\n"
        "Set a field to null if no column in the file clearly corresponds to it.\n"
        "Return the EXACT column header string from the file — do not paraphrase or normalise it."
    )

    user_message = (
        f"## File Headers\n{headers_str}\n\n"
        f"## Sample Rows (first 3)\n{samples_str}\n\n"
        "Map each database field to the CSV column that contains it."
    )

    mapping: ColumnMapping = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])

    return {**state, "mapping": mapping}


def _validate_mapping_node(state: MapperState) -> MapperState:
    """
    Node 2 — validate_mapping
    Checks that the one truly required field (household_name) was mapped.
    Sets state["error"] if not so the caller can raise a clear exception.
    """
    mapping = state["mapping"]
    if mapping is None or not mapping.household_name:
        return {
            **state,
            "error": (
                "Could not identify a 'Household Name' column in the file. "
                "Please ensure your spreadsheet has a column that contains the client or household name."
            ),
        }
    return {**state, "error": None}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def _build_mapper_graph():
    graph = StateGraph(MapperState)

    graph.add_node("map_columns",      _map_columns_node)
    graph.add_node("validate_mapping", _validate_mapping_node)

    graph.set_entry_point("map_columns")
    graph.add_edge("map_columns",      "validate_mapping")
    graph.add_edge("validate_mapping", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_column_mapping(file_path: str) -> ColumnMapping:
    """
    Run the column mapping graph on a CSV or Excel file.

    Reads the file headers and up to 3 sample rows, calls Claude once to
    produce a ColumnMapping, then validates that the required household_name
    field was resolved.

    Args:
        file_path: Absolute path to the CSV or Excel file.

    Returns:
        A ColumnMapping where each field holds the exact CSV column header
        that contains that data, or None if the file has no such column.

    Raises:
        ValueError: if the household_name column cannot be identified.
        KeyError:   if ANTHROPIC_API_KEY is not set.
    """
    # Read headers and sample rows from the file
    if file_path.lower().endswith((".xlsx", ".xls")):
        all_sheets: dict = pd.read_excel(file_path, sheet_name=None, dtype=str)
        df = pd.concat(all_sheets.values(), ignore_index=True)
    else:
        df = pd.read_csv(file_path, dtype=str)

    df.columns = [str(c).strip() for c in df.columns]
    df = df.where(pd.notna(df), None)

    headers     = list(df.columns)
    sample_rows = df.head(3).to_dict(orient="records")

    graph        = _build_mapper_graph()
    final_state  = graph.invoke({
        "headers":     headers,
        "sample_rows": sample_rows,
        "mapping":     None,
        "error":       None,
    })

    if final_state.get("error"):
        raise ValueError(final_state["error"])

    return final_state["mapping"]
