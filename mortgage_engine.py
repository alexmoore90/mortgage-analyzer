"""
mortgage_engine.py
──────────────────
Pure-Python calculation engine. No Streamlit imports — fully testable in isolation.
All monetary values in USD. Rates as decimals (e.g. 0.063 for 6.3%).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


# ── Input dataclasses ──────────────────────────────────────────────────────────

@dataclass
class LoanParams:
    home_price: float
    down_payment: float
    annual_rate: float
    term_months: int          # 180 or 360
    extra_monthly: float = 0.0
    lump_sum: float = 0.0
    lump_sum_month: int = 1

    @property
    def loan_amount(self) -> float:
        return self.home_price - self.down_payment

    @property
    def monthly_rate(self) -> float:
        return self.annual_rate / 12

    @property
    def base_payment(self) -> float:
        """Standard P&I payment with no extra principal."""
        mr = self.monthly_rate
        n  = self.term_months
        return self.loan_amount * mr * (1 + mr) ** n / ((1 + mr) ** n - 1)


@dataclass
class CostParams:
    property_tax_monthly: float = 568.0
    insurance_monthly: float    = 257.0
    hoa_monthly: float          = 0.0

    @property
    def total_fixed_monthly(self) -> float:
        return self.property_tax_monthly + self.insurance_monthly + self.hoa_monthly


@dataclass
class RentalParams:
    monthly_rent: float         = 2800.0
    vacancy_rate: float         = 0.08    # 8%
    mgmt_fee_rate: float        = 0.10    # 10% of effective rent
    maintenance_pct: float      = 0.01    # 1% of home value / year

    def effective_rent(self) -> float:
        return self.monthly_rent * (1 - self.vacancy_rate)

    def mgmt_fee(self) -> float:
        return self.effective_rent() * self.mgmt_fee_rate

    def maintenance_monthly(self, home_value: float) -> float:
        return home_value * self.maintenance_pct / 12


# ── Output dataclass ──────────────────────────────────────────────────────────

@dataclass
class AmortRow:
    # Period
    month: int
    year: int

    # Mortgage
    base_payment: float
    principal: float
    interest: float
    extra_principal: float
    total_payment: float       # base_payment + extra_principal
    balance: float
    equity: float
    equity_pct: float
    cumul_interest: float

    # Fixed costs
    property_tax: float
    insurance: float
    hoa: float

    # Rental
    effective_rent: float
    mgmt_fee: float
    maintenance: float

    # Net
    net_cash_flow: float       # eff_rent - total_payment - fixed - mgmt - maint
    equity_built: float        # principal + extra (monthly equity gain)
    true_net: float            # net_cash_flow + equity_built


# ── Engine ────────────────────────────────────────────────────────────────────

def build_schedule(
    loan: LoanParams,
    costs: CostParams,
    rental: RentalParams,
) -> List[AmortRow]:
    """Build a full monthly amortization schedule with rental overlay."""

    pi          = loan.base_payment
    mr          = loan.monthly_rate
    balance     = loan.loan_amount
    cumul_int   = 0.0
    rows: List[AmortRow] = []

    eff_rent    = rental.effective_rent()
    mgmt        = rental.mgmt_fee()
    maint       = rental.maintenance_monthly(loan.home_price)
    fixed       = costs.total_fixed_monthly

    for m in range(1, loan.term_months + 121):  # safety cap
        if balance <= 0.005:
            break

        interest  = balance * mr
        principal = min(pi - interest, balance)

        # Extra principal: lump sum on target month, recurring thereafter
        remaining = balance - principal
        extra = 0.0
        if m == loan.lump_sum_month and loan.lump_sum > 0:
            extra += min(loan.lump_sum, remaining)
        if m >= loan.lump_sum_month and loan.extra_monthly > 0:
            extra += min(loan.extra_monthly, remaining - extra)
        extra = max(0.0, extra)

        balance -= (principal + extra)
        balance = max(balance, 0.0)
        cumul_int += interest

        total_pmt   = pi + extra
        equity      = loan.home_price - balance
        equity_pct  = equity / loan.home_price * 100
        net_cf      = eff_rent - total_pmt - fixed - mgmt - maint
        equity_bld  = principal + extra
        true_net    = net_cf + equity_bld

        rows.append(AmortRow(
            month           = m,
            year            = (m - 1) // 12 + 1,
            base_payment    = pi,
            principal       = principal,
            interest        = interest,
            extra_principal = extra,
            total_payment   = total_pmt,
            balance         = balance,
            equity          = equity,
            equity_pct      = equity_pct,
            cumul_interest  = cumul_int,
            property_tax    = costs.property_tax_monthly,
            insurance       = costs.insurance_monthly,
            hoa             = costs.hoa_monthly,
            effective_rent  = eff_rent,
            mgmt_fee        = mgmt,
            maintenance     = maint,
            net_cash_flow   = net_cf,
            equity_built    = equity_bld,
            true_net        = true_net,
        ))

        if balance <= 0:
            break

    return rows


def to_yearly(rows: List[AmortRow]) -> List[AmortRow]:
    """
    Aggregate monthly rows into yearly summary rows.
    Uses end-of-year values for balance/equity, sums for flows.
    """
    from collections import defaultdict
    buckets: dict[int, list[AmortRow]] = defaultdict(list)
    for r in rows:
        buckets[r.year].append(r)

    yearly = []
    for yr, group in sorted(buckets.items()):
        last = group[-1]
        def s(attr): return sum(getattr(r, attr) for r in group)

        yearly.append(AmortRow(
            month           = last.month,
            year            = yr,
            base_payment    = s("base_payment"),
            principal       = s("principal"),
            interest        = s("interest"),
            extra_principal = s("extra_principal"),
            total_payment   = s("total_payment"),
            balance         = last.balance,
            equity          = last.equity,
            equity_pct      = last.equity_pct,
            cumul_interest  = last.cumul_interest,
            property_tax    = s("property_tax"),
            insurance       = s("insurance"),
            hoa             = s("hoa"),
            effective_rent  = s("effective_rent"),
            mgmt_fee        = s("mgmt_fee"),
            maintenance     = s("maintenance"),
            net_cash_flow   = s("net_cash_flow"),
            equity_built    = s("equity_built"),
            true_net        = s("true_net"),
        ))
    return yearly


def find_milestones(rows: List[AmortRow], pcts=(50, 75, 90)) -> dict[int, int]:
    """Return {equity_pct -> month} for first time each threshold is crossed."""
    result = {}
    for pct in pcts:
        hit = next((r for r in rows if r.equity_pct >= pct), None)
        if hit:
            result[pct] = hit.month
    return result


def break_even_rent(
    loan: LoanParams,
    costs: CostParams,
    rental: RentalParams,
) -> float:
    """Binary-search the minimum rent where monthly net CF >= 0."""
    pi      = loan.base_payment
    extra   = loan.extra_monthly
    fixed   = costs.total_fixed_monthly
    vac     = rental.vacancy_rate
    mgmt_r  = rental.mgmt_fee_rate
    maint   = rental.maintenance_monthly(loan.home_price)

    lo, hi = 0.0, 15_000.0
    for _ in range(40):
        mid = (lo + hi) / 2
        eff = mid * (1 - vac)
        mgmt = eff * mgmt_r
        net = eff - (pi + extra) - fixed - mgmt - maint
        if net >= 0:
            hi = mid
        else:
            lo = mid
    return round(hi, 2)


def summary_stats(rows: List[AmortRow], loan: LoanParams) -> dict:
    """Key summary numbers for KPI display."""
    last = rows[-1]
    total_extra = sum(r.extra_principal for r in rows)
    avg_net_cf  = sum(r.net_cash_flow for r in rows) / len(rows)
    return {
        "base_payment":    loan.base_payment,
        "total_months":    last.month,
        "payoff_year":     2026 + (last.month - 1) // 12,
        "total_interest":  last.cumul_interest,
        "total_cost":      loan.home_price + last.cumul_interest,
        "total_extra":     total_extra,
        "avg_net_cf":      avg_net_cf,
        "final_equity_pct": last.equity_pct,
    }
