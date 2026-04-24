"""
Review agent — revises a single rejected proposed change.

Called by POST /review/{session_id}/changes/{change_id}/reject when a human
reviewer rejects a proposed DB change and provides written feedback.

Uses LangChain's ChatAnthropic.with_structured_output() so Claude is forced
to return a typed RevisionOutput — no manual JSON parsing or code-fence
stripping required.
"""

import json
import os
from typing import Optional, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

import models
from parsers import prompts


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class RevisionOutput(BaseModel):
    """Claude's decision when asked to revise or dismiss a rejected change."""

    action: Literal["revise", "dismiss"] = Field(
        description=(
            "'revise' if a better value was found or the reviewer provided the correct one. "
            "'dismiss' if the transcript genuinely does not support any change to this field."
        )
    )
    revised_value: Optional[str] = Field(
        default=None,
        description="The corrected value as a string.  Null when action='dismiss'.",
    )
    revised_source_quote: Optional[str] = Field(
        default=None,
        description="The transcript passage supporting the revised value.  Null when action='dismiss'.",
    )
    revised_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence in the revised value 0–1.  Null when action='dismiss'.",
    )
    agent_response: str = Field(
        description="1-2 sentences: what changed and why, or why the change was dismissed.",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def revise_single_change(
    transcript: str,
    change: models.ProposedChange,
    reviewer_feedback: str,
) -> dict:
    """
    Ask Claude to revise or dismiss a single rejected proposed change.

    Receives the original transcript, the full conversation history for this
    specific field (all prior rejection/revision rounds), and the latest
    reviewer feedback — giving Claude full context for a targeted correction.

    Args:
        transcript:        The original meeting transcript from AudioInsight.
        change:            The ProposedChange ORM object being disputed.
        reviewer_feedback: The human reviewer's written reason for rejection.

    Returns:
        dict matching RevisionOutput with keys:
            action, revised_value, revised_source_quote,
            revised_confidence, agent_response.

    Raises:
        KeyError: if ANTHROPIC_API_KEY is not set in the environment.
    """
    llm = ChatAnthropic(
        model="claude-opus-4-5",
        temperature=0,
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )
    structured_llm = llm.with_structured_output(RevisionOutput)

    # Rebuild conversation history so Claude has full context of prior rounds
    try:
        history: list = json.loads(change.conversation_history or "[]")
    except (json.JSONDecodeError, TypeError):
        history = []

    history_text = ""
    if history:
        lines = ["\n## Prior Conversation for This Change"]
        for entry in history:
            role = entry.get("role", "unknown")
            if role == "reviewer":
                action = entry.get("action", "feedback")
                feedback = entry.get("feedback") or action
                lines.append(f"  Reviewer [{action}]: {feedback}")
            elif role == "agent":
                lines.append(f"  Agent [{entry.get('action', 'response')}]: {entry.get('agent_response', '')}")
        history_text = "\n".join(lines)

    # Use revised values as the baseline if this change has already been through one round
    current_proposed = change.revised_value or change.proposed_value or ""
    current_quote    = change.revised_source_quote or change.source_quote or "N/A"

    system_prompt = (
        "You are a financial CRM assistant for a wealth management firm.\n"
        "A human reviewer rejected one of your proposed database changes and provided feedback.\n"
        "Re-examine the original transcript carefully and either revise your proposal or agree to dismiss it.\n\n"
        f"{prompts.SCHEMA_REFERENCE}\n"
        f"{prompts.WHISPER_GUIDANCE}"
    )

    user_message = (
        f"## Original Transcript\n{transcript}\n\n"
        f"## The Change Being Disputed\n"
        f"- Entity:               {change.entity_label or change.entity_type}\n"
        f"- Field:                {change.field_name}\n"
        f"- Current DB value:     {change.current_value or '— (null/empty)'}\n"
        f"- Your last proposed:   {current_proposed}\n"
        f'- Your last quote:      "{current_quote}"\n'
        f"- Your original reasoning: {change.reasoning or 'N/A'}"
        f"{history_text}\n\n"
        f'## Latest Reviewer Feedback\n"{reviewer_feedback}"\n\n'
        "Re-read the transcript in light of this feedback.\n"
        "Choose 'revise' if you found a better value or the reviewer told you the correct one.\n"
        "Choose 'dismiss' if the transcript genuinely does not support any value for this field."
    )

    output: RevisionOutput = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])

    return output.model_dump()
