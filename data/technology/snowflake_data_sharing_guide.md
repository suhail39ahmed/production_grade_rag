# Snowflake Data Sharing Guide

> **FICTIONAL SAMPLE DATA - for RAG testing only**

- **Title:** Snowflake Data Sharing Guide
- **Doc ID:** TECH-SNOW-001
- **Version:** 1.4
- **Effective date:** 2026-02-10
- **Owner:** Data Partnerships Team, Lumenvale Technologies Inc.
- **Status:** Current

## 1. When to Use Snowflake Sharing

Lumenvale shares curated data products with external partners. Following ADR-012 (TECH-ADR-012), partners that already run on Snowflake receive data through **Snowflake secure data sharing**. Partners on Databricks or other platforms use Delta Sharing instead (see TECH-ARCH-001, Section 9).

## 2. Account Setup

| Item | Value |
|---|---|
| Snowflake account identifier | `LUMENVALE-PROD_EUS2` |
| Cloud and region | Azure East US 2 |
| Edition | Business Critical |
| Database holding shared data | `LV_SHARED` |
| Sync warehouse | `WH_SYNC` (X-Small, auto-suspend 60 seconds) |

Data is loaded from the lakehouse Gold layer by the Databricks job **`gold_to_snowflake_sync`**, which runs daily at **07:00 UTC**, after the Gold freshness deadline of 06:00 UTC. Only Gold tables tagged `shareable=true` are synchronized.

## 3. Creating a Share

1. The partner manager opens a request in the **`DATASHARE` Jira project**, naming the partner, the datasets, the purpose and the contract reference.
2. The request needs two approvals: the **Data Owner** of each dataset and **Security Engineering**.
3. A data engineer creates **secure views** over the shared tables in `LV_SHARED.<PARTNER>` that expose only the approved columns and rows. Direct grants on tables to a share are not allowed; always use secure views.
4. Create the share with the naming convention **`SHR_<PARTNER>_<DATASET>`**, for example `SHR_BRIGHTCART_DAILY_SALES`.
5. Add the partner's Snowflake account to the share and confirm the partner can query it.

## 4. Partners in Other Regions

A share can only be consumed directly by accounts in the same cloud region. For partners in another region or cloud, replicate `LV_SHARED` to a secondary Lumenvale account in that region using database replication, and create the share from there. Replication refreshes run every 4 hours.

## 5. Reader Accounts

For partners that do not have their own Snowflake account, Lumenvale can provision a **reader account**. Lumenvale pays for the compute used by reader accounts, so every reader account must have a resource monitor with a cap of **50 credits per month**, after which its warehouse is suspended. Reader accounts are provisioned only for contracts of at least 12 months.

## 6. Revoking Access

When a partner contract ends, access must be revoked **within 24 hours** of the contract end date by removing the partner account from the share and, for reader accounts, dropping the reader account after exporting its usage history.

## 7. Monitoring and Troubleshooting

- Share usage is reviewed monthly using the `DATA_SHARING_USAGE` views.
- If the daily sync fails, the Databricks job raises error **ERR-SNOW-3307**; follow the steps in TECH-RB-001.
- Partners are told to expect data by 12:00 UTC each day.
