# Risk Management Framework

> **FICTIONAL SAMPLE DATA - for RAG testing only**

- **Title:** Risk Management Framework
- **Doc ID:** INV-RMF-001
- **Version:** 2.0
- **Effective date:** 2026-04-01
- **Owner:** Risk Function (Chief Risk Officer: Dmitri Vasquez), Halvorsen Ridge Capital Management LLC
- **Approved by:** Investment Committee, 2026-03-17
- **Status:** Current (supersedes version 1.0 dated 2025-02-01)

## 1. Purpose and Scope

This Risk Management Framework ("the Framework") defines how Halvorsen Ridge Capital Management LLC ("HRCM") identifies, measures, limits, monitors and reports market, liquidity and counterparty risk in the pooled funds it manages: the Halvorsen Ridge Global Equity Fund (HRGE), the Halvorsen Ridge Short Duration Bond Fund (HRSD) and the Halvorsen Ridge Sustainable Infrastructure Fund (HRSI). The Framework also applies to separately managed accounts unless the client's investment management agreement specifies different limits.

The Framework is the single authoritative source for quantitative market risk limits at HRCM. Other documents, including fund factsheets, market commentary and the Investment Policy Statement (INV-IPS-001), may refer to risk limits but do not set them. **If any other document states a different number, this Framework prevails.**

## 2. Risk Governance

### 2.1 Risk Committee

The Risk Committee is chaired by the Chief Risk Officer (CRO) and includes the Chief Investment Officer, the Chief Operating Officer, the Chief Compliance Officer and the Head of Quantitative Research. It meets **monthly, on the second Tuesday of each month**, and reports to the Investment Committee quarterly.

The Risk Committee is responsible for:

- Proposing changes to this Framework for Investment Committee approval.
- Reviewing daily and monthly risk reports, limit utilization and breaches.
- Approving stress scenarios and model changes.
- Overseeing the independent validation of risk models.

### 2.2 Independence

The Risk function is independent of portfolio management. The CRO reports to the Chief Executive Officer and has a direct line to the Chair of the Board. Risk staff compensation is not linked to fund performance.

### 2.3 Three Lines Model

| Line | Who | Role |
|---|---|---|
| First line | Portfolio managers and traders | Own and manage risk within limits |
| Second line | Risk and Compliance | Set limits, monitor, challenge and escalate |
| Third line | Internal Audit | Independently assure the effectiveness of controls |

## 3. Risk Measurement

### 3.1 Value-at-Risk (VaR)

VaR is calculated **daily** for every fund using a historical simulation model with a **two-year (500 business day) lookback window**, a **99% confidence level** and a **one-day horizon**. Positions are revalued fully rather than approximated with sensitivities, except for exchange-traded options where a delta-gamma approximation is used.

VaR is calculated on the end-of-day positions and is available in the risk dashboard by 08:00 Central Time the following business day.

### 3.2 Expected Shortfall (ES)

Expected Shortfall is the average loss in the scenarios beyond the VaR threshold. From version 2.0 of this Framework, HRCM calculates **1-day 97.5% Expected Shortfall** in addition to VaR, because ES better captures tail risk and is less sensitive to the exact shape of the loss distribution near the threshold.

### 3.3 Stress Testing

Stress tests are run **weekly** (increased from monthly in version 1.0) on all funds. The standard scenario set includes:

| Scenario | Type | Description |
|---|---|---|
| GFC 2008 | Historical | September–November 2008 market moves |
| COVID-19 March 2020 | Historical | 19 February – 23 March 2020 market moves |
| Rates shock 2022 | Historical | Simultaneous equity and bond decline of 2022 |
| Parallel +200 bp | Hypothetical | Instantaneous parallel shift of +200 basis points in all yield curves |
| Credit spread widening | Hypothetical | Investment-grade spreads +150 bp, high yield +500 bp |
| EM currency crisis | Hypothetical | EM currencies −25% versus USD |

The Risk Committee reviews the scenario set at least annually. A stress test result that shows a projected loss greater than **20% of NAV for an equity fund or 6% of NAV for a fixed income fund** must be escalated to the CRO the same day, although it is not by itself a limit breach.

### 3.4 Interest Rate Sensitivity

For fixed income funds, interest rate risk is also measured as DV01, the change in fund value for a one basis point parallel move in yields.

## 4. Market Risk Limits

### 4.1 VaR and Expected Shortfall Limits

| Fund type | 1-day 99% VaR hard limit (% of NAV) | 1-day 97.5% ES hard limit (% of NAV) |
|---|---|---|
| Equity funds (HRGE, HRSI) | **2.0%** | **2.8%** |
| Fixed income funds (HRSD) | **0.8%** | **1.1%** |

**Firm-wide aggregate VaR limit:** **USD 110 million** (1-day, 99%), measured across all pooled funds and separately managed accounts on a diversified basis.

### 4.2 Amber (Soft) Limits

Each hard limit has an amber (soft) threshold set at **80% of the hard limit**. For example, the amber threshold for equity fund VaR is 1.6% of NAV. Reaching an amber threshold is not a breach, but the portfolio manager must document the reason and the expected path back below the threshold in the risk system within 2 business days.

### 4.3 Interest Rate Limits

| Fund | Limit |
|---|---|
| HRSD | DV01 must not exceed **USD 420,000 per basis point** |
| HRSD | Effective duration must remain between 1 and 3 years |

### 4.4 Tracking Error

Ex-ante tracking error is monitored daily against each fund's target range (for HRGE, 3% to 6% annualized). Tracking error outside the target range for 10 consecutive business days triggers a review by the Risk Committee but is not a hard limit breach.

## 5. Drawdown Rules

Drawdown is measured as the decline in a fund's NAV per share from its trailing 12-month peak, **relative to the decline in its benchmark** over the same period. For example, if a fund falls 14% from its peak while its benchmark falls 3%, the relative drawdown is 11%.

| Relative drawdown | Required action |
|---|---|
| Greater than **10%** | Mandatory review by the Risk Committee within 5 business days |
| Greater than **15%** | Mandatory de-risking plan submitted to the Investment Committee within 10 business days |

A de-risking plan must state the target reduction in VaR, the timeline and the instruments to be used. The Investment Committee may approve, amend or reject the plan.

## 6. Limit Monitoring and Breach Escalation

### 6.1 Monitoring

Risk monitors all limits daily. Limit utilization is shown in the daily risk dashboard with a traffic-light status: green (below amber threshold), amber (between amber threshold and hard limit) and red (hard limit breached).

### 6.2 Escalation of Hard Limit Breaches

1. The Risk analyst notifies the portfolio manager immediately on detection.
2. The **Chief Risk Officer must be notified within 1 business day** of the breach (shortened from 2 business days in version 1.0).
3. The portfolio manager submits a remediation plan within 3 business days.
4. The breach is reported to the Risk Committee at its next monthly meeting and to the Investment Committee at its next quarterly meeting.
5. If a breach is not remediated within 10 business days, the CRO may instruct trades to reduce risk directly, with notice to the CIO.

### 6.3 Breach Log

All amber events and hard limit breaches are recorded in the breach log, including the cause, the actions taken and the time to resolution. The log is reviewed by Internal Audit annually.

## 7. Liquidity Risk

### 7.1 Liquidity Requirements

- At least 85% of each fund's assets must be capable of being liquidated within 7 calendar days (consistent with INV-IPS-001).
- Illiquid investments may not exceed 15% of net assets.
- Each fund must hold a **liquidity buffer of at least 7% of NAV** (increased from 5% in version 1.0) in cash or instruments that settle within two business days.

### 7.2 Redemption Stress Testing

Funds are tested monthly against a redemption scenario in which the three largest investors redeem in full on the same day, alongside a market-wide stress. If the fund could not meet the scenario without breaching the liquidity buffer, Risk will notify the CIO and the portfolio manager.

## 8. Counterparty Risk

Over-the-counter derivative and securities lending counterparties must have a minimum long-term credit rating of A− (or equivalent) at the time of trading. Net exposure to any single counterparty, after collateral, may not exceed 5% of a fund's NAV. Collateral is exchanged daily with a minimum transfer amount of USD 250,000.

## 9. Model Risk and Back-Testing

### 9.1 Back-Testing

The VaR model is back-tested daily by comparing each day's predicted 99% VaR to the actual profit or loss. An exception occurs when the actual loss exceeds the predicted VaR. The number of exceptions over the most recent 250 business days is classified as follows:

| Exceptions in 250 days | Zone | Action |
|---|---|---|
| 0 – 4 | Green | No action |
| 5 – 9 | Amber | Model review by Quantitative Research within 30 days |
| 10 or more | Red | Model suspended for limit purposes; Risk Committee must approve interim methodology |

### 9.2 Independent Validation

The VaR and ES models are validated by an independent external party **every two years**, and after any material change to methodology. Validation findings are tracked to closure by the Risk Committee.

## 10. Risk Reporting

| Report | Frequency | Audience |
|---|---|---|
| Risk dashboard (VaR, ES, limits, exposures) | Daily | Portfolio managers, Risk, CIO |
| Stress test report | Weekly | Portfolio managers, Risk Committee |
| Risk Committee pack | Monthly | Risk Committee |
| Investment Committee risk report | Quarterly | Investment Committee |
| Board risk summary | Semi-annually | Board of Directors |

## 11. Roles of Specific Functions

### 11.1 Chief Risk Officer

The CRO, currently Dmitri Vasquez, owns this Framework, chairs the Risk Committee, approves amber limit exceptions of up to 30 days and has authority to instruct risk-reducing trades as described in Section 6.2.

### 11.2 Portfolio Managers

Portfolio managers are expected to manage their funds so that limit utilization normally stays below the amber threshold. Repeated amber events (more than three in a calendar quarter for the same fund) are discussed at the Risk Committee.

### 11.3 Quantitative Research

The Quantitative Research team maintains the risk models, the scenario library and the back-testing process.

## 12. Exceptions

Temporary exceptions to hard limits may be granted only by the Investment Committee, on the recommendation of the CRO, for a maximum of 30 calendar days. Exceptions must be documented in the breach log.

## 13. Review

This Framework is reviewed annually by the Risk Committee and approved by the Investment Committee. Interim changes may be made when market conditions or regulation require it.

## 14. Summary of Changes from Version 1.0

| Item | Version 1.0 (2025-02-01) | Version 2.0 (2026-04-01) |
|---|---|---|
| Equity fund 1-day 99% VaR limit | 2.5% of NAV | **2.0% of NAV** |
| Fixed income fund 1-day 99% VaR limit | 0.8% of NAV | 0.8% of NAV (unchanged) |
| Firm-wide aggregate VaR limit | USD 95 million | **USD 110 million** |
| Expected Shortfall limit | Not used | Introduced (2.8% equity, 1.1% fixed income) |
| Drawdown review trigger | 12% relative drawdown | **10%** relative drawdown |
| Drawdown de-risking trigger | 18% relative drawdown | **15%** relative drawdown |
| Stress testing frequency | Monthly | **Weekly** |
| CRO notification of hard breach | Within 2 business days | **Within 1 business day** |
| Liquidity buffer | 5% of NAV | **7% of NAV** |
| Independent model validation | Annually | Every two years |

The increase in the firm-wide VaR limit reflects growth in assets under management rather than an increase in risk appetite; on a percentage-of-AUM basis, the firm-wide limit is lower than in version 1.0.

## Appendix A — VaR Methodology Details

### A.1 Data and Scenarios

The historical simulation uses the most recent 500 business days of daily risk factor changes. Risk factors include equity prices (single names and indices), government yield curves at 12 tenor points, credit spread curves by rating and sector, foreign exchange rates against USD and implied volatilities for listed options. Missing data for newly listed securities are proxied using a sector-and-region index with an idiosyncratic volatility add-on approved by Quantitative Research.

### A.2 Weighting

Scenarios are equally weighted. The Risk Committee considered exponentially weighted scenarios during the version 2.0 review but rejected them because they produced unstable limit utilization for the equity funds during volatile periods.

### A.3 Aggregation

Fund-level VaR is calculated on the full fund portfolio. Firm-wide VaR is calculated by aggregating the scenario profit and loss vectors of all funds and separately managed accounts, so diversification across portfolios is captured. The sum of standalone fund VaRs is reported alongside the diversified firm-wide figure for information.

### A.4 Known Limitations

- Historical simulation cannot capture events that are absent from the lookback window.
- The one-day horizon does not reflect the time needed to liquidate less liquid positions; this is addressed by the liquidity requirements in Section 7.
- VaR says nothing about the size of losses beyond the confidence level; this is why Expected Shortfall was introduced in version 2.0.

## Appendix B — Worked Example of a Hard Limit Breach

On a given day, the Halvorsen Ridge Global Equity Fund (HRGE) reports a 1-day 99% VaR of 2.12% of NAV, above the 2.0% hard limit for equity funds. The following steps apply:

1. The Risk analyst identifies the breach in the morning risk dashboard at 08:00 Central Time and notifies the lead portfolio manager by phone and email.
2. The CRO is notified the same day, which satisfies the requirement to notify within 1 business day.
3. The portfolio manager identifies that the breach is driven by a concentrated semiconductor position and higher market volatility, and submits a remediation plan within 3 business days, proposing to reduce the position and add an index futures hedge within the derivatives limits of INV-IPS-001.
4. VaR falls to 1.74% of NAV within four business days. Because 1.74% is above the amber threshold of 1.6%, the fund remains in amber status and the manager documents the expected path back to green.
5. The event is recorded in the breach log and presented at the next monthly Risk Committee meeting.

Under version 1.0 of the Framework, the same VaR figure of 2.12% would not have been a breach, because the equity fund limit was then 2.5% of NAV.

## Appendix C — Glossary of Risk Terms Used in this Framework

- **Hard limit:** A limit that must not be exceeded; exceeding it is a breach requiring escalation.
- **Amber threshold:** 80% of a hard limit; reaching it requires documentation but is not a breach.
- **Relative drawdown:** Fund drawdown from its trailing 12-month peak minus benchmark drawdown over the same period.
- **DV01:** Dollar value of a one basis point move in yields.
- **Exception (back-testing):** A day on which the actual loss exceeds the predicted VaR.

For general investment terms, see the Investment Glossary (INV-GLO-001).
