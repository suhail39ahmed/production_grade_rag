# ADR-012: External Data Sharing Mechanism

> **FICTIONAL SAMPLE DATA - for RAG testing only**

- **Title:** ADR-012: External Data Sharing Mechanism
- **Doc ID:** TECH-ADR-012
- **Version:** 1.0
- **Effective date:** 2026-01-27
- **Owner:** Architecture Review Board, Lumenvale Technologies Inc.
- **Status:** Accepted

## Context

Lumenvale shares curated Gold data products with 20 external partners. A survey in December 2025 found that **14 partners run on Snowflake**, **6 run on Databricks or open-source Spark**, and none required file-based delivery. Until now, data was shared through nightly CSV exports to SFTP, which caused frequent schema mismatches and could not be governed centrally.

## Options Considered

1. Continue SFTP CSV exports.
2. Use Delta Sharing for all partners.
3. Copy all shared data to Snowflake and use Snowflake secure shares for all partners.
4. Use Delta Sharing for Databricks and open-source partners, and Snowflake secure shares for Snowflake-native partners.

## Decision

We adopt **option 4**. Delta Sharing is the default mechanism because data stays in the lakehouse and is governed by Unity Catalog. Snowflake secure shares are used for Snowflake-native partners, because many of them would otherwise need to build ingestion pipelines and some prefer to query data without leaving Snowflake. The SFTP exports will be retired by **30 June 2026**.

## Consequences

- Shared Gold tables must be copied to Snowflake by a daily sync job, creating a second copy that must be documented as an approved exception to the "one governed copy" principle.
- The Data Partnerships team owns the Snowflake account and share lifecycle (see TECH-SNOW-001).
- Every share, on either mechanism, requires Data Owner and Security Engineering approval.
- Restricted data may never be shared on either mechanism.
