"""
Review router — Human-in-the-Loop review queue for proposed DB changes.
"""

import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas

router = APIRouter(prefix="/review", tags=["review"])


def _parse_conversation_history(change: models.ProposedChange) -> list:
    """Parse conversation_history JSON string to a Python list."""
    try:
        return json.loads(change.conversation_history or "[]")
    except (json.JSONDecodeError, TypeError):
        return []


def _serialize_proposed_change(change: models.ProposedChange) -> schemas.ProposedChangeResponse:
    """Convert a ProposedChange ORM object to a response schema."""
    return schemas.ProposedChangeResponse(
        id=change.id,
        session_id=change.session_id,
        entity_type=change.entity_type,
        entity_id=change.entity_id,
        entity_label=change.entity_label,
        field_name=change.field_name,
        current_value=change.current_value,
        proposed_value=change.proposed_value,
        source_quote=change.source_quote,
        confidence=change.confidence,
        reasoning=change.reasoning,
        status=change.status,
        reviewer_feedback=change.reviewer_feedback,
        reviewed_at=change.reviewed_at,
        revised_value=change.revised_value,
        revised_source_quote=change.revised_source_quote,
        revised_confidence=change.revised_confidence,
        agent_response=change.agent_response,
        conversation_history=_parse_conversation_history(change),
        created_at=change.created_at,
    )


# ---------------------------------------------------------------------------
# GET /review — list all sessions
# ---------------------------------------------------------------------------

@router.get("", response_model=List[schemas.ReviewSessionListItem])
def list_review_sessions(db: Session = Depends(get_db)):
    """List all review sessions, newest first, with change counts per status."""
    sessions = (
        db.query(models.ReviewSession)
        .order_by(models.ReviewSession.created_at.desc())
        .all()
    )

    result = []
    for session in sessions:
        changes = session.proposed_changes
        item = schemas.ReviewSessionListItem(
            id=session.id,
            audio_insight_id=session.audio_insight_id,
            status=session.status,
            proposed_household_name=session.proposed_household_name,
            agent_summary=session.agent_summary,
            created_at=session.created_at,
            pending_count=sum(1 for c in changes if c.status == "pending"),
            approved_count=sum(1 for c in changes if c.status == "approved"),
            rejected_count=sum(1 for c in changes if c.status == "rejected"),
            revised_count=sum(1 for c in changes if c.status == "revised"),
            dismissed_count=sum(1 for c in changes if c.status == "dismissed"),
        )
        result.append(item)

    return result


# ---------------------------------------------------------------------------
# GET /review/{session_id} — full session with all changes
# ---------------------------------------------------------------------------

@router.get("/{session_id}", response_model=schemas.ReviewSessionResponse)
def get_review_session(session_id: int, db: Session = Depends(get_db)):
    """Get a full review session with all proposed changes."""
    session = db.query(models.ReviewSession).filter(models.ReviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review session not found")

    return schemas.ReviewSessionResponse(
        id=session.id,
        audio_insight_id=session.audio_insight_id,
        status=session.status,
        matched_household_id=session.matched_household_id,
        proposed_household_name=session.proposed_household_name,
        is_new_client=session.is_new_client,
        agent_summary=session.agent_summary,
        created_at=session.created_at,
        updated_at=session.updated_at,
        proposed_changes=[_serialize_proposed_change(c) for c in session.proposed_changes],
    )


# ---------------------------------------------------------------------------
# POST /review/{session_id}/changes/{change_id}/approve
# ---------------------------------------------------------------------------

@router.post("/{session_id}/changes/{change_id}/approve", response_model=schemas.ProposedChangeResponse)
def approve_change(session_id: int, change_id: int, db: Session = Depends(get_db)):
    """Approve a proposed change."""
    change = (
        db.query(models.ProposedChange)
        .filter(
            models.ProposedChange.id == change_id,
            models.ProposedChange.session_id == session_id,
        )
        .first()
    )
    if not change:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposed change not found")

    change.status = "approved"
    change.reviewed_at = datetime.utcnow()

    history = _parse_conversation_history(change)
    history.append({"role": "reviewer", "action": "approved", "timestamp": datetime.utcnow().isoformat()})
    change.conversation_history = json.dumps(history)

    db.commit()
    db.refresh(change)
    return _serialize_proposed_change(change)


# ---------------------------------------------------------------------------
# POST /review/{session_id}/changes/{change_id}/reject
# ---------------------------------------------------------------------------

@router.post("/{session_id}/changes/{change_id}/reject", response_model=schemas.ProposedChangeResponse)
def reject_change(
    session_id: int,
    change_id: int,
    body: schemas.RejectChangeRequest,
    db: Session = Depends(get_db),
):
    """
    Reject a proposed change with feedback.
    Immediately calls the agent to revise or dismiss the change (synchronous).
    """
    change = (
        db.query(models.ProposedChange)
        .filter(
            models.ProposedChange.id == change_id,
            models.ProposedChange.session_id == session_id,
        )
        .first()
    )
    if not change:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposed change not found")

    session = db.query(models.ReviewSession).filter(models.ReviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review session not found")

    # Get the transcript from the linked AudioInsight
    transcript = ""
    if session.audio_insight_id:
        insight = db.query(models.AudioInsight).filter(
            models.AudioInsight.id == session.audio_insight_id
        ).first()
        if insight and insight.transcription:
            transcript = insight.transcription

    # Update rejection fields
    change.status = "pending_revision"
    change.reviewer_feedback = body.feedback
    change.reviewed_at = datetime.utcnow()

    history = _parse_conversation_history(change)
    history.append({
        "role": "reviewer",
        "action": "rejected",
        "feedback": body.feedback,
        "timestamp": datetime.utcnow().isoformat(),
    })
    change.conversation_history = json.dumps(history)
    db.commit()

    # Call the agent to revise — lazy import to avoid circular imports
    from parsers.review_agent import revise_single_change
    agent_result = revise_single_change(transcript, change, body.feedback)

    action = agent_result.get("action", "dismiss")
    agent_response = agent_result.get("agent_response", "")

    history.append({
        "role": "agent",
        "action": action,
        "agent_response": agent_response,
        "timestamp": datetime.utcnow().isoformat(),
    })

    if action == "revise":
        change.status = "revised"
        change.revised_value = str(agent_result.get("revised_value") or "")
        change.revised_source_quote = agent_result.get("revised_source_quote")
        change.revised_confidence = agent_result.get("revised_confidence")
        change.agent_response = agent_response
    else:
        # dismiss
        change.status = "dismissed"
        change.agent_response = agent_response

    change.conversation_history = json.dumps(history)
    db.commit()
    db.refresh(change)
    return _serialize_proposed_change(change)


# ---------------------------------------------------------------------------
# POST /review/{session_id}/changes/{change_id}/accept-revision
# ---------------------------------------------------------------------------

@router.post("/{session_id}/changes/{change_id}/accept-revision", response_model=schemas.ProposedChangeResponse)
def accept_revision(session_id: int, change_id: int, db: Session = Depends(get_db)):
    """Accept a revised proposed change."""
    change = (
        db.query(models.ProposedChange)
        .filter(
            models.ProposedChange.id == change_id,
            models.ProposedChange.session_id == session_id,
        )
        .first()
    )
    if not change:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposed change not found")

    change.status = "approved"
    change.reviewed_at = datetime.utcnow()

    history = _parse_conversation_history(change)
    history.append({
        "role": "reviewer",
        "action": "accepted_revision",
        "timestamp": datetime.utcnow().isoformat(),
    })
    change.conversation_history = json.dumps(history)

    db.commit()
    db.refresh(change)
    return _serialize_proposed_change(change)


# ---------------------------------------------------------------------------
# POST /review/{session_id}/apply — apply all approved changes to DB
# ---------------------------------------------------------------------------

@router.post("/{session_id}/apply", response_model=schemas.ApplyChangesResponse)
def apply_changes(session_id: int, db: Session = Depends(get_db)):
    """Apply all approved changes to the database."""
    session = db.query(models.ReviewSession).filter(models.ReviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review session not found")

    approved_changes = [c for c in session.proposed_changes if c.status == "approved"]
    skipped = len([c for c in session.proposed_changes if c.status not in ("approved", "dismissed")])

    if not approved_changes:
        session.status = "completed"
        db.commit()
        return schemas.ApplyChangesResponse(applied=0, skipped=skipped, message="No approved changes to apply.")

    # Helper to get effective value for an approved change
    def effective_value(change: models.ProposedChange) -> str:
        # If the change went through revision, use revised_value; otherwise proposed_value
        if change.revised_value is not None:
            return change.revised_value
        return change.proposed_value or ""

    # Determine target household_id for new entities
    target_household_id = session.matched_household_id

    applied = 0

    # ---- Step 1: Create new household if needed ----------------------------
    new_household_changes = [c for c in approved_changes if c.entity_type == "new_household"]
    new_hh: models.Household | None = None

    if new_household_changes:
        # Use the session's proposed_household_name for the "name" field
        hh_name = session.proposed_household_name or "New Household"
        # Check if a household with this name already exists
        existing_hh = db.query(models.Household).filter(models.Household.name == hh_name).first()
        if existing_hh:
            new_hh = existing_hh
        else:
            new_hh = models.Household(name=hh_name)
            db.add(new_hh)
            db.flush()

        target_household_id = new_hh.id

        # Apply all other new_household field changes
        for change in new_household_changes:
            if change.field_name != "name":  # name was handled above
                val = effective_value(change)
                setattr(new_hh, change.field_name, val)
            applied += 1

        db.flush()

        # Backfill household_id on action items that were created at upload
        # time but had no household yet (new client scenario).
        if session.audio_insight_id:
            orphan_items = (
                db.query(models.ActionItem)
                .filter(
                    models.ActionItem.audio_insight_id == session.audio_insight_id,
                    models.ActionItem.household_id.is_(None),
                )
                .all()
            )
            for item in orphan_items:
                item.household_id = new_hh.id
        db.flush()

    # ---- Step 2: Create new members ----------------------------------------
    new_member_changes = [c for c in approved_changes if c.entity_type == "new_member"]
    # Group by entity_label
    member_groups: dict[str, list] = {}
    for change in new_member_changes:
        label = change.entity_label or "Unknown Member"
        member_groups.setdefault(label, []).append(change)

    created_members: dict[str, models.Member] = {}
    hh_id_for_new = target_household_id or session.matched_household_id

    for label, changes in member_groups.items():
        # Build member data from changes
        member_data: dict[str, str] = {}
        for c in changes:
            member_data[c.field_name] = effective_value(c)

        first_name = member_data.get("first_name", "")
        last_name = member_data.get("last_name", "")

        if not hh_id_for_new:
            # Skip if we have no household to attach to
            skipped += len(changes)
            continue

        # Check for existing member
        member = None
        if first_name and last_name:
            member = (
                db.query(models.Member)
                .filter(
                    models.Member.household_id == hh_id_for_new,
                    models.Member.first_name == first_name,
                    models.Member.last_name == last_name,
                )
                .first()
            )

        if member is None:
            member = models.Member(
                household_id=hh_id_for_new,
                first_name=first_name or "Unknown",
                last_name=last_name or "",
            )
            db.add(member)
            db.flush()

        for field, val in member_data.items():
            if field not in ("first_name", "last_name"):
                setattr(member, field, val)

        db.flush()
        created_members[label] = member
        applied += len(changes)

    # ---- Step 3: Create new accounts ---------------------------------------
    new_account_changes = [c for c in approved_changes if c.entity_type == "new_account"]
    account_groups: dict[str, list] = {}
    for change in new_account_changes:
        label = change.entity_label or "Unknown Account"
        account_groups.setdefault(label, []).append(change)

    for label, changes in account_groups.items():
        account_data: dict[str, str] = {}
        for c in changes:
            account_data[c.field_name] = effective_value(c)

        account_type = account_data.get("account_type", "Unknown")
        if not hh_id_for_new:
            skipped += len(changes)
            continue

        acc = models.Account(
            household_id=hh_id_for_new,
            account_type=account_type,
            custodian=account_data.get("custodian"),
            account_number=account_data.get("account_number"),
        )
        if account_data.get("account_value"):
            try:
                acc.account_value = float(account_data["account_value"])
            except (ValueError, TypeError):
                pass
        db.add(acc)
        db.flush()
        applied += len(changes)

    # ---- Step 4: Update existing entities ----------------------------------
    update_changes = [
        c for c in approved_changes
        if c.entity_type in ("household", "member", "account")
    ]

    for change in update_changes:
        val = effective_value(change)
        if change.entity_type == "household" and change.entity_id:
            hh = db.query(models.Household).filter(models.Household.id == change.entity_id).first()
            if hh:
                setattr(hh, change.field_name, val)
                applied += 1
            else:
                skipped += 1
        elif change.entity_type == "member" and change.entity_id:
            member = db.query(models.Member).filter(models.Member.id == change.entity_id).first()
            if member:
                setattr(member, change.field_name, val)
                applied += 1
            else:
                skipped += 1
        elif change.entity_type == "account" and change.entity_id:
            account = db.query(models.Account).filter(models.Account.id == change.entity_id).first()
            if account:
                setattr(account, change.field_name, val)
                applied += 1
            else:
                skipped += 1
        else:
            skipped += 1

    session.status = "completed"
    db.commit()

    return schemas.ApplyChangesResponse(
        applied=applied,
        skipped=skipped,
        message=f"Applied {applied} change(s) to the database. {skipped} skipped.",
    )
