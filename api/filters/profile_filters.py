from django.db.models import Q
from ..models import Profile

class ProfileFilter:
    def __init__(self, params):
        self.params = params
        self.query = Q()

    def apply_filters(self):
        """Apply all filters to the queryset"""
        queryset = Profile.objects.all()

        # Gender filter
        gender = self.params.get('gender')
        if gender:
            self.query &= Q(gender__iexact=gender)

        # Age group filter
        age_group = self.params.get('age_group')
        if age_group:
            self.query &= Q(age_group__iexact=age_group)
        
        # Country filter
        country_id = self.params.get('country_id')
        if country_id:
            self.query &= Q(country_id__iexact=country_id)

        # Min age filter
        min_age = self.params.get('min_age')
        if min_age:
            try:
                self.query &= Q(age__gte=int(min_age))
            except ValueError:
                pass

        # Max age filter
        max_age = self.params.get('max_age')
        if max_age:
            try:
                self.query &= Q(age__lte=int(max_age))
            except ValueError:
                pass

        # Min gender probability filter
        min_gender_prob = self.params.get('min_gender_probability')
        if min_gender_prob:
            try:
                self.query &= Q(gender_probability__gte=float(min_gender_prob))
            except ValueError:
                pass

        # Min country probability filter
        min_country_prob = self.params.get('min_country_probability')
        if min_country_prob:
            try:
                self.query &= Q(country_probability__gte=float(min_country_prob))
            except ValueError:
                pass

        return queryset.filter(self.query)

    def apply_sorting(self, queryset):
        """Apply sorting to queryset"""
        sort_by = self.params.get('sort_by', 'created_at')
        order = self.params.get('order', 'desc')

        # Allow sort fields
        allowed_sort_fields = ['age', 'created_at', 'gender_probability', 'country_probability']

        if sort_by not in allowed_sort_fields:
            sort_by = 'created_at'

        if order.lower() == 'asc':
            return queryset.order_by(sort_by)
        else:
            return queryset.order_by(f'-{sort_by}')
        
    def apply_pagination(self, queryset):
        """Apply pagination and return paginated data with metadata"""
        page = int(self.params.get('page', 1))
        limit = int(self.params.get('limit', 10))

        # Limit max to 50
        limit = min(limit, 50)

        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit

        paginated_queryset = queryset[start:end]

        return {
            'data': paginated_queryset,
            'page': page,
            'limit': limit,
            'total': total
        }
    