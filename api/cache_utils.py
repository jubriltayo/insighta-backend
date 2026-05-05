import json
import hashlib
from django.core.cache import cache

CACHE_TTL = 60  # seconds


def normalize_filters(params: dict) -> dict:
    """
    Produce a canonical filter dict from raw query params.
    Two queries expressing the same intent must produce identical output.
    - All keys lowercased
    - String values stripped and lowercased
    - Numeric values cast to int/float
    - Keys sorted deterministically
    - Unknown/empty values dropped
    """
    NUMERIC_INT = {"min_age", "max_age", "page", "limit"}
    NUMERIC_FLOAT = {"min_gender_probability", "min_country_probability"}
    STRING_FIELDS = {"gender", "age_group", "country_id", "sort_by", "order"}

    normalized = {}

    for key, value in params.items():
        if value is None or value == "":
            continue

        key = key.strip().lower()

        if key in NUMERIC_INT:
            try:
                normalized[key] = int(value)
            except (ValueError, TypeError):
                pass
        elif key in NUMERIC_FLOAT:
            try:
                normalized[key] = float(value)
            except (ValueError, TypeError):
                pass
        elif key in STRING_FIELDS:
            normalized[key] = str(value).strip().lower()

    # Apply defaults so cache keys are fully explicit
    normalized.setdefault("sort_by", "created_at")
    normalized.setdefault("order", "desc")
    normalized.setdefault("page", 1)
    normalized.setdefault("limit", 10)

    return dict(sorted(normalized.items()))


def make_cache_key(prefix: str, filters: dict) -> str:
    """
    Produce a stable cache key string from a normalized filter dict.
    prefix: e.g. "profiles_list" or "profiles_search"
    """
    raw = json.dumps(filters, sort_keys=True)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"insighta:{prefix}:{digest}"


def get_cached(key: str):
    return cache.get(key)


def set_cached(key: str, value, ttl: int = CACHE_TTL):
    cache.set(key, value, timeout=ttl)


def invalidate_profiles_cache():
    """
    Called after any write (create, import, delete) to wipe profile list/search cache.
    Uses Django's cache versioning approach: bump a global version key.
    Any key built before the bump will no longer match.
    """
    cache.delete_pattern("insighta:profiles_*")