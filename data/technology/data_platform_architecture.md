# Lumenvale Data Platform Architecture

> **FICTIONAL SAMPLE DATA - for RAG testing only**

- **Title:** Lumenvale Data Platform Architecture
- **Doc ID:** TECH-ARCH-001
- **Version:** 3.1
- **Effective date:** 2026-05-20
- **Owner:** Platform Engineering (Principal Architect: Kenji Abara), Lumenvale Technologies Inc.
- **Status:** Current

## 1. Introduction

This document describes the architecture of the Lumenvale Data Platform ("the Platform"), the central analytics and data engineering environment of Lumenvale Technologies Inc. ("Lumenvale"). The Platform is a lakehouse built on **Azure Databricks** with **Unity Catalog** for governance, **Delta Lake** as the table format and **Azure Data Lake Storage Gen2 (ADLS Gen2)** as the underlying storage. Curated data is also made available to partners through Delta Sharing and Snowflake secure shares.

The audience is data engineers, analytics engineers, platform engineers and security reviewers. The document describes the target state as of version 3.1; deviations must be recorded as exceptions in the architecture register.

### 1.1 Design Principles

1. **One governed copy of data.** Data is stored once in Delta format and governed in Unity Catalog. Copies outside the lakehouse are allowed only for sharing and must be documented.
2. **Medallion layering.** Data flows through Bronze, Silver and Gold layers with clear contracts at each boundary.
3. **Everything as code.** Workspaces, clusters, jobs and permissions are defined in Terraform and Databricks Asset Bundles and deployed through CI/CD (see TECH-CICD-001).
4. **Least privilege.** Access is granted to groups, never to individual users, and production write access is limited to service principals.
5. **Private by default.** No Platform component is reachable from the public internet (see TECH-AZ-001).

### 1.2 Key Numbers

| Metric | Value (May 2026) |
|---|---|
| Average daily ingest volume | ~3.2 TB |
| Number of production Delta tables | ~2,450 |
| Number of production jobs | 610 |
| Registered data consumers (users) | ~1,900 |
| Number of source systems | 74 |

## 2. Environments and Workspaces

The Platform runs in three environments, each with its own Databricks workspace and Azure subscription under the `mg-landingzones/corp` management group.

| Environment | Workspace name | Resource group | Purpose |
|---|---|---|---|
| Development | `dbw-dataplat-dev-eus2-001` | `rg-dataplat-dev-eus2-001` | Feature development, sample data only |
| Test | `dbw-dataplat-test-eus2-001` | `rg-dataplat-test-eus2-001` | Integration testing, masked production data |
| Production | `dbw-dataplat-prod-eus2-001` | `rg-dataplat-prod-eus2-001` | Production workloads |

The primary region is **Azure East US 2 (eastus2)**. A warm disaster recovery workspace, `dbw-dataplat-dr-cus-001`, runs in **Central US (centralus)**. All workspaces are deployed with VNet injection, secure cluster connectivity (no public IP) and private endpoints for the front-end and back-end, following the landing zone standards in TECH-AZ-001.

## 3. Storage Layout

### 3.1 Storage Accounts

Production data is stored in the ADLS Gen2 account **`stlvlakeprodeus2`** with hierarchical namespace enabled. (Storage account names cannot contain hyphens, so they are an approved exception to the standard naming convention.) The account has these containers:

| Container | Contents |
|---|---|
| `landing` | Files dropped by source systems and integration tools, before ingestion |
| `bronze` | Managed storage for Bronze catalogs |
| `silver` | Managed storage for Silver catalogs |
| `gold` | Managed storage for Gold catalogs |
| `checkpoints` | Streaming checkpoints for Auto Loader and Structured Streaming |

Public network access is disabled on the storage account; it is reachable only through private endpoints. Storage account shared keys are disabled and all access uses Microsoft Entra ID identities (see TECH-SEC-001). Production storage is encrypted with customer-managed keys held in the Key Vault `kv-dataplat-prod-eus2-001`.

### 3.2 External Locations

Each container is registered in Unity Catalog as an external location backed by a storage credential that uses the Databricks access connector managed identity `ac-dataplat-prod-eus2`. Engineers never use storage keys or SAS tokens to access lakehouse data.

## 4. Unity Catalog

### 4.1 Metastore

There is **one Unity Catalog metastore per region**: `uc-metastore-eus2` for East US 2 and `uc-metastore-cus` for Central US. All Lumenvale workspaces in a region attach to that region's metastore.

The legacy Hive metastore was made read-only on 1 October 2025 and was **decommissioned on 31 March 2026**, as decided in ADR-007 (TECH-ADR-007). No new workloads may reference `hive_metastore`.

### 4.2 Catalog and Schema Structure

Catalogs are organized by environment and medallion layer. Schemas are organized by business domain.

| Catalog | Layer | Example schemas |
|---|---|---|
| `lv_prod_bronze` | Bronze | `sales`, `billing`, `product_events`, `crm` |
| `lv_prod_silver` | Silver | `sales`, `billing`, `product_events`, `customer` |
| `lv_prod_gold` | Gold | `finance_marts`, `product_analytics`, `customer_360` |
| `lv_prod_sandbox` | Sandbox | One schema per team, e.g. `team_growth` |

Equivalent catalogs exist for test (`lv_test_*`) and development (`lv_dev_*`). Fully qualified table names therefore follow the three-level namespace `catalog.schema.table`, for example `lv_prod_gold.finance_marts.fct_monthly_revenue`.

### 4.3 Table Naming Conventions

| Prefix | Meaning | Example |
|---|---|---|
| `raw_` | Bronze table mirroring a source object | `raw_salesforce_opportunity` |
| `stg_` | Silver staging/cleansed table | `stg_opportunity` |
| `dim_` | Gold dimension | `dim_customer` |
| `fct_` | Gold fact | `fct_monthly_revenue` |
| `agg_` | Gold aggregate for dashboards | `agg_daily_active_users` |

Table and column names use lower snake_case. Every table must have a table comment and an `owner` tag.

### 4.4 Access Control

Privileges are granted only to Entra ID groups synchronized to Databricks through SCIM:

| Group | Typical privileges |
|---|---|
| `grp-data-engineers` | `USE CATALOG`, `SELECT` on Bronze and Silver; `MODIFY` in dev and test only |
| `grp-analytics-engineers` | `SELECT` on Silver and Gold; `CREATE TABLE` in `lv_prod_sandbox` |
| `grp-bi-consumers` | `SELECT` on Gold only |
| `grp-data-platform-admins` | Metastore admin (break-glass use only, see TECH-SEC-001) |
| `sp-dataplat-prod-deployer` | Service principal that owns and writes all production tables |

Human users have no write access to production catalogs. All production writes come from jobs running as service principals.

### 4.5 Fine-grained Security

- **Row filters** restrict rows by region for tables containing customer data; for example, users in `grp-emea-analysts` see only EMEA rows of `lv_prod_gold.customer_360.dim_customer`.
- **Column masks** are applied to all columns tagged `pii=true`. The masking function returns a SHA-256 hash for members of `grp-analytics-engineers` and the clear value only for members of `grp-pii-readers`.
- Tables classified as **Restricted** (see TECH-SEC-001) may not be shared externally under any circumstances.

### 4.6 Lineage and Auditing

Unity Catalog captures table- and column-level lineage automatically for jobs, notebooks and SQL warehouses. Audit logs are delivered through system tables (`system.access.audit`) and exported daily to the security team's Log Analytics workspace, where they are retained for **2 years**.

## 5. Medallion Layers

### 5.1 Bronze

- **Purpose:** Land source data with minimal transformation, preserving full history for replay.
- **Ingestion:** Files are ingested from the `landing` container with **Auto Loader** (`cloudFiles`) in file notification mode. Database sources are ingested through change data capture into the landing zone by the integration team.
- **Format:** Append-only Delta tables. A `_rescued_data` column captures fields that do not match the expected schema. An ingestion metadata struct (`_ingest_ts`, `_source_file`, `_batch_id`) is added to every row.
- **Schema handling:** Schema hints are maintained in the job configuration. When the proportion of rows with non-null `_rescued_data` in a batch exceeds the threshold defined in the pipeline runbook, the job fails with error code ERR-PIPE-4012 so that schema drift is investigated rather than silently absorbed (see TECH-RB-001).
- **Retention:** Bronze data is retained for **400 days**, after which it is deleted by a scheduled retention job.

### 5.2 Silver

- **Purpose:** Provide cleansed, deduplicated, conformed data at the grain of the business entity.
- **Processing:** Implemented as Lakeflow Declarative Pipelines (formerly Delta Live Tables) in triggered or continuous mode depending on latency needs.
- **Data quality:** Expectations are declared for every Silver table. Rows that violate `warn` expectations are kept and counted; rows that violate `drop` expectations are removed and written to a quarantine table; violations of `fail` expectations stop the update.
- **Change data:** Slowly changing dimensions use `APPLY CHANGES` with SCD type 2 for customer and product entities.
- **Retention:** Silver data is retained for **7 years** to satisfy financial record-keeping requirements.
- **Latency:** Streaming Silver tables have a latency SLO of **less than 15 minutes at p95** from file arrival to availability.

### 5.3 Gold

- **Purpose:** Business-level marts, metrics and aggregates designed for BI, data science and sharing.
- **Processing:** Built with Databricks SQL and dbt-style SQL models orchestrated by Lakeflow Jobs. Gold models run on job compute with **Photon** enabled.
- **Freshness SLO:** Daily Gold tables must be refreshed by **06:00 UTC** every day. The SLO is met when at least 99% of Gold tables tagged `tier=1` are fresh by that time on a monthly basis.
- **Semantic layer:** Certified metrics are defined as Unity Catalog metric views in `lv_prod_gold.metrics`.

### 5.4 Layer Contract Summary

| Layer | Mutability | Retention | Quality enforcement | Who reads it |
|---|---|---|---|---|
| Bronze | Append-only | 400 days | Schema checks, rescued data threshold | Data engineers |
| Silver | Merge/upsert | 7 years | Declarative pipeline expectations | Data and analytics engineers |
| Gold | Rebuild or merge | Per data product (default 7 years) | dbt-style tests, freshness monitors | Analysts, BI, partners |

## 6. Compute

### 6.1 Job Compute

Production pipelines run on job clusters or serverless jobs compute. Classic job clusters must use a cluster policy:

| Policy | Max workers | Node types allowed | Notes |
|---|---|---|---|
| `policy-jobs-standard` | 20 | Standard_D8ds_v5, Standard_D16ds_v5 | Default for batch jobs |
| `policy-jobs-memory` | 12 | Standard_E16ds_v5 | For large joins and ML feature jobs |
| `policy-streaming` | 8 | Standard_D8ds_v5 | Fixed size, no autoscaling, for streaming |

Instance pools keep warm capacity for the most common node types. A fallback pool, `pool-d8ds-v5-fallback`, uses a different VM family and availability-zone mix and is used when cluster launch fails because of capacity or quota (see ERR-PIPE-5001 in TECH-RB-001).

### 6.2 Interactive Compute

All-purpose clusters are permitted only in development and test. They must use the `policy-interactive` policy, which enforces **auto-termination after 30 minutes** of inactivity and a maximum of 8 workers.

### 6.3 SQL Warehouses

| Warehouse | Type | Size | Auto-stop | Used by |
|---|---|---|---|---|
| `wh-bi-prod` | Serverless | Medium | 10 minutes | Power BI and dashboards |
| `wh-adhoc-prod` | Serverless | Small (scales to 3 clusters) | 10 minutes | Analysts' ad hoc queries |
| `wh-etl-prod` | Pro | Large | 15 minutes | SQL-based Gold transformations |

### 6.4 Authentication for Jobs

Production jobs run as service principals using OAuth machine-to-machine authentication. Personal access tokens are not permitted for production jobs. Secrets used by jobs (for example source system credentials) are read from Key Vault-backed secret scopes (see TECH-SEC-001).

## 7. Orchestration and Deployment

Jobs are defined in Databricks Asset Bundles stored in the `lv-dataplat-bundles` repository. Each bundle declares the job, its compute and its target environments. Deployment to test and production happens through the CI/CD pipeline described in TECH-CICD-001. Manual changes to production jobs through the UI are blocked by workspace permissions; drift detection runs nightly and opens a ticket if any job definition differs from the deployed bundle.

Cross-pipeline dependencies are handled through table update triggers where possible, rather than fixed schedules, so that Gold models start as soon as their Silver inputs are refreshed.

## 8. Table Maintenance

- **Liquid clustering** is the default for new tables larger than 1 TB; legacy partitioned tables are being migrated by end of 2026.
- **Predictive optimization** is enabled at the catalog level for `lv_prod_silver` and `lv_prod_gold`, running `OPTIMIZE` and `VACUUM` automatically.
- **VACUUM retention** is set to **7 days (168 hours)**. Time travel beyond 7 days is therefore not available; teams that need longer history must snapshot data explicitly.
- **Deletion vectors** are enabled on all Silver and Gold tables.

## 9. Data Sharing

Curated Gold data products can be shared outside the Platform through two mechanisms, as decided in ADR-012 (TECH-ADR-012):

- **Delta Sharing** for partners using Databricks or open-source Delta Sharing clients.
- **Snowflake secure shares** for Snowflake-native partners. Gold tables are synchronized to the Lumenvale Snowflake account by the `gold_to_snowflake_sync` job (see TECH-SNOW-001).

Only Gold tables tagged `shareable=true` and classified Internal or lower may be shared, and every share requires a data owner and a security approval.

## 10. Observability

- **Job monitoring:** Job failures raise alerts in PagerDuty through the `dataplat-prod` service. Failure classification uses the error codes defined in TECH-RB-001.
- **Data quality monitoring:** Lakehouse Monitoring profiles are attached to all tier-1 Gold tables and alert on freshness, volume anomalies and null-rate drift.
- **Cost monitoring:** System billing tables (`system.billing.usage`) feed a cost dashboard. All compute must carry the tags `cost-center`, `owner` and `env`; untagged clusters are blocked by policy.

## 11. Disaster Recovery

| Objective | Target |
|---|---|
| Recovery point objective (RPO) | **4 hours** |
| Recovery time objective (RTO) | **8 hours** |

- ADLS Gen2 data in the production account is replicated to Central US using object replication for the `silver` and `gold` containers. Bronze is not replicated; it can be rebuilt from source systems where needed.
- Unity Catalog metadata (catalogs, schemas, grants) and job definitions are recreated in the DR region from Terraform and Asset Bundles.
- DR failover is tested **twice a year**, in March and September. The March 2026 test achieved recovery in 6 hours 40 minutes.

## 12. Non-functional Requirements Summary

| Requirement | Target |
|---|---|
| Platform availability SLO (internal) | 99.5% monthly (see TECH-ONC-001) |
| Gold daily freshness | By 06:00 UTC |
| Silver streaming latency | < 15 minutes p95 |
| Audit log retention | 2 years |
| RPO / RTO | 4 hours / 8 hours |

## 13. Roadmap (H2 2026)

- Migrate remaining partitioned tables to liquid clustering.
- Expand serverless jobs compute to all batch workloads where cost-neutral.
- Introduce data contracts for the top 20 source systems, validated at Bronze ingestion.
- Pilot an internal "Ask My Docs" retrieval-augmented assistant over platform documentation, using Databricks Vector Search with hybrid keyword and vector retrieval.

## 14. Related Documents

- TECH-AZ-001 Azure Landing Zone Standards
- TECH-SEC-001 Security and Secrets Standards
- TECH-RB-001 Incident Runbook: Data Pipeline Failures
- TECH-ONC-001 On-call and SLA Policy
- TECH-CICD-001 CI/CD and Release Process
- TECH-SNOW-001 Snowflake Data Sharing Guide
- TECH-ADR-007 Adopt Unity Catalog and Retire the Hive Metastore
- TECH-ADR-012 External Data Sharing Mechanism

## Appendix A — Onboarding a New Source System

1. The requesting team opens a ticket in the `DATAPLAT` Jira project with the source system name, owner, data classification, expected daily volume and required freshness.
2. Platform Engineering assigns a Bronze schema and creates the landing folder `landing/<source_system>/<object>/` through Terraform.
3. The source owner agrees a data contract covering schema, delivery schedule, expected file format (Parquet or JSON preferred; CSV only by exception) and the late-arrival threshold.
4. The data engineer creates the Bronze ingestion job and the Silver pipeline in a bundle, with schema hints and expectations, and deploys to development.
5. After successful testing with masked data in the test workspace, the change goes through the standard release train into production.
6. The new tables are registered with owners, descriptions and classification tags before any consumer is granted access.

Typical lead time for a new source with an agreed contract is **10 business days**.
