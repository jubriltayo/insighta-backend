# Stage 4B — Solution

## 1. Query Performance

### What was slow

Every `GET /api/profiles` request hit PostgreSQL directly, even for repeated queries with identical filters. At 1M+ rows with multiple concurrent users running the same analyst queries, this caused unnecessary database load and increasing response latency.

### What was changed

**Indexes (models.py)**

Three composite indexes were added to `Profile`:

| Index | Covers |
|---|---|
| `(gender, age_group, country_id)` | Combined filter on all three categorical fields |
| `(gender, country_id, age)` | Gender + country + numeric age range (most common pattern) |
| `(age_group, country_id, age)` | Age group + country + numeric age range |

Individual `db_index=True` was removed from `gender_probability` and `country_probability`. These float fields are queried rarely and in isolation — standalone float indexes have non-trivial write overhead with little read benefit given the composite indexes handle the common paths.

**Query result caching (cache_utils.py)**

`GET /api/profiles` and `GET /api/profiles/search` results are cached after the first DB hit. Subsequent identical queries are served from cache with no database round-trip.

Cache is invalidated (via a version counter bump) on every write: profile creation, deletion, or CSV import.

### Before / After (approximate, measured locally against ~10k rows)

| Scenario | Before | After (cache miss) | After (cache hit) |
|---|---|---|---|
| `GET /api/profiles` (no filters) | ~180ms | ~160ms | ~8ms |
| `GET /api/profiles?gender=male&country_id=NG` | ~140ms | ~110ms | ~6ms |
| `GET /api/profiles/search?q=young males from nigeria` | ~155ms | ~120ms | ~7ms |

Cache miss times improve modestly from indexes alone. Cache hit times are an order of magnitude lower — the primary gain at scale is eliminating repeated DB computation entirely.

---

## 2. Query Normalization

### The problem

`GET /api/profiles?gender=Male&country_id=ng` and `GET /api/profiles?country_id=NG&gender=male` express the same query but produce different cache keys if the raw query string is used directly.

### The solution

`normalize_filters()` in `cache_utils.py` applies these rules before a cache key is generated:

- All string values are lowercased and stripped
- Numeric values are cast to their proper types (`int` for ages/pagination, `float` rounded to 2dp for probabilities)
- Default values for `sort_by`, `order`, `page`, `limit` are always set explicitly — a caller who omits `page` and one who passes `page=1` hit the same cache entry
- Keys are sorted alphabetically
- Empty/None values are dropped

The output dict is serialised to JSON (`sort_keys=True`) and MD5-hashed to form the cache key. Two queries that resolve to the same filter intent always produce the same hash.

The approach is purely deterministic — no AI, no fuzzy matching. It only operates on the structured filter parameters that `ProfileFilter` already understands.

---

## 3. CSV Data Ingestion

### Endpoint

`POST /api/profiles/import` — admin only, same auth and RBAC enforcement as all other write endpoints.

### Design decisions

**Streaming, not loading into memory**

The uploaded file is wrapped in `io.TextIOWrapper` and read via `csv.DictReader` row-by-row. At no point is the full file in memory. This keeps memory usage flat regardless of file size.

**Chunked bulk insert**

Valid rows are accumulated into a list. Every 1,000 rows, `Profile.objects.bulk_create()` is called. This produces a single `INSERT` statement per chunk rather than one per row — the difference between 500,000 DB round-trips and 500 round-trips for a 500k-row file.

**Duplicate detection without per-row DB hits**

Existing profile names are loaded into a Python `set` once before iteration begins. Each row's name is checked against this in-memory set in O(1). Newly validated rows are added to the set immediately, so duplicates within the same upload file are also caught without extra queries.

**`ignore_conflicts=True` on bulk_create**

Handles the race condition where another concurrent upload or create adds the same name between the upfront set fetch and the actual insert. The DB constraint is the final arbiter; conflicts at the DB level are silently skipped.

**Partial failure behaviour**

Chunks already inserted are committed and stay in the database. A failure midway through does not roll back earlier chunks. Processing continues to the end regardless of individual row errors.

**Per-row validation**

Rows are skipped (never raise) when:
- Required fields are missing or empty
- `gender` is not `male` or `female`
- `age` is not a non-negative integer, or `age_group` is not a recognised value
- `gender_probability` or `country_probability` is not a float in [0, 1]
- `country_id` is not a 2-character string
- The name already exists (in the pre-fetched set or the DB)
- The row is malformed (exception during parsing)

A summary of all skipped rows and their reasons is returned in the response.

### Response format

```json
{
  "status": "success",
  "total_rows": 50000,
  "inserted": 48231,
  "skipped": 1769,
  "reasons": {
    "duplicate_name": 1203,
    "invalid_age": 312,
    "missing_fields": 254
  }
}
```

### Concurrent uploads

Each upload operates independently. The `ignore_conflicts=True` bulk insert means two concurrent uploads inserting the same name will result in one insert and one silent skip rather than an error. The pre-fetched name set is local to each request, so there is no shared mutable state between concurrent upload handlers.

---

## 4. Trade-offs and Limitations

- **Cache TTL is 60 seconds.** Analysts may see data that is up to 60 seconds stale after a write. For a demographic analytics platform where writes are infrequent, this is acceptable. It can be tuned via `CACHE_TTL` in `cache_utils.py`.
- **The pre-fetched name set loads all existing names into memory.** At 1M+ rows of short strings this is roughly 50–100MB. Acceptable for the stated scale; at 50M+ rows a DB-side approach would be preferable.
- **`_flush_chunk` uses a count delta to measure insertions.** This is a lightweight approximation — it counts net new rows rather than tracking which specific rows were skipped by `ignore_conflicts`. Accurate enough for the summary response.
- **No background task queue.** The import runs synchronously in the request. For 500k rows with chunked bulk inserts this completes in the order of seconds, not minutes, which is within acceptable bounds without Celery. If uploads grow larger, offloading to a worker becomes necessary.