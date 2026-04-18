from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, ForeignKey, DateTime
)
from sqlalchemy.orm import relationship as sa_relationship
from database import Base


class Household(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    estimated_liquid_net_worth = Column(Float, nullable=True)
    estimated_total_net_worth = Column(Float, nullable=True)
    annual_income = Column(Float, nullable=True)
    tax_bracket = Column(String, nullable=True)
    primary_investment_objective = Column(String, nullable=True)
    risk_tolerance = Column(String, nullable=True)
    time_horizon = Column(String, nullable=True)
    source_of_funds = Column(String, nullable=True)
    primary_use_of_funds = Column(String, nullable=True)
    liquidity_needs = Column(String, nullable=True)
    account_decision_making = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = sa_relationship("Member", back_populates="household", cascade="all, delete-orphan")
    accounts = sa_relationship("Account", back_populates="household", cascade="all, delete-orphan")
    audio_insights = sa_relationship("AudioInsight", back_populates="household", cascade="all, delete-orphan")
    action_items = sa_relationship("ActionItem", back_populates="household", cascade="all, delete-orphan")


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    dob = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    ssn = Column(String, nullable=True)
    occupation = Column(String, nullable=True)
    employer = Column(String, nullable=True)
    marital_status = Column(String, nullable=True)
    relationship = Column(String, nullable=True)  # e.g. "primary", "spouse", "child"
    drivers_license_no = Column(String, nullable=True)
    drivers_license_state = Column(String, nullable=True)
    drivers_license_issue_date = Column(String, nullable=True)
    drivers_license_exp_date = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    household = sa_relationship("Household", back_populates="members")
    accounts = sa_relationship("Account", back_populates="member")
    bank_details = sa_relationship("BankDetail", back_populates="member", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    account_type = Column(String, nullable=False)
    custodian = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    account_value = Column(Float, nullable=True)
    ownership_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    household = sa_relationship("Household", back_populates="accounts")
    member = sa_relationship("Member", back_populates="accounts")
    beneficiaries = sa_relationship("Beneficiary", back_populates="account", cascade="all, delete-orphan")


class BankDetail(Base):
    __tablename__ = "bank_details"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    bank_name = Column(String, nullable=True)
    bank_type = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    routing_number = Column(String, nullable=True)

    member = sa_relationship("Member", back_populates="bank_details")


class Beneficiary(Base):
    __tablename__ = "beneficiaries"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    name = Column(String, nullable=True)
    percentage = Column(Float, nullable=True)
    dob = Column(String, nullable=True)

    account = sa_relationship("Account", back_populates="beneficiaries")


class AudioInsight(Base):
    __tablename__ = "audio_insights"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=True)
    transcription = Column(Text, nullable=True)
    extracted_data = Column(Text, nullable=True)  # JSON stored as Text
    created_at = Column(DateTime, default=datetime.utcnow)

    household = sa_relationship("Household", back_populates="audio_insights")
    review_sessions = sa_relationship("ReviewSession", back_populates="audio_insight", cascade="all, delete-orphan")
    action_items = sa_relationship("ActionItem", back_populates="audio_insight", cascade="all, delete-orphan")


class ActionItem(Base):
    """
    A follow-up task extracted from a client meeting recording.

    Lifecycle:
      1. Created automatically when an audio file is uploaded and Claude
         extracts action_items from the transcript.
      2. Linked to both the source AudioInsight and the Household so they
         are permanently visible on the household page.
      3. Advisor marks status pending → completed when done.

    household_id is nullable because at upload time the audio may not yet
    be linked to a household (e.g. new client whose household is created
    later via the Review Queue apply step).  The apply step backfills
    household_id once the household exists.
    """
    __tablename__ = "action_items"

    id               = Column(Integer, primary_key=True, index=True)
    household_id     = Column(Integer, ForeignKey("households.id"), nullable=True, index=True)
    audio_insight_id = Column(Integer, ForeignKey("audio_insights.id"), nullable=True)
    description      = Column(Text, nullable=False)
    status           = Column(String, default="pending")   # pending | completed
    created_at       = Column(DateTime, default=datetime.utcnow)
    completed_at     = Column(DateTime, nullable=True)

    household    = sa_relationship("Household", back_populates="action_items")
    audio_insight = sa_relationship("AudioInsight", back_populates="action_items", foreign_keys=[audio_insight_id])


class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id = Column(Integer, primary_key=True, index=True)
    audio_insight_id = Column(Integer, ForeignKey("audio_insights.id"), nullable=True)
    status = Column(String, default="pending")  # pending | in_review | completed | dismissed
    matched_household_id = Column(Integer, ForeignKey("households.id"), nullable=True)
    proposed_household_name = Column(String, nullable=True)
    is_new_client = Column(String, nullable=True)  # "true"/"false"
    agent_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    audio_insight = sa_relationship("AudioInsight", foreign_keys=[audio_insight_id], back_populates="review_sessions")
    matched_household = sa_relationship("Household", foreign_keys=[matched_household_id])
    proposed_changes = sa_relationship("ProposedChange", back_populates="session", cascade="all, delete-orphan")


class ProposedChange(Base):
    __tablename__ = "proposed_changes"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("review_sessions.id"), nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=True)
    entity_label = Column(String, nullable=True)
    field_name = Column(String, nullable=False)
    current_value = Column(Text, nullable=True)
    proposed_value = Column(Text, nullable=True)
    source_quote = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending | approved | rejected | pending_revision | revised | dismissed
    reviewer_feedback = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    revised_value = Column(Text, nullable=True)
    revised_source_quote = Column(Text, nullable=True)
    revised_confidence = Column(Float, nullable=True)
    agent_response = Column(Text, nullable=True)
    conversation_history = Column(Text, default="[]")  # JSON array
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = sa_relationship("ReviewSession", back_populates="proposed_changes")
