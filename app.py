"""
app.py — Mortgage & Rental Analyzer
=====================================
Run:  uv run streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from mortgage_engine import (
    LoanParams, CostParams, RentalParams,
    build_schedule, to_yearly, find_milestones,
    break_even_rent, summary_stats,
)

# ── Page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mortgage & Rental Analyzer",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
section[data-testid="stSidebar"] { min-width: 300px; max-width: 320px; }
[data-testid="stMetric"] { background: #1c2333; border-radius: 8px; padding: 12px 16px; }
[data-testid="stMetricLabel"] { font-size: 11px !important; letter-spacing: 0.1em; text-transform: uppercase; }
[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
button[data-baseweb="tab"] { font-size: 13px; font-weight: 600; letter-spacing: 0.04em; }
hr { border-color: #2a3450; margin: 8px 0; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 🏠 Mortgage & Rental Analyzer")
    st.caption("Adjust any input — tables and charts update instantly.")
    st.divider()

    # ── Loan details ───────────────────────────────────────────────
    st.markdown("**Loan Details**")
    home_price = st.number_input(
        "Home price ($)", min_value=50_000, max_value=5_000_000,
        value=359_000, step=1_000, format="%d",
    )
    down_pmt = st.number_input(
        "Down payment ($)", min_value=0, max_value=int(home_price),
        value=100_000, step=1_000, format="%d",
    )
    loan_amount = home_price - down_pmt
    st.caption(f"Loan amount: **${loan_amount:,.0f}** ({down_pmt/home_price*100:.1f}% down)")

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        rate_15 = st.number_input("15-yr rate (%)", 2.0, 12.0, 6.10, 0.05, format="%.2f")
    with col_r2:
        rate_30 = st.number_input("30-yr rate (%)", 2.0, 12.0, 6.30, 0.05, format="%.2f")

    def _pi(loan, rate, n):
        mr = rate / 100 / 12
        return loan * mr * (1 + mr)**n / ((1 + mr)**n - 1)

    pi15 = _pi(loan_amount, rate_15, 180)
    pi30 = _pi(loan_amount, rate_30, 360)
    st.caption(f"15-yr P&I: **${pi15:,.0f}/mo** · 30-yr P&I: **${pi30:,.0f}/mo**")

    st.divider()

    # ── Fixed costs ────────────────────────────────────────────────
    st.markdown("**Fixed Monthly Costs**")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        prop_tax  = st.number_input("Property tax", 0, 10_000, 568, 1, format="%d")
        hoa       = st.number_input("HOA", 0, 5_000, 0, 1, format="%d")
    with col_c2:
        insurance = st.number_input("Insurance", 0, 10_000, 257, 1, format="%d")

    st.divider()

    # ── Extra principal ────────────────────────────────────────────
    st.markdown("**Extra Principal Payments**")
    extra_30 = st.slider("30-yr extra / mo ($)", 0, 2_000, 625, 25)
    extra_15 = st.slider("15-yr extra / mo ($)", 0, 1_000, 0, 25)

    with st.expander("One-time lump sum (30-yr)"):
        lump_sum       = st.number_input("Lump sum ($)", 0, 500_000, 0, 1_000, format="%d")
        lump_sum_month = st.number_input("Apply at month #", 1, 360, 1, 1, format="%d")

    st.divider()

    # ── Rental ────────────────────────────────────────────────────
    st.markdown("**Rental Income**")
    rent          = st.number_input("Monthly rent ($)", 0, 20_000, 2_800, 50, format="%d")
    vacancy_rate  = st.slider("Vacancy rate (%)", 0, 25, 8, 1) / 100
    mgmt_fee_rate = st.slider("Mgmt fee (%)", 0.0, 20.0, 10.0, 0.5) / 100
    maint_pct     = st.slider("Maintenance (% home value/yr)", 0.0, 3.0, 1.0, 0.25) / 100

    eff_rent = rent * (1 - vacancy_rate)
    st.caption(f"Effective rent (after vacancy): **${eff_rent:,.0f}/mo**")

    st.markdown("**Rental Period**")
    rental_start_year = st.number_input(
        "Renting starts at year #", min_value=1, max_value=30, value=1, step=1,
        help="Set to 1 to rent from day one. Set to 5 if you live there 4 years first.",
    )
    if rental_start_year > 1:
        st.caption(f"Years 1–{rental_start_year - 1}: owner-occupied · Year {rental_start_year}+: rental")
    else:
        st.caption("Renting from month 1")

    st.divider()

    # ── Display options ────────────────────────────────────────────
    st.markdown("**Table Options**")
    granularity = st.radio("Row granularity", ["Monthly", "Yearly"], horizontal=True)

    show_cols = st.multiselect(
        "Extra columns to show",
        ["Insurance", "HOA", "Maintenance", "Equity Built", "True Net (CF + Equity)"],
        default=[],
    )


# ══════════════════════════════════════════════════════════════════
# BUILD SCHEDULES
# ══════════════════════════════════════════════════════════════════

costs  = CostParams(prop_tax, insurance, hoa)
rental = RentalParams(rent, vacancy_rate, mgmt_fee_rate, maint_pct)

loan15 = LoanParams(home_price, down_pmt, rate_15 / 100, 180, extra_15)
loan30 = LoanParams(home_price, down_pmt, rate_30 / 100, 360, extra_30,
                    lump_sum, lump_sum_month)

@st.cache_data
def get_schedule(hp, dp, rate, term, extra, lump, lump_mo,
                 tax, ins, hoa_v, rent_v, vac, mgmt, maint, rent_start_yr):
    lp = LoanParams(hp, dp, rate / 100, term, extra, lump, lump_mo)
    cp = CostParams(tax, ins, hoa_v)
    rp = RentalParams(rent_v, vac, mgmt, maint)
    rows = build_schedule(lp, cp, rp)
    # Zero out rental income and costs for years before rental_start_year
    for r in rows:
        if r.year < rent_start_yr:
            r.effective_rent = 0.0
            r.mgmt_fee       = 0.0
            r.maintenance    = 0.0
            # Recalculate net CF and true net without rental
            r.net_cash_flow  = -(r.total_payment + cp.total_fixed_monthly)
            r.true_net       = r.net_cash_flow + r.equity_built
    return rows

rows15 = get_schedule(home_price, down_pmt, rate_15, 180, extra_15,
                      0, 1, prop_tax, insurance, hoa,
                      rent, vacancy_rate, mgmt_fee_rate, maint_pct,
                      rental_start_year)

rows30 = get_schedule(home_price, down_pmt, rate_30, 360, extra_30,
                      lump_sum, lump_sum_month, prop_tax, insurance, hoa,
                      rent, vacancy_rate, mgmt_fee_rate, maint_pct,
                      rental_start_year)

stats15 = summary_stats(rows15, loan15)
stats30 = summary_stats(rows30, loan30)
be15    = break_even_rent(loan15, costs, rental)
be30    = break_even_rent(loan30, costs, rental)
mil15   = find_milestones(rows15)
mil30   = find_milestones(rows30)


# ══════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════════

def rows_to_df(rows, yearly=False):
    data = to_yearly(rows) if yearly else rows
    records = []
    for r in data:
        label = f"Year {r.year}" if yearly else f"M{r.month:03d} · Y{r.year}"
        # Total Payment now includes P&I + extra + tax + insurance + HOA
        total_all_in = r.total_payment + r.property_tax + r.insurance + r.hoa
        rec = {
            "Period":          label,
            "Base P&I":        r.base_payment,
            "Principal":       r.principal,
            "Interest":        r.interest,
            "Extra Prin.":     r.extra_principal,
            "Tax":             r.property_tax,
            # Total Payment = P&I + extra + tax + insurance + HOA
            "Total Payment":   total_all_in,
            "Balance":         r.balance,
            "Equity":          r.equity,
            "Equity %":        r.equity_pct,
            "Cumul. Interest": r.cumul_interest,
            "Eff. Rent":       r.effective_rent,
            "Mgmt Fee":        r.mgmt_fee,
            "Net CF":          r.net_cash_flow,
        }
        if "Insurance" in show_cols:
            rec["Insurance"] = r.insurance
        if "HOA" in show_cols:
            rec["HOA"] = r.hoa
        if "Maintenance" in show_cols:
            rec["Maintenance"] = r.maintenance
        if "Equity Built" in show_cols:
            rec["Equity Built"] = r.equity_built
        if "True Net (CF + Equity)" in show_cols:
            rec["True Net"] = r.true_net
        records.append(rec)
    return pd.DataFrame(records)


def style_df(df: pd.DataFrame):
    """Apply conditional formatting."""
    money_cols = [c for c in df.columns if c not in ("Period", "Equity %")]
    pct_cols   = ["Equity %"]
    fmt_map    = {c: "${:,.0f}" for c in money_cols}
    fmt_map.update({c: "{:.1f}%" for c in pct_cols})

    def color_net(val):
        if isinstance(val, (int, float)):
            return "color: #4ade80" if val >= 0 else "color: #f87171"
        return ""

    def color_extra(val):
        if isinstance(val, (int, float)) and val > 0:
            return "color: #4ade80"
        return "color: #6b7fa8"

    def color_rent(val):
        if isinstance(val, (int, float)):
            return "color: #4ade80" if val > 0 else "color: #6b7fa8"
        return ""

    styler = df.style.format(fmt_map, na_rep="—")
    if "Net CF" in df.columns:
        styler = styler.map(color_net, subset=["Net CF"])
    if "Extra Prin." in df.columns:
        styler = styler.map(color_extra, subset=["Extra Prin."])
    if "True Net" in df.columns:
        styler = styler.map(color_net, subset=["True Net"])
    if "Eff. Rent" in df.columns:
        styler = styler.map(color_rent, subset=["Eff. Rent"])
    return styler


def kpi_row(stats, be, loan, label_color):
    ncf     = stats["avg_net_cf"]
    surplus = rent - be
    cols    = st.columns(6)
    cols[0].metric("Monthly P&I",      f"${stats['base_payment']:,.0f}")
    cols[1].metric("Total Interest",   f"${stats['total_interest']:,.0f}")
    cols[2].metric("Total Cost",       f"${stats['total_cost']:,.0f}")
    cols[3].metric("Payoff",
                   f"{stats['total_months']} mo",
                   f"{stats['payoff_year']}")
    cols[4].metric("Avg Net CF / mo",
                   f"{'+'if ncf>=0 else ''}{ncf:,.0f}",
                   "positive" if ncf >= 0 else "negative",
                   delta_color="normal" if ncf >= 0 else "inverse")
    cols[5].metric("Break-even Rent",
                   f"${be:,.0f}",
                   f"{'+'if surplus>=0 else ''}{surplus:,.0f} vs target",
                   delta_color="normal" if surplus >= 0 else "inverse")


def equity_chart(rows15, rows30):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[r.month for r in rows15], y=[r.equity_pct for r in rows15],
        name="15-yr", mode="lines", line=dict(color="#38bdf8", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=[r.month for r in rows30], y=[r.equity_pct for r in rows30],
        name="30-yr", mode="lines", line=dict(color="#a78bfa", width=2)
    ))
    for pct in [50, 75, 90]:
        fig.add_hline(y=pct, line_dash="dot", line_color="#2a3450",
                      annotation_text=f"{pct}%", annotation_position="left",
                      annotation_font_color="#6b7fa8")
    if rental_start_year > 1:
        fig.add_vline(
            x=(rental_start_year - 1) * 12,
            line_dash="dash", line_color="#fbbf24",
            annotation_text=f"Rental start (Y{rental_start_year})",
            annotation_font_color="#fbbf24",
        )
    fig.update_layout(
        title="Equity % Over Time",
        xaxis_title="Month", yaxis_title="Equity %",
        yaxis=dict(range=[0, 105]),
        plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
        font=dict(color="#e2e8f8", size=11),
        legend=dict(bgcolor="#1c2333", bordercolor="#2a3450"),
        margin=dict(t=40, b=30, l=10, r=10), height=320,
    )
    return fig


def interest_breakdown_chart(stats15, stats30):
    fig = go.Figure(data=[
        go.Bar(name="Principal", x=["15-Year", "30-Year"],
               y=[loan_amount, loan_amount], marker_color="#1e4a6e"),
        go.Bar(name="Interest",  x=["15-Year", "30-Year"],
               y=[stats15["total_interest"], stats30["total_interest"]],
               marker_color=["#38bdf8", "#a78bfa"]),
    ])
    fig.update_layout(
        barmode="stack", title="Total Cost Breakdown", yaxis_title="$",
        plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
        font=dict(color="#e2e8f8", size=11),
        legend=dict(bgcolor="#1c2333"),
        margin=dict(t=40, b=30, l=10, r=10), height=320,
    )
    return fig


# ══════════════════════════════════════════════════════════════════
# MAIN TABS
# ══════════════════════════════════════════════════════════════════

tab15, tab30, tab_cmp = st.tabs([
    "📘  15-Year Mortgage",
    "📙  30-Year Mortgage",
    "⚖️  Compare",
])

yearly = (granularity == "Yearly")

# ── TAB 15 ────────────────────────────────────────────────────────
with tab15:
    st.markdown(f"#### 15-Year Fixed · {rate_15:.2f}% · ${pi15:,.0f}/mo base P&I")
    kpi_row(stats15, be15, loan15, "#38bdf8")
    st.divider()

    # Milestones
    st.markdown("**Equity Milestones**")
    mil_cols = st.columns(len(mil15)) if mil15 else st.columns(1)
    for i, (pct, mo) in enumerate(mil15.items()):
        yr = 2026 + (mo - 1) // 12
        mil_cols[i].success(f"**{pct}% equity** — Month {mo} ({yr})")

    st.divider()
    df15 = rows_to_df(rows15, yearly)
    st.dataframe(style_df(df15), use_container_width=True, hide_index=True, height=520)


# ── TAB 30 ────────────────────────────────────────────────────────
with tab30:
    extra_note = f" + ${extra_30:,}/mo extra" if extra_30 > 0 else ""
    lump_note  = f" + ${lump_sum:,} lump @ M{lump_sum_month}" if lump_sum > 0 else ""
    st.markdown(f"#### 30-Year Fixed · {rate_30:.2f}% · ${pi30:,.0f}/mo base P&I{extra_note}{lump_note}")
    kpi_row(stats30, be30, loan30, "#a78bfa")
    st.divider()

    # Milestones
    st.markdown("**Equity Milestones**")
    mil_cols = st.columns(len(mil30)) if mil30 else st.columns(1)
    for i, (pct, mo) in enumerate(mil30.items()):
        yr = 2026 + (mo - 1) // 12
        mil_cols[i].info(f"**{pct}% equity** — Month {mo} ({yr})")

    st.divider()
    df30 = rows_to_df(rows30, yearly)
    st.dataframe(style_df(df30), use_container_width=True, hide_index=True, height=520)


# ── TAB COMPARE ───────────────────────────────────────────────────
with tab_cmp:
    st.markdown("#### Side-by-Side Comparison")

    int_diff  = stats30["total_interest"] - stats15["total_interest"]
    cost_diff = stats30["total_cost"]     - stats15["total_cost"]
    mo_diff   = stats30["total_months"]   - stats15["total_months"]
    pmt_diff  = (pi30 + extra_30) - (pi15 + extra_15)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Interest difference",
              f"${abs(int_diff):,.0f}",
              f"30-yr pays {'more' if int_diff>0 else 'less'}",
              delta_color="inverse" if int_diff > 0 else "normal")
    c2.metric("Total cost difference",
              f"${abs(cost_diff):,.0f}",
              f"30-yr costs {'more' if cost_diff>0 else 'less'}",
              delta_color="inverse" if cost_diff > 0 else "normal")
    c3.metric("Payoff difference",
              f"{abs(mo_diff)} months",
              f"30-yr {'later' if mo_diff>0 else 'earlier'}",
              delta_color="inverse" if mo_diff > 0 else "normal")
    c4.metric("Monthly pmt difference",
              f"${abs(pmt_diff):,.0f}/mo",
              f"30-yr {'cheaper' if pmt_diff<0 else 'pricier'} (flexibility)",
              delta_color="normal" if pmt_diff < 0 else "inverse")

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(equity_chart(rows15, rows30), use_container_width=True)
    with col_b:
        st.plotly_chart(interest_breakdown_chart(stats15, stats30), use_container_width=True)

    st.divider()

    st.markdown("**Detailed Comparison**")
    ncf15 = stats15["avg_net_cf"]
    ncf30 = stats30["avg_net_cf"]
    cmp_data = {
        "Metric": [
            "Loan Amount", "Base Monthly P&I", "Extra / mo", "Total Monthly (P&I+extra)",
            "Total Interest", "Total Cost (home+interest)",
            "Payoff Months", "Payoff Year",
            "Avg Net CF / mo", "Break-even Rent",
            "Rental starts", "50% Equity", "75% Equity", "90% Equity",
            "Payment Flexibility",
        ],
        "15-Year": [
            f"${loan_amount:,.0f}", f"${pi15:,.0f}", f"${extra_15:,.0f}",
            f"${pi15+extra_15:,.0f}",
            f"${stats15['total_interest']:,.0f}", f"${stats15['total_cost']:,.0f}",
            stats15["total_months"], stats15["payoff_year"],
            f"{'+'if ncf15>=0 else ''}{ncf15:,.0f}",
            f"${be15:,.0f}",
            f"Year {rental_start_year}",
            f"M{mil15.get(50,'—')} ({2026+(mil15.get(50,0)-1)//12 if 50 in mil15 else '—'})",
            f"M{mil15.get(75,'—')} ({2026+(mil15.get(75,0)-1)//12 if 75 in mil15 else '—'})",
            f"M{mil15.get(90,'—')} ({2026+(mil15.get(90,0)-1)//12 if 90 in mil15 else '—'})",
            f"Fixed ${pi15+extra_15:,.0f}/mo",
        ],
        "30-Year": [
            f"${loan_amount:,.0f}", f"${pi30:,.0f}", f"${extra_30:,.0f}",
            f"${pi30+extra_30:,.0f}",
            f"${stats30['total_interest']:,.0f}", f"${stats30['total_cost']:,.0f}",
            stats30["total_months"], stats30["payoff_year"],
            f"{'+'if ncf30>=0 else ''}{ncf30:,.0f}",
            f"${be30:,.0f}",
            f"Year {rental_start_year}",
            f"M{mil30.get(50,'—')} ({2026+(mil30.get(50,0)-1)//12 if 50 in mil30 else '—'})",
            f"M{mil30.get(75,'—')} ({2026+(mil30.get(75,0)-1)//12 if 75 in mil30 else '—'})",
            f"M{mil30.get(90,'—')} ({2026+(mil30.get(90,0)-1)//12 if 90 in mil30 else '—'})",
            f"Drop to ${pi30:,.0f}/mo anytime",
        ],
    }
    st.dataframe(pd.DataFrame(cmp_data), use_container_width=True, hide_index=True)