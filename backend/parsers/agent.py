"""
LangGraph extraction agent.

Pipeline (StateGraph):
  build_context → extract_with_claude → END

The client is identified by the household_id explicitly passed by the caller
(selected by the user on the frontend) — no regex guessing or fuzzy matching.

build_context fetches that household's current DB record and formats it as
a text snapshot.  extract_with_claude sends that snapshot + transcript to
Claude using with_structured_output() to guarantee a typed ExtractionOutput.
"""

import os
from typing import Optional, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing_extensions import TypedDict

from parsers import prompts
from parsers.context import build_client_context


# ---------------------------------------------------------------------------
# Structured output schemas (Pydantic)
#
# LangChain's with_structured_output() uses these to build a tool/schema for
# Claude, guaranteeing that the LLM response always conforms to the model.
# ---------------------------------------------------------------------------

class ProposedChangeSchema(BaseModel):
    entity_type: Literal[
        "household", "member", "account",
        "new_household", "new_member", "new_account",
    ]
    entity_id: Optional[int] = Field(
        default=None,
        description="DB id of existing entity, or null for new entities.",
    )
    entity_label: str = Field(
        description="Human-readable label; must be identical for all fields of the same person/account.",
    )
    field_name: str = Field(description="Exact DB column name from the schema reference.")
    proposed_value: str = Field(description="The extracted value as a string.")
    source_quote: str = Field(description="Verbatim words from the transcript supporting this value.")
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence 0–1.")
    reasoning: str = Field(description="One sentence: why this value, and any Whisper caveats.")


class ExtractionOutput(BaseModel):
    """Full structured output from one transcript analysis pass."""

    matched_household_id: Optional[int] = Field(
        default=None,
        description="ID of the matched household if found in DB, else null.",
    )
    proposed_household_name: str = Field(
        description="Full client name extracted from the transcript.",
    )
    is_new_client: bool = Field(
        description="True if this person has no existing household record.",
    )
    agent_summary: str = Field(
        description="2-3 sentence summary: who is the client, key financial facts, any Whisper artifacts to flag.",
    )
    proposed_changes: list[ProposedChangeSchema] = Field(
        default_factory=list,
        description="All field-level DB changes proposed from this transcript.",
    )
    key_insights: list[str] = Field(
        default_factory=list,
        description="Important observations from the meeting not captured as DB fields.",
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="Follow-up tasks mentioned or implied in the transcript.",
    )


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    transcript: str
    household_id: Optional[int]   # explicitly provided by the caller — no guessing
    client_context: str
    result: Optional[dict]


# ---------------------------------------------------------------------------
# Node factories
#
# Each factory closes over the db session so nodes can query the DB without
# passing it through the graph state (which would make state non-serialisable).
# ---------------------------------------------------------------------------

def _make_context_node(db: Session):
    """
    Node 1 — build_context
    Fetches the selected household's current DB record as a formatted string.
    The household_id was explicitly chosen by the user on the frontend —
    no regex extraction or fuzzy matching involved.
    Scoped to one household so other clients' PII never enters the prompt.
    """
    def build_context(state: AgentState) -> AgentState:
        context = build_client_context(state["household_id"], db)
        return {**state, "client_context": context}

    return build_context


def _make_extract_node():
    """
    Node 3 — extract_with_claude
    The only node that calls the LLM.  Uses ChatAnthropic.with_structured_output()
    so Claude is forced to return a valid ExtractionOutput — no parsing needed.
    """
    def extract_with_claude(state: AgentState) -> AgentState:
        llm = ChatAnthropic(
            model="claude-opus-4-5",
            temperature=0,
            api_key=os.environ["ANTHROPIC_API_KEY"],
        )
        structured_llm = llm.with_structured_output(ExtractionOutput)

        system_prompt = (
            "You are a financial CRM assistant for a wealth management firm.\n"
            "Analyze advisor meeting notes and extract precise, field-level database changes.\n\n"
            f"{prompts.SCHEMA_REFERENCE}\n"
            f"{prompts.ENTITY_RULES}\n"
            f"{prompts.WHISPER_GUIDANCE}"
        )

        user_message = (
            "## Current Client Database State — Scoped to This Client Only\n"
            f"{state['client_context']}\n\n"
            "## Transcript to Analyze\n"
            f"{state['transcript']}\n\n"
            "Extract all field-level changes, key insights, and action items from this transcript."
        )

        output: ExtractionOutput = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])

        return {**state, "result": output.model_dump()}

    return extract_with_claude


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def _build_extraction_graph(db: Session):
    """
    Compile the two-node extraction StateGraph.

    Graph topology:
        build_context → extract_with_claude → END

    Args:
        db: SQLAlchemy session injected into nodes via closure.

    Returns:
        A compiled LangGraph ready to call with .invoke().
    """
    graph = StateGraph(AgentState)

    graph.add_node("build_context",       _make_context_node(db))
    graph.add_node("extract_with_claude", _make_extract_node())

    graph.set_entry_point("build_context")
    graph.add_edge("build_context",       "extract_with_claude")
    graph.add_edge("extract_with_claude", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_agent(transcript: str, db: Session, household_id: Optional[int] = None) -> dict:
    """
    Run the extraction graph on a transcript and return the full result.

    Args:
        transcript:    Plain-text transcript from Whisper.
        db:            Active SQLAlchemy session.
        household_id:  The household explicitly selected by the user on the
                       frontend.  Pass None for new clients — the agent will
                       use new_household / new_member / new_account entity types.

    Returns a dict matching ExtractionOutput:
        {
            "matched_household_id": int | None,
            "proposed_household_name": str,
            "is_new_client": bool,
            "agent_summary": str,
            "proposed_changes": [{ entity_type, entity_id, entity_label,
                                    field_name, proposed_value, source_quote,
                                    confidence, reasoning }, ...],
            "key_insights": [str, ...],
            "action_items": [str, ...],
        }

    Raises:
        KeyError: if ANTHROPIC_API_KEY is not set in the environment.
    """
    graph = _build_extraction_graph(db)
    final_state = graph.invoke({
        "transcript":   transcript,
        "household_id": household_id,
        "client_context": "",
        "result": None,
    })
    return final_state["result"]
