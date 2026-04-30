import csv
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

        # Apply filters, sorting, and pagination
        filter_handler = ProfileFilter(params)
        queryset = filter_handler.apply_filters()
        queryset = filter_handler.apply_sorting(queryset)
        paginated_data = filter_handler.apply_pagination(queryset)

        serializer = ProfileSerializer(paginated_data["data"], many=True)
        return Response(
            {
                "status": "success",
                "page": paginated_data["page"],
                "limit": paginated_data["limit"],
                "total": paginated_data["total"],
                "total_pages": paginated_data["total_pages"],
                "links": paginated_data["links"],
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

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

        # Apply filters to queryset
        filter_handler = ProfileFilter(filters)
        queryset = filter_handler.apply_filters()
        queryset = filter_handler.apply_sorting(queryset)
        paginated_data = filter_handler.apply_pagination(
            queryset, base_url="/api/profiles/search"
        )

        serializer = ProfileSerializer(paginated_data["data"], many=True)
        return Response(
            {
                "status": "success",
                "page": paginated_data["page"],
                "limit": paginated_data["limit"],
                "total": paginated_data["total"],
                "total_pages": paginated_data["total_pages"],
                "links": paginated_data["links"],
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


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
        return Response({}, status=status.HTTP_204_NO_CONTENT)


# class ProfileExportView(AuthenticatedAPIView):
#     """
#     GET /api/profiles/export?format=csv
#     """

#     def get(self, request):
#         print("=== EXPORT VIEW CALLED, format:", request.GET.get('format'))

#         format_type = request.GET.get('format')

#         if format_type != 'csv':
#             return Response({
#                 "status": "error",
#                 "message": "Invalid format"
#             }, status=status.HTTP_400_BAD_REQUEST)

#         params = request.query_params.dict()
#         params.pop('format', None)

#         filter_handler = ProfileFilter(params)
#         queryset = filter_handler.apply_filters()
#         queryset = filter_handler.apply_sorting(queryset)

#         # Create CSV response
#         response = HttpResponse(content_type='text/csv')
#         filename = f"profiles_{datetime.now(timezone.utc).timestamp()}.csv"
#         response['Content-Disposition'] = f'attachment; filename="{filename}"'

#         writer = csv.writer(response)

#         # Write header
#         writer.writerow([
#             'id', 'name', 'gender', 'gender_probability',
#             'age', 'age_group', 'country_id', 'country_name',
#             'country_probability', 'created_at'
#         ])

#         # Write data rows
#         for obj in queryset:
#             writer.writerow([
#                 str(obj.id),
#                 obj.name,
#                 obj.gender,
#                 round(obj.gender_probability, 2),
#                 obj.age,
#                 obj.age_group,
#                 obj.country_id,
#                 obj.country_name,
#                 round(obj.country_probability, 2),
#                 obj.created_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
#             ])

#         return response


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

        for obj in queryset:
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
