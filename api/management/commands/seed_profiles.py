import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from api.models import Profile

class Command(BaseCommand):
    help = 'Seed database with profiles from JSON file'
    
    def handle(self, *args, **options):
        file_path = settings.BASE_DIR / 'data' / 'seed_profiles.json'
        
        if not file_path.exists():
            self.stdout.write(
                self.style.ERROR(f'File not found: {file_path}')
            )
            self.stdout.write('Please place seed_profiles.json in the data/ folder')
            return
        
        with open(file_path, 'r') as file:
            data = json.load(file)
        
        # Get the actual profiles list
        profiles = data.get('profiles', [])
        
        if not profiles:
            self.stdout.write(
                self.style.ERROR('No profiles found in JSON file')
            )
            return
        
        created_count = 0
        skipped_count = 0
        
        for profile_data in profiles:
            _, created = Profile.objects.get_or_create(
                name=profile_data['name'],
                defaults={
                    'gender': profile_data['gender'],
                    'gender_probability': profile_data['gender_probability'],
                    'age': profile_data['age'],
                    'age_group': profile_data['age_group'],
                    'country_id': profile_data['country_id'],
                    'country_name': profile_data['country_name'],
                    'country_probability': profile_data['country_probability'],
                }
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Seeding complete: {created_count} created, {skipped_count} skipped'
            )
        )