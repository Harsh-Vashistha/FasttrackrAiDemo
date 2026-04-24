"""
Upload router — handles CSV/Excel file uploads and audio file processing.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# Directory where transcript files are written — created on first use
TRANSCRIPTS_DIR = Path(__file__).resolve().parent.parent / "transcripts"

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from parsers.csv_parser import parse_file
from parsers.audio_parser import transcribe_audio
from parsers.agent import run_agent

router = APIRouter(prefix="/upload", tags=["upload"])

# ---------------------------------------------------------------------------
# Allowed MIME types / extensions
# ---------------------------------------------------------------------------

EXCEL_CSV_EXTENSIONS = {".csv", ".xlsx", ".xls"}
AUDIO_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".flac", ".webm"}


def _extension(filename: str) -> str:
    return os.path.splitext(filename.lower())[1]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _upsert_household(db: Session, data: dict) -> tuple[models.Household, bool]:
    """
    Insert a new Household or update an existing one by name.
    Returns (household_obj, created:bool).
    """
    hh = (
        db.query(models.Household)
        .filter(models.Household.name == data["household_name"])
        .first()
    )
    created = hh is None
    if created:
        hh = models.Household(name=data["household_name"])
        db.add(hh)

    # Update scalar fields
    scalar_fields = [
        "estimated_liquid_net_worth",
        "estimated_total_net_worth",
        "annual_income",
        "tax_bracket",
        "primary_investment_objective",
        "risk_tolerance",
        "time_horizon",
        "source_of_funds",
        "primary_use_of_funds",
        "liquidity_needs",
        "account_decision_making",
    ]
    for field in scalar_fields:
        val = data.get(field)
        if val is not None:
            setattr(hh, field, val)

    db.flush()  # Get hh.id without committing

    # ---- Members ----------------------------------------------------------
    for member_data in data.get("members", []):
        first = (member_data.get("first_name") or "").strip()
        last = (member_data.get("last_name") or "").strip()

        member = (
            db.query(models.Member)
            .filter(
                models.Member.household_id == hh.id,
                models.Member.first_name == first,
                models.Member.last_name == last,
            )
            .first()
        )

        if member is None:
            member = models.Member(
                household_id=hh.id,
                first_name=first,
                last_name=last,
            )
            db.add(member)

        # Update member fields
        member_fields = [
            "dob", "phone", "email", "address", "ssn",
            "occupation", "employer", "marital_status", "relationship",
            "drivers_license_no", "drivers_license_state",
            "drivers_license_issue_date", "drivers_license_exp_date",
        ]
        for f in member_fields:
            val = member_data.get(f)
            if val is not None:
                setattr(member, f, val)

        db.flush()

        # ---- Accounts -----------------------------------------------------
        for acc_data in member_data.get("accounts", []):
            acc_type = (acc_data.get("account_type") or "").strip()
            if not acc_type:
                continue
            custodian = acc_data.get("custodian")
            acc_no = acc_data.get("account_number")

            # Dedup by account_number when present, else by type+custodian
            existing_acc = None
            if acc_no:
                existing_acc = (
                    db.query(models.Account)
                    .filter(
                        models.Account.household_id == hh.id,
                        models.Account.account_number == acc_no,
                    )
                    .first()
                )
            if existing_acc is None:
                existing_acc = (
                    db.query(models.Account)
                    .filter(
                        models.Account.household_id == hh.id,
                        models.Account.member_id == member.id,
                        models.Account.account_type == acc_type,
                        models.Account.custodian == custodian,
                    )
                    .first()
                )

            if existing_acc is None:
                acc = models.Account(
                    household_id=hh.id,
                    member_id=member.id,
                    account_type=acc_type,
                    custodian=custodian,
                    account_number=acc_no,
                )
                db.add(acc)
                db.flush()
            else:
                acc = existing_acc
                if custodian:
                    acc.custodian = custodian
                if acc_no:
                    acc.account_number = acc_no
                db.flush()

            # Beneficiaries for this account
            for bene_data in member_data.get("beneficiaries", []):
                name = bene_data.get("name")
                if not name:
                    continue
                existing_bene = (
                    db.query(models.Beneficiary)
                    .filter(
                        models.Beneficiary.account_id == acc.id,
                        models.Beneficiary.name == name,
                    )
                    .first()
                )
                if existing_bene is None:
                    db.add(
                        models.Beneficiary(
                            account_id=acc.id,
                            name=name,
                            percentage=bene_data.get("percentage"),
                            dob=bene_data.get("dob"),
                        )
                    )

        # ---- Bank details -------------------------------------------------
        for bank_data in member_data.get("bank_details", []):
            bank_name = bank_data.get("bank_name")
            if not bank_name:
                continue
            existing_bank = (
                db.query(models.BankDetail)
                .filter(
                    models.BankDetail.member_id == member.id,
                    models.BankDetail.bank_name == bank_name,
                )
                .first()
            )
            if existing_bank is None:
                db.add(
                    models.BankDetail(
                        member_id=member.id,
                        bank_name=bank_name,
                        bank_type=bank_data.get("bank_type"),
                        account_number=bank_data.get("account_number"),
                    )
                )

    return hh, created


# ---------------------------------------------------------------------------
# POST /upload/excel
# ---------------------------------------------------------------------------

@router.post("/excel", response_model=schemas.UploadResponse)
async def upload_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Accept a CSV or XLSX file, parse it, and upsert households into the DB.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    ext = _extension(file.filename)
    if ext not in EXCEL_CSV_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Must be one of {EXCEL_CSV_EXTENSIONS}.",
        )

    # Save to a temp file so pandas can read it
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        parsed_households = parse_file(tmp_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse file: {exc}",
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    created_count = 0
    updated_count = 0
    errors: list[str] = []

    for hh_data in parsed_households:
        try:
            _, was_created = _upsert_household(db, hh_data)
            if was_created:
                created_count += 1
            else:
                updated_count += 1
        except Exception as exc:
            errors.append(f"Household '{hh_data.get('household_name')}': {exc}")
            db.rollback()
            continue

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database commit failed: {exc}",
        )

    return schemas.UploadResponse(
        created=created_count,
        updated=updated_count,
        errors=errors,
        message=(
            f"Processed {len(parsed_households)} household(s): "
            f"{created_count} created, {updated_count} updated."
            + (f" {len(errors)} error(s)." if errors else "")
        ),
    )


# ---------------------------------------------------------------------------
# POST /upload/audio
# ---------------------------------------------------------------------------

@router.post("/audio", response_model=schemas.AudioUploadResponse)
async def upload_audio(
    file: UploadFile = File(...),
    household_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Accept an audio file, transcribe it with Whisper, extract financial data
    with Claude, and persist an AudioInsight record.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    ext = _extension(file.filename)
    if ext not in AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio type '{ext}'. Must be one of {AUDIO_EXTENSIONS}.",
        )

    # Validate household_id if provided
    household_name: Optional[str] = None
    if household_id is not None:
        hh = db.query(models.Household).filter(models.Household.id == household_id).first()
        if not hh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Household {household_id} not found.",
            )
        household_name = hh.name

    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        # Step 1 — Transcribe with Whisper
        transcription = transcribe_audio(tmp_path)

        # Step 2 — Save raw transcript to disk for audit / debugging
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_stem = Path(file.filename).stem.replace(" ", "_")
        transcript_path = TRANSCRIPTS_DIR / f"{timestamp}_{safe_stem}.txt"

        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(f"File     : {file.filename}\n")
            f.write(f"Uploaded : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Household: {household_name or 'not linked'}\n")
            f.write("=" * 60 + "\n\n")
            f.write(transcription)

        # Step 3 — Run the LangGraph extraction agent
        # household_id comes directly from the user's frontend selection —
        # no regex or fuzzy matching. None means new client.
        agent_result = run_agent(transcription, db, household_id=household_id)

        # Append structured output to the transcript file
        with open(transcript_path, "a", encoding="utf-8") as f:
            f.write("\n\n" + "=" * 60 + "\n")
            f.write("AGENT EXTRACTION OUTPUT\n")
            f.write("=" * 60 + "\n")
            f.write(json.dumps(agent_result, indent=2, default=str))
            f.write("\n")

        # Build extracted_data dict for AudioInsight storage
        extracted_data = {
            "household_name": agent_result.get("proposed_household_name"),
            "key_insights":   agent_result.get("key_insights", []),
            "action_items":   agent_result.get("action_items", []),
            "agent_summary":  agent_result.get("agent_summary", ""),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio processing failed: {exc}",
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Persist AudioInsight
    insight = models.AudioInsight(
        household_id=household_id,
        transcription=transcription,
        extracted_data=json.dumps(extracted_data),
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)

    # ---- Persist action items as individual DB records ---------------------
    # extracted_data["action_items"] is a list of strings from Claude.
    # Storing them in their own table (instead of buried in JSON) means
    # they can be queried, filtered, and updated per household later.
    for description in extracted_data.get("action_items", []):
        if description and str(description).strip():
            db.add(models.ActionItem(
                household_id=household_id,        # may be None if not linked yet
                audio_insight_id=insight.id,
                description=str(description).strip(),
                status="pending",
            ))
    db.commit()

    # ---- Persist review session and proposed changes -----------------------
    review_session_id: Optional[int] = None
    try:
        review_session = models.ReviewSession(
            audio_insight_id=insight.id,
            status="pending",
            matched_household_id=agent_result.get("matched_household_id"),
            proposed_household_name=agent_result.get("proposed_household_name"),
            is_new_client=str(agent_result.get("is_new_client", True)).lower(),
            agent_summary=agent_result.get("agent_summary", ""),
        )
        db.add(review_session)
        db.flush()

        for change_data in agent_result.get("proposed_changes", []):
            # Look up current_value from DB if entity_id is provided
            current_value = None
            entity_id = change_data.get("entity_id")
            entity_type = change_data.get("entity_type", "")
            field_name = change_data.get("field_name", "")

            if entity_id and entity_type and field_name:
                if entity_type == "household":
                    obj = db.query(models.Household).filter(models.Household.id == entity_id).first()
                    if obj:
                        raw_val = getattr(obj, field_name, None)
                        current_value = str(raw_val) if raw_val is not None else None
                elif entity_type == "member":
                    obj = db.query(models.Member).filter(models.Member.id == entity_id).first()
                    if obj:
                        raw_val = getattr(obj, field_name, None)
                        current_value = str(raw_val) if raw_val is not None else None
                elif entity_type == "account":
                    obj = db.query(models.Account).filter(models.Account.id == entity_id).first()
                    if obj:
                        raw_val = getattr(obj, field_name, None)
                        current_value = str(raw_val) if raw_val is not None else None

            proposed_change = models.ProposedChange(
                session_id=review_session.id,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_label=change_data.get("entity_label"),
                field_name=field_name,
                current_value=current_value,
                proposed_value=str(change_data.get("proposed_value") or ""),
                source_quote=change_data.get("source_quote"),
                confidence=change_data.get("confidence"),
                reasoning=change_data.get("reasoning"),
                status="pending",
                conversation_history="[]",
            )
            db.add(proposed_change)

        db.commit()
        db.refresh(review_session)
        review_session_id = review_session.id

    except Exception:
        # Don't fail the upload if the agent fails — just skip the review session
        db.rollback()

    return schemas.AudioUploadResponse(
        insight_id=insight.id,
        household_id=household_id,
        transcription=transcription,
        extracted_data=extracted_data,
        transcript_file=str(transcript_path),
        review_session_id=review_session_id,
    )
