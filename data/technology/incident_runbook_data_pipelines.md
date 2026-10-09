# Incident Runbook: Data Pipeline Failures

> **FICTIONAL SAMPLE DATA - for RAG testing only**

- **Title:** Incident Runbook: Data Pipeline Failures
- **Doc ID:** TECH-RB-001
- **Version:** 2.3
- **Effective date:** 2026-06-02
- **Owner:** Data Reliability Engineering (DRE), Lumenvale Technologies Inc.
- **Status:** Current

## 1. How to Use this Runbook

This runbook is for the on-call data engineer responding to alerts from the `dataplat-prod` PagerDuty service. Every pipeline failure on the Lumenvale Data Platform (TECH-ARCH-001) is classified with an error code. Find the error code in the alert, go to its section and follow the steps in order. Severity definitions and response times are set in the On-call and SLA Policy (TECH-ONC-001).

Before you start any procedure:

1. Acknowledge the page.
2. Open an incident channel in Slack named `#inc-<yyyymmdd>-<short-name>`.
3. Check the platform status dashboard for any ongoing Azure or Databricks incident.

## 2. Error Code Reference

| Error code | Meaning | Default severity |
|---|---|---|
| ERR-PIPE-4012 | Schema drift detected in Bronze ingestion | Sev2 |
| ERR-PIPE-4013 | Upstream source file late | Sev3 |
| ERR-PIPE-4020 | Silver expectation failure rate exceeded | Sev2 |
| ERR-PIPE-4031 | Streaming checkpoint corruption | Sev2 |
| ERR-PIPE-5001 | Cluster launch failure (capacity or quota) | Sev3 |
| ERR-UC-2201 | Unity Catalog permission denied on external location | Sev2 |
| ERR-SNOW-3307 | Snowflake sync job failed | Sev3 |

Raise the severity by one level (for example Sev3 to Sev2) if the failure puts the Gold 06:00 UTC freshness SLO at risk for any tier-1 table.

## 3. ERR-PIPE-4012 — Schema Drift Detected in Bronze Ingestion

**Trigger:** An Auto Loader Bronze job fails when more than **1% of rows in a micro-batch** have a non-null `_rescued_data` column, meaning the source has sent fields that do not match the expected schema (new, renamed or retyped columns).

**Impact:** The Bronze table stops updating; downstream Silver and Gold tables become stale.

**Steps:**

1. Open the failed job run and note the source file path(s) from `_source_file` in the error output.
2. Query the rescued data to see which fields drifted:
   ```sql
   SELECT _rescued_data, _source_file
   FROM lv_prod_bronze.<schema>.<table>
   WHERE _ingest_ts > current_timestamp() - INTERVAL 1 DAY
     AND _rescued_data IS NOT NULL
   LIMIT 100;
   ```
3. Classify the change:
   - **New column added:** update the schema hints in the bundle, set `cloudFiles.schemaEvolutionMode` to `addNewColumns`, deploy through the hotfix path and re-run the job.
   - **Column renamed or removed:** do not change the schema. Contact the source system owner and escalate to the owning domain team; this breaks the data contract.
   - **Type change (for example integer to string):** add an explicit cast in Silver and keep Bronze as string; deploy via hotfix.
4. **Do not delete or reset the streaming checkpoint** to make the error go away. Resetting the checkpoint causes files to be re-ingested and creates duplicates.
5. Confirm the next micro-batch succeeds and that the rescued-data ratio is back below 1%.

## 4. ERR-PIPE-4013 — Upstream Source File Late

**Trigger:** An expected file has not arrived in the `landing` container more than **2 hours** after its contracted arrival time.

**Steps:**

1. Check the source system's status page or contact its on-call.
2. If the source confirms a delay of more than 4 hours, notify consumers of affected Gold tables in `#data-announcements`.
3. No re-run is needed; the triggered pipeline will pick up the file on arrival.

## 5. ERR-PIPE-4020 — Silver Expectation Failure Rate Exceeded

**Trigger:** More than **5% of rows** in a Silver pipeline update violate `drop` expectations, or any `fail` expectation is violated. The pipeline update is halted.

**Steps:**

1. Open the pipeline event log and identify the expectation with the highest failure count.
2. Inspect the quarantine table (`<table>_quarantine`) for sample rows.
3. If the issue is a bad upstream batch, ask the source owner to resend and re-run the update with a full refresh of the affected table only.
4. If the expectation itself is wrong, fix it through the normal release process; do not lower thresholds during an incident without approval from the DRE lead.

## 6. ERR-PIPE-4031 — Streaming Checkpoint Corruption

**Trigger:** A streaming job fails to start because its checkpoint in the `checkpoints` container is unreadable or inconsistent.

**Steps:**

1. Page the secondary on-call; this procedure requires two engineers.
2. Restore the checkpoint folder from the most recent storage snapshot (snapshots are taken every 6 hours).
3. Restart the stream and verify there are no duplicate records using the `_batch_id` column.
4. Only if restore fails, create a new checkpoint with a defined `startingTimestamp` and deduplicate downstream. This requires DRE lead approval.

## 7. ERR-PIPE-5001 — Cluster Launch Failure

**Trigger:** A job cluster fails to start because of Azure capacity or subscription quota limits.

**Steps:**

1. Re-run the job using the fallback instance pool **`pool-d8ds-v5-fallback`** by setting the job parameter `use_fallback_pool=true`.
2. If the fallback also fails, check the subscription vCPU quota in the Azure portal and open a quota increase request.
3. For repeated occurrences (more than 3 in 7 days), raise a ticket with Platform Engineering to review pool sizing.

## 8. ERR-UC-2201 — Unity Catalog Permission Denied on External Location

**Trigger:** A job running as a service principal receives a permission error reading or writing an external location.

**Steps:**

1. Check for recent grant changes in `system.access.audit` for the external location.
2. Confirm the job is running as `sp-dataplat-prod-deployer` and not as a user.
3. Grants must be restored through Terraform, not manually. Open a hotfix pull request in the platform infrastructure repository.

## 9. ERR-SNOW-3307 — Snowflake Sync Job Failed

**Trigger:** The `gold_to_snowflake_sync` job fails, usually because the Snowflake warehouse `WH_SYNC` is suspended or its resource monitor credit quota is exhausted.

**Steps:**

1. Check the resource monitor in Snowflake; if the quota is exhausted, contact the Data Partnerships team for approval to raise it.
2. Re-run the sync job. Partners are notified only if the sync has not completed by **12:00 UTC**.
3. See the Snowflake Data Sharing Guide (TECH-SNOW-001) for share-specific troubleshooting.

## 10. After the Incident

- Update the incident ticket with the timeline and the root cause.
- A postmortem is required for Sev1 and Sev2 incidents, as set out in TECH-ONC-001.
- If the runbook was wrong or incomplete, open a pull request to update it within 5 business days.
