# CI/CD and Release Process

> **FICTIONAL SAMPLE DATA - for RAG testing only**

- **Title:** CI/CD and Release Process
- **Doc ID:** TECH-CICD-001
- **Version:** 2.2
- **Effective date:** 2026-04-14
- **Owner:** Developer Experience Team, Lumenvale Technologies Inc.
- **Status:** Current

## 1. Overview

All production code at Lumenvale Technologies Inc. — application services, data pipelines and infrastructure — is built, tested and deployed through GitHub Actions. Data pipelines are packaged as Databricks Asset Bundles; infrastructure is managed with Terraform.

## 2. Branching Model

- Lumenvale uses **trunk-based development** on the `main` branch.
- Feature branches must be short-lived (merged within 3 working days) and named `feat/<ticket>-<description>`, `fix/<ticket>-<description>` or `hotfix/<incident-id>-<description>`.
- Direct pushes to `main` are blocked.

## 3. Pull Request Requirements

Every pull request to `main` requires:

| Requirement | Rule |
|---|---|
| Approvals | **2 approvals**, at least one from a CODEOWNER of the changed paths |
| Unit tests | All pass |
| Code coverage | **At least 80%** line coverage on changed modules |
| Linting | `ruff` (Python) and `sqlfluff` (SQL) with no errors |
| Bundle validation | `databricks bundle validate` passes for all targets |
| Security scanning | Dependency scan and secret scan pass (see TECH-SEC-001) |
| Terraform | `terraform plan` output attached for infrastructure changes |

### 3.1 Evaluation Gate for ML and LLM Services

Services that use machine learning models or large language models must also pass an offline evaluation job in CI. For retrieval-augmented generation (RAG) services, the gate fails the build if, on the golden evaluation set:

- faithfulness is below **0.85**,
- answer correctness drops by more than **3 percentage points** compared with the last release, or
- the citation validity rate (answers whose citations point to retrieved chunks that support the claim) is below **0.95**.

## 4. Environments and Promotion

| Stage | Trigger | Approval |
|---|---|---|
| dev | Every merge to `main` | Automatic |
| test | Every merge to `main`, after dev deploy succeeds | Automatic; integration tests run |
| prod | Weekly release train | Release manager approval in GitHub Environments |

## 5. Release Train

- Production releases go out on the **weekly release train every Tuesday at 14:00 UTC**.
- The release candidate is cut from `main` on Monday at 12:00 UTC and tagged `vMAJOR.MINOR.PATCH` using semantic versioning.
- The Insights API is released using a **canary**: 5% of traffic for 30 minutes, then 100% if the error rate and p99 latency stay within thresholds.

## 6. Change Freezes

No production releases are made during:

- The annual freeze from **15 December to 5 January** (inclusive).
- The **last 3 business days of each fiscal quarter**, to protect financial reporting.

Only hotfixes are allowed during a freeze.

## 7. Hotfixes

A hotfix may be deployed outside the release train when it resolves an active incident. Requirements:

- A linked incident ID in the branch name and pull request.
- **1 approval** from a CODEOWNER plus approval from the incident's on-call lead.
- All automated checks still apply, except that the coverage threshold may be waived by the on-call lead.

## 8. Rollback

Every production deployment must be reversible by redeploying the previous release tag. The target time to roll back is **30 minutes** from the decision. Database and Delta table schema migrations must be backward compatible for at least one release.
