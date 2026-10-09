# On-call and SLA Policy

> **FICTIONAL SAMPLE DATA - for RAG testing only**

- **Title:** On-call and SLA Policy
- **Doc ID:** TECH-ONC-001
- **Version:** 3.0
- **Effective date:** 2026-03-01
- **Owner:** Site Reliability Engineering (Head of SRE: Beatriz Holm), Lumenvale Technologies Inc.
- **Status:** Current

## 1. Scope

This policy applies to all engineering teams at Lumenvale Technologies Inc. that operate production services, including the Lumenvale Data Platform and the Lumenvale Insights API.

## 2. Severity Levels

| Severity | Definition | Example |
|---|---|---|
| Sev1 | Complete outage of a customer-facing service or confirmed data breach | Insights API returning errors for all customers |
| Sev2 | Major degradation, or a tier-1 data SLO at risk | Bronze ingestion halted by schema drift; Gold freshness SLO at risk |
| Sev3 | Minor degradation with a workaround | Single non-critical job failing, late source file |
| Sev4 | Cosmetic issue or question with no customer impact | Dashboard label wrong |

## 3. Response and Resolution Targets

| Severity | Acknowledge within | Status updates | Target resolution |
|---|---|---|---|
| Sev1 | **5 minutes** | Every 30 minutes | 4 hours |
| Sev2 | **15 minutes** | Every 60 minutes | 8 hours |
| Sev3 | **4 business hours** | Daily | 3 business days |
| Sev4 | **2 business days** | As needed | Best effort |

## 4. Escalation

If a Sev1 page is not acknowledged within **10 minutes**, PagerDuty escalates to the secondary on-call. If it is still not acknowledged after **20 minutes**, it escalates to the engineering manager for the service. For Sev2, the same escalation applies after 30 and 45 minutes respectively.

## 5. Rotations

- Rotations are weekly, with handoff every **Monday at 09:00 UTC**.
- Each service has a primary and a secondary on-call.
- Engineers may not be primary on-call for more than one week in any four-week period.
- On-call engineers receive a stipend of **USD 400 per week** of primary on-call and USD 150 per week of secondary on-call.

## 6. Service Level Agreements and Objectives

| Service | Commitment | Type |
|---|---|---|
| Lumenvale Insights API (external) | **99.9% monthly availability** | Contractual SLA |
| Lumenvale Data Platform (internal) | 99.5% monthly availability | Internal SLO |
| Gold daily tables | Fresh by 06:00 UTC | Internal SLO |

### 6.1 Service Credits (Insights API)

| Monthly availability | Service credit (% of monthly fee) |
|---|---|
| Below 99.9% but at least 99.0% | 10% |
| Below 99.0% but at least 95.0% | 25% |
| Below 95.0% | 50% |

Customers must request credits within 30 days of the end of the affected month. Scheduled maintenance announced at least 72 hours in advance is excluded from availability calculations.

## 7. Postmortems

A blameless postmortem is required for every **Sev1 and Sev2** incident and must be published within **5 business days** of resolution. Action items are tracked in Jira with an owner and due date; Sev1 action items must be completed within 30 days.
