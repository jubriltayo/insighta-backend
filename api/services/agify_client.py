import requests

class AgifyClient:
    BASE_URL = 'https://api.agify.io'
    TIMEOUT = 10

    @staticmethod
    def fetch_age_data(name: str):
        try:
            response = requests.get(
                AgifyClient.BASE_URL,
                params={'name': name},
                timeout=AgifyClient.TIMEOUT
            )

            response.raise_for_status()
            data = response.json()

            # Edge case: invalid response
            if data.get("age") is None:
                return None
            
            # Age group classification
            age = data.get('age')
            if age <= 12:
                age_group = 'child'
            elif age <=19:
                age_group = 'teenager'
            elif age <= 59:
                age_group = 'adult'
            else:
                age_group = 'senior'

            return {
                "age": age,
                "age_group": age_group
            }
        except requests.RequestException:
            return None