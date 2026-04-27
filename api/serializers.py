from rest_framework import serializers
from .models import Profile

class ProfileSerializer(serializers.ModelSerializer):
    gender_probability = serializers.SerializerMethodField()
    country_probability = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'id', 'name', 'gender', 'gender_probability',
            'age', 'age_group', 'country_id', 'country_name',
            'country_probability', 'created_at'
        ]

    def get_gender_probability(self, obj):
        return round(obj.gender_probability, 2)

    def get_country_probability(self, obj):
        return round(obj.country_probability, 2)

    def get_created_at(self, obj):
        return obj.created_at.replace(microsecond=0).isoformat().replace('+00:00', 'Z')


class CreateProfileSerializer(serializers.Serializer):
    name = serializers.CharField()

    def validate_name(self, value):
        if not isinstance(value, str):
            raise serializers.ValidationError("Invalid type")
        if not value.strip():
            raise serializers.ValidationError("Missing or empty name")
        return value.strip()
