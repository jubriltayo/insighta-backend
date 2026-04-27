import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

from .models import Profile
from .filters.profile_filters import ProfileFilter
from .parsers.natural_language_parser import NaturalLanguageParser
from .services.genderize_client import GenderizeClient
from .services.agify_client import AgifyClient
from .services.nationalize_client import NationalizeClient

# Helper function
def format_profile_response(profile):
    """Format profile data consistently across all endpoints"""
    return {
        "id": str(profile.id),
        "name": profile.name,
        "gender": profile.gender,
        "gender_probability": round(profile.gender_probability, 2),
        "age": profile.age,
        "age_group": profile.age_group,
        "country_id": profile.country_id,
        "country_name": profile.country_name,
        "country_probability": round(profile.country_probability, 2),
        "created_at": profile.created_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    }

@csrf_exempt
@require_http_methods(["GET", "POST", "OPTIONS"])
def profile_list(request):
    """
    GET /api/profiles - List all profiles (with filters, sorting, and pagination)
    POST /api/profiles - Create a new profile
    """

    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)
    
    # Get all profiles
    if request.method == "GET":
        # Get all query parameters
        params = request.GET.dict()

        # Validate parameters - return error for invalid parameters (except known ones)
        known_params = {
            "gender", "age_group", "country_id", "min_age", "max_age",
            "min_gender_probability", "min_country_probability",
            "sort_by", "order", "page", "limit"
        }
        invalid_params = set(params.keys()) - known_params
        if invalid_params:
            return JsonResponse({
                "status": "error",
                "message": "Invalid query parameters"
            }, status=400)
        
        # Apply filters, sorting, and pagination
        filter_handler = ProfileFilter(params)
        queryset = filter_handler.apply_filters()
        queryset = filter_handler.apply_sorting(queryset)
        paginated_data = filter_handler.apply_pagination(queryset)

        # Format response
        data = [format_profile_response(profile) for profile in paginated_data['data']]

        return JsonResponse({
            "status": "success",
            "page": paginated_data['page'],
            "limit": paginated_data['limit'],
            "total": paginated_data['total'],
            "data": data
        }, status=200)
    
    # Create new profile
    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                "status": "error",
                "message": "Invalid JSON"
            }, status=400)

        name = body.get("name", "").strip()

        # Validation
        if not name:
            return JsonResponse({
                "status": "error",
                "message": "Missing or empty name"
            }, status=400)
        
        if not isinstance(name, str):
            return JsonResponse({
                "status": "error",
                "message": "Invalid type"
            }, status=400)
        
        # Check if profile already exists (idempotency)
        existing_profile = Profile.objects.filter(name__iexact=name).first()
        if existing_profile:
            return JsonResponse({
                "status": "success",
                "message": "Profile already exists",
                "data": format_profile_response(existing_profile)
            }, status=200)
        
        # Fetch data from external APIs
        gender_data = GenderizeClient.fetch_gender_data(name)
        if not gender_data:
            return JsonResponse({
                "status": "error",
                "message": "Genderize returned invalid response"
            }, status=502)
        
        age_data = AgifyClient.fetch_age_data(name)
        if not age_data:
            return JsonResponse({
                "status": "error",
                "message": "Agify returned invalid response"
            }, status=502)
        
        nationality_data = NationalizeClient.fetch_nationality_data(name)
        if not nationality_data:
            return JsonResponse({
                "status": "error",
                "message": "Nationalize returned invalid response"
            }, status=502)
        
        # Create new profile
        profile = Profile.objects.create(
            name=name.lower(),
            gender=gender_data["gender"],
            gender_probability=gender_data["probability"],
            age=age_data["age"],
            age_group=age_data["age_group"],
            country_id=nationality_data["country_id"],
            country_name=nationality_data["country_name"],
            country_probability=nationality_data["country_probability"]
        )

        return JsonResponse({
            "status": "success",
            "data": format_profile_response(profile)
        }, status=201)
    
@require_http_methods(["GET", "OPTIONS"])
def search_profiles(request):
    """
    GET /api/profiles/search?q=...
    Search profiles using natural language query
    """
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)
    
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({
            "status": "error",
            "message": "Missing or empty parameter"
        }, status=400)

    # Parse natural language query to extract filters
    filters = NaturalLanguageParser.parse(query)
    if not filters:
        return JsonResponse({
            "status": "error",
            "message": "Unable to interpret query"
        }, status=400)
    
    # Add pagination parameters from request
    page = request.GET.get('page', 1)
    limit = request.GET.get('limit', 10)
    filters['page'] = page
    filters['limit'] = limit

    # Apply filters to queryset
    filter_handler = ProfileFilter(filters)
    queryset = filter_handler.apply_filters()
    queryset = filter_handler.apply_sorting(queryset)
    paginated_data = filter_handler.apply_pagination(queryset)

    # Format response
    data = [format_profile_response(profile) for profile in paginated_data['data']]

    return JsonResponse({
        "status": "success",
        "page": paginated_data['page'],
        "limit": paginated_data['limit'],
        "total": paginated_data['total'],
        "data": data,
    }, status=200)

@require_http_methods(["GET", "DELETE", "OPTIONS"])
def profile_detail(request, profile_id):
    """
    GET /api/profiles/{id} - Retrieve a specific profile
    DELETE /api/profiles/{id} - Delete a specific profile
    """
    
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)
    
    try:
        profile = Profile.objects.get(id=profile_id)
    except (ValidationError, Profile.DoesNotExist):
        return JsonResponse({
            "status": "error",
            "message": "Profile not found"
        }, status=404)

    if request.method == "GET":
        return JsonResponse({
            "status": "success",
            "data": format_profile_response(profile)
        }, status=200)
    
    if request.method == "DELETE":
        profile.delete()
        return JsonResponse({}, status=204)
    