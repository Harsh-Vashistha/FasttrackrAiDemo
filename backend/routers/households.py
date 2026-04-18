"""
Households router — CRUD operations for household records.
"""

import json
from typing import List, Any, Optional

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models
import schemas

router = APIRouter(prefix="/households", tags=["households"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_household_or_404(household_id: int, db: Session) -> models.Household:
    hh = (
        db.query(models.Household)
        .filter(models.Household.id == household_id)
        .first()
    )
    if not hh:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household {household_id} not found",
        )
    return hh


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=List[schemas.HouseholdListItem])
def list_households(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Return a paginated list of households with member and account counts."""
    households = (
        db.query(models.Household)
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []
    for hh in households:
        item = schemas.HouseholdListItem.model_validate(hh)
        item.member_count = len(hh.members)
        item.account_count = len(hh.accounts)
        result.append(item)
    return result


@router.get("/{household_id}", response_model=schemas.HouseholdResponse)
def get_household(
    household_id: int,
    db: Session = Depends(get_db),
):
    """Return full household detail including nested members and accounts."""
    return _get_household_or_404(household_id, db)


@router.put("/{household_id}", response_model=schemas.HouseholdResponse)
def update_household(
    household_id: int,
    payload: schemas.HouseholdUpdate,
    db: Session = Depends(get_db),
):
    """Partial update of household fields."""
    hh = _get_household_or_404(household_id, db)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(hh, field, value)

    db.commit()
    db.refresh(hh)
    return hh


@router.delete("/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_household(
    household_id: int,
    db: Session = Depends(get_db),
):
    """Delete a household and all related records (cascade)."""
    hh = _get_household_or_404(household_id, db)
    db.delete(hh)
    db.commit()


@router.get("/{household_id}/action-items", response_model=List[schemas.ActionItemResponse])
def get_action_items(
    household_id: int,
    db: Session = Depends(get_db),
):
    """Return all action items for a household, newest first."""
    _get_household_or_404(household_id, db)
    return (
        db.query(models.ActionItem)
        .filter(models.ActionItem.household_id == household_id)
        .order_by(models.ActionItem.created_at.desc())
        .all()
    )


@router.patch("/{household_id}/action-items/{item_id}", response_model=schemas.ActionItemResponse)
def update_action_item_status(
    household_id: int,
    item_id: int,
    payload: schemas.ActionItemStatusUpdate,
    db: Session = Depends(get_db),
):
    """Toggle an action item between pending and completed."""
    _get_household_or_404(household_id, db)
    item = (
        db.query(models.ActionItem)
        .filter(
            models.ActionItem.id == item_id,
            models.ActionItem.household_id == household_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action item not found")

    item.status = payload.status
    item.completed_at = datetime.utcnow() if payload.status == "completed" else None
    db.commit()
    db.refresh(item)
    return item


@router.get("/{household_id}/audio-insights")
def get_audio_insights(
    household_id: int,
    db: Session = Depends(get_db),
):
    """Return all audio insights for a household."""
    _get_household_or_404(household_id, db)
    insights = (
        db.query(models.AudioInsight)
        .filter(models.AudioInsight.household_id == household_id)
        .order_by(models.AudioInsight.created_at.desc())
        .all()
    )
    result = []
    for insight in insights:
        extracted = None
        if insight.extracted_data:
            try:
                extracted = json.loads(insight.extracted_data)
            except Exception:
                extracted = {"raw_response": insight.extracted_data}
        result.append({
            "id": insight.id,
            "household_id": insight.household_id,
            "transcription": insight.transcription,
            "extracted_data": extracted,
            "created_at": insight.created_at.isoformat() if insight.created_at else None,
        })
    return result
