import csv
import io
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timezone
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse

from .models import Profile
from .serializers import ProfileSerializer, CreateProfileSerializer
from .filters.profile_filters import ProfileFilter
from .parsers.natural_language_parser import NaturalLanguageParser
from .services.genderize_client import GenderizeClient
from .services.agify_client import AgifyClient
from .services.nationalize_client import NationalizeClient
from .base import AuthenticatedAPIView, AuthenticatedView
from .permissions import admin_required
from .cache_utils import (
    normalize_filters,
    make_cache_key,
    get_cached,
    set_cached,
    invalidate_profiles_cache,
)


KNOWN_PARAMS = {
    "gender",
    "age_group",
    "country_id",
    "min_age",
    "max_age",
    "min_gender_probability",
    "min_country_probability",
    "sort_by",
    "order",
    "page",
    "limit",
}

VALID_GENDERS = {"male", "female"}
VALID_AGE_GROUPS = {"child", "teenager", "adult", "senior"}
CHUNK_SIZE = 1000  # rows per bulk_create batch


class ProfileListCreateView(AuthenticatedAPIView):
    """
    GET  /api/profiles  - List profiles with filters, sorting, and pagination
    POST /api/profiles  - Create a new profile
    """

    def get(self, request):
        # Get all query parameters
        params = request.query_params.dict()

        # Validate parameters - return error for invalid parameters (except known ones)
        invalid_params = set(params.keys()) - KNOWN_PARAMS
        if invalid_params:
            return Response(
                {"status": "error", "message": "Invalid query parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        normalized = normalize_filters(params)
        cache_key = make_cache_key("profiles_list", normalized)

        cached = get_cached(cache_key)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        # Apply filters, sorting, and pagination
        filter_handler = ProfileFilter(params)
        queryset = filter_handler.apply_filters()
        queryset = filter_handler.apply_sorting(queryset)
        paginated_data = filter_handler.apply_pagination(queryset)

        serializer = ProfileSerializer(paginated_data["data"], many=True)
        response_data = {
            "status": "success",
            "page": paginated_data["page"],
            "limit": paginated_data["limit"],
            "total": paginated_data["total"],
            "total_pages": paginated_data["total_pages"],
            "links": paginated_data["links"],
            "data": serializer.data,
        }
        
        set_cached(cache_key, response_data)
        return Response(response_data, status=status.HTTP_200_OK)

    @admin_required
    def post(self, request):
        serializer = CreateProfileSerializer(data=request.data)

        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))[0]
            return Response(
                {"status": "error", "message": str(first_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = serializer.validated_data["name"]

        # Idempotency: return existing profile already present
        existing_profile = Profile.objects.filter(name__iexact=name).first()
        if existing_profile:
            existing_serializer = ProfileSerializer(existing_profile)
            return Response(
                {
                    "status": "success",
                    "message": "Profile already exists",
                    "data": existing_serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        # Fetch data from external APIs
        gender_data = GenderizeClient.fetch_gender_data(name)
        if not gender_data:
            return Response(
                {"status": "error", "message": "Genderize returned invalid response"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        age_data = AgifyClient.fetch_age_data(name)
        if not age_data:
            return Response(
                {"status": "error", "message": "Agify returned invalid response"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        nationality_data = NationalizeClient.fetch_nationality_data(name)
        if not nationality_data:
            return Response(
                {"status": "error", "message": "Nationalize returned invalid response"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Create new profile
        profile = Profile.objects.create(
            name=name.lower(),
            gender=gender_data["gender"],
            gender_probability=gender_data["probability"],
            age=age_data["age"],
            age_group=age_data["age_group"],
            country_id=nationality_data["country_id"],
            country_name=nationality_data["country_name"],
            country_probability=nationality_data["country_probability"],
        )

        serializer = ProfileSerializer(profile)
        return Response(
            {"status": "success", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )


class ProfileSearchView(AuthenticatedAPIView):
    """
    GET /api/profiles/search?q=...
    Search profiles using natural language query
    """

    def get(self, request):
        query = request.GET.get("q", "").strip()
        if not query:
            return Response(
                {"status": "error", "message": "Missing or empty parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse natural language query to extract filters
        filters = NaturalLanguageParser.parse(query)
        if not filters:
            return Response(
                {"status": "error", "message": "Unable to interpret query"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Add pagination parameters from request
        filters["page"] = request.GET.get("page", 1)
        filters["limit"] = request.GET.get("limit", 10)

        normalized = normalize_filters(filters)
        cache_key = make_cache_key("profiles_search", normalized)

        cached = get_cached(cache_key)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        # Apply filters to queryset
        filter_handler = ProfileFilter(filters)
        queryset = filter_handler.apply_filters()
        queryset = filter_handler.apply_sorting(queryset)
        paginated_data = filter_handler.apply_pagination(
            queryset, base_url="/api/profiles/search"
        )

        serializer = ProfileSerializer(paginated_data["data"], many=True)
        response_data = {
            "status": "success",
            "page": paginated_data["page"],
            "limit": paginated_data["limit"],
            "total": paginated_data["total"],
            "total_pages": paginated_data["total_pages"],
            "links": paginated_data["links"],
            "data": serializer.data,
        }

        set_cached(cache_key, response_data)
        return Response(response_data, status=status.HTTP_200_OK)


class ProfileDetailView(AuthenticatedAPIView):
    """
    GET /api/profiles/{id} - Retrieve a specific profile
    DELETE /api/profiles/{id} - Delete a specific profile
    """

    def _get_profile(self, profile_id):
        try:
            return Profile.objects.get(id=profile_id)
        except (ValidationError, Profile.DoesNotExist):
            return None

    def get(self, request, profile_id):
        profile = self._get_profile(profile_id)
        if not profile:
            return Response(
                {"status": "error", "message": "Profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProfileSerializer(profile)
        return Response(
            {"status": "success", "data": serializer.data}, status=status.HTTP_200_OK
        )

    @admin_required
    def delete(self, request, profile_id):
        profile = self._get_profile(profile_id)
        if not profile:
            return Response(
                {"status": "error", "message": "Profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        profile.delete()
        invalidate_profiles_cache()
        return Response({}, status=status.HTTP_204_NO_CONTENT)


class ProfileExportView(AuthenticatedView):
    """
    GET /api/profiles/export?format=csv
    Uses plain Django View (not DRF APIView) to avoid content negotiation
    issues with non-JSON responses.
    """

    def get(self, request):
        format_type = request.GET.get("format")

        if format_type != "csv":
            return JsonResponse(
                {"status": "error", "message": "Invalid format"}, status=400
            )

        params = dict(request.GET)
        params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
        params.pop("format", None)

        known = {
            "gender",
            "age_group",
            "country_id",
            "min_age",
            "max_age",
            "min_gender_probability",
            "min_country_probability",
            "sort_by",
            "order",
        }
        params = {k: v for k, v in params.items() if k in known}

        filter_handler = ProfileFilter(params)
        queryset = filter_handler.apply_filters()
        queryset = filter_handler.apply_sorting(queryset)

        response = HttpResponse(content_type="text/csv")
        filename = f"profiles_{datetime.now(timezone.utc).timestamp()}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "name",
                "gender",
                "gender_probability",
                "age",
                "age_group",
                "country_id",
                "country_name",
                "country_probability",
                "created_at",
            ]
        )

        for obj in queryset.iterator(chunk_size=500):
            writer.writerow(
                [
                    str(obj.id),
                    obj.name,
                    obj.gender,
                    round(obj.gender_probability, 2),
                    obj.age,
                    obj.age_group,
                    obj.country_id,
                    obj.country_name,
                    round(obj.country_probability, 2),
                    obj.created_at.replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                ]
            )

        return response


class ProfileImportView(AuthenticatedAPIView):
    """
    POST /api/profiles/import
    Admin only. Accepts a CSV file upload with up to 500k rows.
    Processes in chunks — never loads entire file into memory.
    A single bad row never fails the upload.
    Rows already inserted before a mid-process error remain committed.
    """

    REQUIRED_COLUMNS = {
        "name",
        "gender",
        "gender_probability",
        "age",
        "age_group",
        "country_id",
        "country_name",
        "country_probability",
    }

    @admin_required
    def post(self, request):
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return Response(
                {"status": "error", "message": "No file uploaded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not uploaded_file.name.endswith(".csv"):
            return Response(
                {"status": "error", "message": "File must be a CSV"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Decode the uploaded file as a text stream — no full load into memory
        try:
            text_stream = io.TextIOWrapper(uploaded_file, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text_stream)
        except Exception:
            return Response(
                {"status": "error", "message": "Unable to read file"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate headers exist before processing any rows
        if not reader.fieldnames:
            return Response(
                {"status": "error", "message": "CSV file is empty or missing headers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        missing_headers = self.REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing_headers:
            return Response(
                {
                    "status": "error",
                    "message": f"Missing required columns: {', '.join(sorted(missing_headers))}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch existing names once upfront to check duplicates without per-row DB hits
        existing_names = set(
            Profile.objects.values_list("name", flat=True)
        )

        total_rows = 0
        inserted = 0
        skip_reasons = {
            "duplicate_name": 0,
            "invalid_age": 0,
            "invalid_gender": 0,
            "invalid_probability": 0,
            "missing_fields": 0,
            "malformed_row": 0,
        }

        chunk = []

        for row in reader:
            total_rows += 1

            # Guard against rows with wrong column count (DictReader fills None for missing)
            try:
                parsed = self._parse_row(row, existing_names, skip_reasons)
            except Exception:
                skip_reasons["malformed_row"] += 1
                continue

            if parsed is None:
                continue

            chunk.append(parsed)

            if len(chunk) >= CHUNK_SIZE:
                count = self._flush_chunk(chunk, existing_names)
                inserted += count
                chunk.clear()

        # Flush remaining rows
        if chunk:
            count = self._flush_chunk(chunk, existing_names)
            inserted += count

        invalidate_profiles_cache()

        skipped = total_rows - inserted
        reasons = {k: v for k, v in skip_reasons.items() if v > 0}

        return Response(
            {
                "status": "success",
                "total_rows": total_rows,
                "inserted": inserted,
                "skipped": skipped,
                "reasons": reasons,
            },
            status=status.HTTP_200_OK,
        )

    def _parse_row(self, row: dict, existing_names: set, skip_reasons: dict):
        """
        Validate a single CSV row. Returns a Profile instance ready for bulk_create,
        or None if the row should be skipped (mutates skip_reasons).
        """
        # Missing required fields
        for field in self.REQUIRED_COLUMNS:
            val = row.get(field)
            if val is None or str(val).strip() == "":
                skip_reasons["missing_fields"] += 1
                return None

        name = row["name"].strip().lower()

        # Duplicate check (in-memory set — no DB hit per row)
        if name in existing_names:
            skip_reasons["duplicate_name"] += 1
            return None

        # Validate gender
        gender = row["gender"].strip().lower()
        if gender not in VALID_GENDERS:
            skip_reasons["invalid_gender"] += 1
            return None

        # Validate age
        try:
            age = int(row["age"])
            if age < 0 or age > 150:
                raise ValueError
        except (ValueError, TypeError):
            skip_reasons["invalid_age"] += 1
            return None

        # Validate age_group
        age_group = row["age_group"].strip().lower()
        if age_group not in VALID_AGE_GROUPS:
            skip_reasons["invalid_age"] += 1
            return None

        # Validate probabilities
        try:
            gender_probability = float(row["gender_probability"])
            country_probability = float(row["country_probability"])
            if not (0 <= gender_probability <= 1) or not (0 <= country_probability <= 1):
                raise ValueError
        except (ValueError, TypeError):
            skip_reasons["invalid_probability"] += 1
            return None

        country_id = row["country_id"].strip().upper()
        if len(country_id) != 2:
            skip_reasons["missing_fields"] += 1
            return None

        country_name = row["country_name"].strip()

        # Mark as seen so subsequent rows in same file don't duplicate
        existing_names.add(name)

        return Profile(
            name=name,
            gender=gender,
            gender_probability=gender_probability,
            age=age,
            age_group=age_group,
            country_id=country_id,
            country_name=country_name,
            country_probability=country_probability,
        )

    def _flush_chunk(self, chunk: list, existing_names: set) -> int:
        """
        Bulk insert a chunk. ignore_conflicts=True means DB-level duplicate
        violations (race conditions, names added between the upfront set fetch
        and this insert) are silently skipped rather than raising.
        Returns the number of rows actually inserted.
        """
        before = Profile.objects.count()
        Profile.objects.bulk_create(chunk, ignore_conflicts=True)
        after = Profile.objects.count()
        return after - before
    