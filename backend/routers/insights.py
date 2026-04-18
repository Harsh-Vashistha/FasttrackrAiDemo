"""
Insights router — aggregated analytics data for dashboard charts.
"""

from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas

router = APIRouter(prefix="/insights", tags=["insights"])


# ---------------------------------------------------------------------------
# GET /insights/summary
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=schemas.InsightsResponse)
def get_summary(db: Session = Depends(get_db)):
    """Return aggregated data for all dashboard charts."""
    households = db.query(models.Household).all()
    members = db.query(models.Member).all()
    accounts = db.query(models.Account).all()

    # Households by net worth
    households_by_net_worth = [
        schemas.NetWorthItem(
            name=hh.name,
            liquid_net_worth=hh.estimated_liquid_net_worth,
            total_net_worth=hh.estimated_total_net_worth,
        )
        for hh in households
    ]

    # Income distribution
    income_distribution = [
        schemas.IncomeItem(name=hh.name, annual_income=hh.annual_income)
        for hh in households
        if hh.annual_income is not None
    ]

    # Account type distribution
    acc_type_counter: Counter = Counter()
    for acc in accounts:
        if acc.account_type:
            acc_type_counter[acc.account_type] += 1
    account_type_distribution = [
        schemas.AccountTypeItem(account_type=acc_type, count=cnt)
        for acc_type, cnt in sorted(acc_type_counter.items(), key=lambda x: -x[1])
    ]

    # Tax bracket distribution
    bracket_counter: Counter = Counter()
    for hh in households:
        if hh.tax_bracket:
            bracket_counter[hh.tax_bracket] += 1
    tax_bracket_distribution = [
        schemas.TaxBracketItem(bracket=bracket, count=cnt)
        for bracket, cnt in sorted(bracket_counter.items(), key=lambda x: -x[1])
    ]

    # Risk tolerance distribution
    risk_counter: Counter = Counter()
    for hh in households:
        if hh.risk_tolerance:
            risk_counter[hh.risk_tolerance] += 1
    risk_tolerance_distribution = [
        schemas.RiskToleranceItem(risk=risk, count=cnt)
        for risk, cnt in sorted(risk_counter.items(), key=lambda x: -x[1])
    ]

    # Members per household
    members_per_household = [
        schemas.MembersPerHouseholdItem(
            household_name=hh.name,
            member_count=len(hh.members),
        )
        for hh in households
    ]

    # Total AUM (sum of estimated_total_net_worth)
    total_aum = sum(
        hh.estimated_total_net_worth
        for hh in households
        if hh.estimated_total_net_worth is not None
    )

    return schemas.InsightsResponse(
        households_by_net_worth=households_by_net_worth,
        income_distribution=income_distribution,
        account_type_distribution=account_type_distribution,
        tax_bracket_distribution=tax_bracket_distribution,
        risk_tolerance_distribution=risk_tolerance_distribution,
        members_per_household=members_per_household,
        total_aum=total_aum,
        total_households=len(households),
        total_members=len(members),
    )


# ---------------------------------------------------------------------------
# GET /insights/household/{id}
# ---------------------------------------------------------------------------

@router.get("/household/{household_id}", response_model=schemas.HouseholdInsightsResponse)
def get_household_insights(
    household_id: int,
    db: Session = Depends(get_db),
):
    """Return analytics specific to a single household."""
    hh = (
        db.query(models.Household)
        .filter(models.Household.id == household_id)
        .first()
    )
    if not hh:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household {household_id} not found.",
        )

    acc_type_counter: Counter = Counter()
    for acc in hh.accounts:
        if acc.account_type:
            acc_type_counter[acc.account_type] += 1

    account_type_breakdown = [
        schemas.AccountTypeItem(account_type=acc_type, count=cnt)
        for acc_type, cnt in sorted(acc_type_counter.items(), key=lambda x: -x[1])
    ]

    return schemas.HouseholdInsightsResponse(
        household_id=hh.id,
        household_name=hh.name,
        total_accounts=len(hh.accounts),
        total_members=len(hh.members),
        account_type_breakdown=account_type_breakdown,
        estimated_liquid_net_worth=hh.estimated_liquid_net_worth,
        estimated_total_net_worth=hh.estimated_total_net_worth,
        annual_income=hh.annual_income,
        risk_tolerance=hh.risk_tolerance,
        time_horizon=hh.time_horizon,
        primary_investment_objective=hh.primary_investment_objective,
    )
