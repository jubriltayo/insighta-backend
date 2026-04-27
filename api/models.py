from uuid_extensions import uuid7
from django.db import models

def generate_uuid7():
    return uuid7()

class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=generate_uuid7, editable=False)
    name = models.CharField(max_length=100, unique=True)
    gender = models.CharField(max_length=10, db_index=True)
    gender_probability = models.FloatField(db_index=True)
    age = models.IntegerField(db_index=True)
    age_group = models.CharField(max_length=20, db_index=True)
    country_id = models.CharField(max_length=2, db_index=True)
    country_name = models.CharField(max_length=100)
    country_probability = models.FloatField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['gender', 'age_group', 'country_id']),
        ]

    def __str__(self):
        return f'{self.name} - {self.gender} - {self.age_group} - {self.country_id}'
    