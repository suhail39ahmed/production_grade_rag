# Lumenvale Insights API v2 — Reference

> **FICTIONAL SAMPLE DATA - for RAG testing only**

- **Title:** Lumenvale Insights API v2 — Reference
- **Doc ID:** TECH-API-001
- **Version:** 2.5
- **Effective date:** 2026-06-15
- **Owner:** API Platform Team, Lumenvale Technologies Inc.
- **Status:** Current

## 1. Overview

The Lumenvale Insights API gives customers programmatic access to curated datasets and an asynchronous query service backed by the Lumenvale Data Platform.

- **Base URL:** `https://api.lumenvale.example/v2`
- **Format:** JSON over HTTPS (TLS 1.2+)
- **Availability:** 99.9% monthly SLA (see TECH-ONC-001)

API v1 (`/v1`) is deprecated and will be **sunset on 31 December 2026**. After that date all `/v1` requests return HTTP 410 Gone.

## 2. Authentication

The API uses the OAuth 2.0 client credentials flow.

```
POST https://auth.lumenvale.example/oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=...&client_secret=...&scope=datasets:read queries:write
```

Access tokens are valid for **3600 seconds (1 hour)**. Clients should cache tokens and request a new one shortly before expiry. Scopes:

| Scope | Grants |
|---|---|
| `datasets:read` | List and read datasets and records |
| `queries:write` | Submit and cancel queries |
| `queries:read` | Read query status and results |
| `usage:read` | Read usage statistics |

## 3. Endpoints

| Method | Path | Description | Scope |
|---|---|---|---|
| GET | `/datasets` | List datasets available to the client | `datasets:read` |
| GET | `/datasets/{dataset_id}` | Get dataset metadata and schema | `datasets:read` |
| GET | `/datasets/{dataset_id}/records` | Page through dataset records | `datasets:read` |
| POST | `/queries` | Submit an asynchronous SQL query | `queries:write` |
| GET | `/queries/{query_id}` | Get query status and result location | `queries:read` |
| DELETE | `/queries/{query_id}` | Cancel a running query | `queries:write` |
| GET | `/usage` | Get request and query usage for the current month | `usage:read` |

### 3.1 GET /datasets/{dataset_id}/records

Query parameters:

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `page_size` | integer | 100 | Maximum **1000** |
| `cursor` | string | — | Opaque cursor returned in `next_cursor` |
| `fields` | string | all | Comma-separated list of fields |
| `updated_since` | ISO 8601 timestamp | — | Return only records updated after this time |

Pagination is cursor-based. When `next_cursor` is `null`, there are no more pages.

### 3.2 POST /queries

Request body:

```json
{
  "sql": "SELECT region, SUM(revenue) FROM daily_sales GROUP BY region",
  "dataset_ids": ["ds_daily_sales"],
  "result_format": "parquet"
}
```

Response: `202 Accepted` with a `query_id`. Poll `GET /queries/{query_id}` until `status` is `SUCCEEDED`, `FAILED` or `CANCELLED`.

- Maximum query runtime: **15 minutes**; longer queries are cancelled with error `LV-API-4080`.
- Query results are retained for **24 hours** and are available through a pre-signed URL that expires after 15 minutes (request a new one by calling `GET /queries/{query_id}` again).
- Supported result formats: `parquet`, `csv`, `json`.

## 4. Rate Limits

Rate limits are applied per client ID.

| Plan | Requests per minute | Concurrent queries (`POST /queries`) |
|---|---|---|
| Free | 60 | 1 |
| Standard | 600 | 10 |
| Enterprise | 3,000 | 50 |

Every response includes these headers:

- `X-RateLimit-Limit` — requests allowed in the current window
- `X-RateLimit-Remaining` — requests remaining in the window
- `X-RateLimit-Reset` — Unix time when the window resets

When a limit is exceeded, the API returns **HTTP 429** with error code `LV-API-4290` and a `Retry-After` header in seconds. Clients should use exponential backoff with jitter.

## 5. Errors

Errors use a consistent body:

```json
{ "error": { "code": "LV-API-4040", "message": "Dataset not found", "request_id": "req_8f2c..." } }
```

| HTTP status | Error code | Meaning |
|---|---|---|
| 400 | LV-API-4001 | Invalid parameter |
| 401 | LV-API-4010 | Access token missing or expired |
| 403 | LV-API-4030 | Token lacks the required scope |
| 404 | LV-API-4040 | Resource not found |
| 408 | LV-API-4080 | Query exceeded maximum runtime |
| 429 | LV-API-4290 | Rate limit exceeded |
| 503 | LV-API-5030 | Query engine temporarily unavailable; retry later |

Always include the `request_id` when contacting support.

## 6. Changelog

| Version | Date | Change |
|---|---|---|
| 2.5 | 2026-06-15 | Added `updated_since` filter to records endpoint |
| 2.4 | 2026-02-01 | Enterprise rate limit raised from 2,000 to 3,000 requests per minute |
| 2.3 | 2025-10-20 | Added `json` result format |
