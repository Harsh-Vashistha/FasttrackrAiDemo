from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# BankDetail
# ---------------------------------------------------------------------------

class BankDetailBase(BaseModel):
    bank_name: Optional[str] = None
    bank_type: Optional[str] = None
    account_number: Optional[str] = None
    routing_number: Optional[str] = None


class BankDetailCreate(BankDetailBase):
    pass


class BankDetailResponse(BankDetailBase):
    id: int
    member_id: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Beneficiary
# ---------------------------------------------------------------------------

class BeneficiaryBase(BaseModel):
    name: Optional[str] = None
    percentage: Optional[float] = None
    dob: Optional[str] = None


class BeneficiaryCreate(BeneficiaryBase):
    pass


class BeneficiaryResponse(BeneficiaryBase):
    id: int
    account_id: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

class AccountBase(BaseModel):
    account_type: str
    custodian: Optional[str] = None
    account_number: Optional[str] = None
    account_value: Optional[float] = None
    ownership_type: Optional[str] = None


class AccountCreate(AccountBase):
    household_id: int
    member_id: Optional[int] = None


class AccountResponse(AccountBase):
    id: int
    household_id: int
    member_id: Optional[int] = None
    created_at: datetime
    beneficiaries: List[BeneficiaryResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Member
# ---------------------------------------------------------------------------

class MemberBase(BaseModel):
    first_name: str
    last_name: str
    dob: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    ssn: Optional[str] = None
    occupation: Optional[str] = None
    employer: Optional[str] = None
    marital_status: Optional[str] = None
    relationship: Optional[str] = None
    drivers_license_no: Optional[str] = None
    drivers_license_state: Optional[str] = None
    drivers_license_issue_date: Optional[str] = None
    drivers_license_exp_date: Optional[str] = None


class MemberCreate(MemberBase):
    household_id: int


class MemberResponse(MemberBase):
    id: int
    household_id: int
    created_at: datetime
    bank_details: List[BankDetailResponse] = []
    accounts: List[AccountResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Household
# ---------------------------------------------------------------------------

class HouseholdBase(BaseModel):
    name: str
    estimated_liquid_net_worth: Optional[float] = None
    estimated_total_net_worth: Optional[float] = None
    annual_income: Optional[float] = None
    tax_bracket: Optional[str] = None
    primary_investment_objective: Optional[str] = None
    risk_tolerance: Optional[str] = None
    time_horizon: Optional[str] = None
    source_of_funds: Optional[str] = None
    primary_use_of_funds: Optional[str] = None
    liquidity_needs: Optional[str] = None
    account_decision_making: Optional[str] = None


class HouseholdCreate(HouseholdBase):
    pass


class HouseholdUpdate(BaseModel):
    name: Optional[str] = None
    estimated_liquid_net_worth: Optional[float] = None
    estimated_total_net_worth: Optional[float] = None
    annual_income: Optional[float] = None
    tax_bracket: Optional[str] = None
    primary_investment_objective: Optional[str] = None
    risk_tolerance: Optional[str] = None
    time_horizon: Optional[str] = None
    source_of_funds: Optional[str] = None
    primary_use_of_funds: Optional[str] = None
    liquidity_needs: Optional[str] = None
    account_decision_making: Optional[str] = None


class HouseholdResponse(HouseholdBase):
    id: int
    created_at: datetime
    updated_at: datetime
    members: List[MemberResponse] = []
    accounts: List[AccountResponse] = []

    model_config = {"from_attributes": True}


class HouseholdListItem(HouseholdBase):
    """Lightweight household listing with counts instead of full nested data."""
    id: int
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    account_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# AudioInsight
# ---------------------------------------------------------------------------

class AudioInsightResponse(BaseModel):
    id: int
    household_id: Optional[int] = None
    transcription: Optional[str] = None
    extracted_data: Optional[Any] = None  # parsed JSON
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Insights / Charts
# ---------------------------------------------------------------------------

class NetWorthItem(BaseModel):
    name: str
    liquid_net_worth: Optional[float] = None
    total_net_worth: Optional[float] = None


class IncomeItem(BaseModel):
    name: str
    annual_income: Optional[float] = None


class AccountTypeItem(BaseModel):
    account_type: str
    count: int


class TaxBracketItem(BaseModel):
    bracket: str
    count: int


class RiskToleranceItem(BaseModel):
    risk: str
    count: int


class MembersPerHouseholdItem(BaseModel):
    household_name: str
    member_count: int


class InsightsResponse(BaseModel):
    households_by_net_worth: List[NetWorthItem] = []
    income_distribution: List[IncomeItem] = []
    account_type_distribution: List[AccountTypeItem] = []
    tax_bracket_distribution: List[TaxBracketItem] = []
    risk_tolerance_distribution: List[RiskToleranceItem] = []
    members_per_household: List[MembersPerHouseholdItem] = []
    total_aum: float = 0.0
    total_households: int = 0
    total_members: int = 0


class HouseholdInsightsResponse(BaseModel):
    household_id: int
    household_name: str
    total_accounts: int = 0
    total_members: int = 0
    account_type_breakdown: List[AccountTypeItem] = []
    estimated_liquid_net_worth: Optional[float] = None
    estimated_total_net_worth: Optional[float] = None
    annual_income: Optional[float] = None
    risk_tolerance: Optional[str] = None
    time_horizon: Optional[str] = None
    primary_investment_objective: Optional[str] = None


# ---------------------------------------------------------------------------
# ActionItem
# ---------------------------------------------------------------------------

class ActionItemResponse(BaseModel):
    id: int
    household_id: Optional[int] = None
    audio_insight_id: Optional[int] = None
    description: str
    status: str                         # "pending" | "completed"
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ActionItemStatusUpdate(BaseModel):
    status: str                         # "pending" | "completed"


# ---------------------------------------------------------------------------
# Upload responses
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    created: int
    updated: int
    errors: List[str] = []
    message: str


class AudioUploadResponse(BaseModel):
    insight_id: int
    household_id: Optional[int] = None
    transcription: str
    extracted_data: Any
    transcript_file: Optional[str] = None  # absolute path to the saved .txt file
    review_session_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Review Queue
# ---------------------------------------------------------------------------

class ProposedChangeResponse(BaseModel):
    id: int
    session_id: int
    entity_type: str
    entity_id: Optional[int] = None
    entity_label: Optional[str] = None
    field_name: str
    current_value: Optional[str] = None
    proposed_value: Optional[str] = None
    source_quote: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    status: str
    reviewer_feedback: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    revised_value: Optional[str] = None
    revised_source_quote: Optional[str] = None
    revised_confidence: Optional[float] = None
    agent_response: Optional[str] = None
    conversation_history: Optional[Any] = None  # parsed JSON
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewSessionResponse(BaseModel):
    id: int
    audio_insight_id: Optional[int] = None
    status: str
    matched_household_id: Optional[int] = None
    proposed_household_name: Optional[str] = None
    is_new_client: Optional[str] = None
    agent_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    proposed_changes: List[ProposedChangeResponse] = []

    model_config = {"from_attributes": True}


class ReviewSessionListItem(BaseModel):
    id: int
    audio_insight_id: Optional[int] = None
    status: str
    proposed_household_name: Optional[str] = None
    agent_summary: Optional[str] = None
    created_at: datetime
    pending_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    revised_count: int = 0
    dismissed_count: int = 0

    model_config = {"from_attributes": True}


class RejectChangeRequest(BaseModel):
    feedback: str


class ApplyChangesResponse(BaseModel):
    applied: int
    skipped: int
    message: str
