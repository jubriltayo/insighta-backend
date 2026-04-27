import requests

class GenderizeClient:
    BASE_URL = "https://api.genderize.io"
    TIMEOUT = 10

    @staticmethod
    def fetch_gender_data(name: str):
        try:
            response = requests.get(
                GenderizeClient.BASE_URL,
                params={"name": name},
                timeout=GenderizeClient.TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            # Edge case: invalid response
            if data.get('gender') is None or data.get('count', 0) == 0:
                return None
            
            return {
                'gender': data.get('gender'),
                'probability': data.get('probability'),
            }
        except requests.RequestException:
            return None