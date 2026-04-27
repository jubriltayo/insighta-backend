import requests

class NationalizeClient:
    BASE_URL = 'https://api.nationalize.io'
    TIMEOUT = 10

    # Country name mapping
    COUNTRY_NAMES = {
        'NG': 'Nigeria',
        'US': 'United States',
        'GB': 'United Kingdom',
        'KE': 'Kenya',
        'TZ': 'Tanzania',
        'CM': 'Cameroon',
        'UG': 'Uganda',
        'SD': 'Sudan',
        'ZA': 'South Africa',
        'GH': 'Ghana',
        'AO': 'Angola',
        'BJ': 'Benin',
        'DZ': 'Algeria',
        'EG': 'Egypt',
        'MA': 'Morocco',
        'FR': 'France',
        'DE': 'Germany',
        'IT': 'Italy',
        'ES': 'Spain',
        'IN': 'India',
        'CN': 'China',
        'JP': 'Japan',
        'BR': 'Brazil',
        'MX': 'Mexico',
        'CA': 'Canada',
        'AU': 'Australia',
        'RU': 'Russia',
        'KR': 'South Korea',
        'ID': 'Indonesia',
        'PK': 'Pakistan',
        'BD': 'Bangladesh',
        'PH': 'Philippines',
        'VN': 'Vietnam',
        'TH': 'Thailand',
        'MY': 'Malaysia',
        'SG': 'Singapore',
        'AE': 'United Arab Emirates',
        'SA': 'Saudi Arabia',
        'IL': 'Israel',
        'TR': 'Turkey',
        'PL': 'Poland',
        'NL': 'Netherlands',
        'SE': 'Sweden',
        'NO': 'Norway',
        'DK': 'Denmark',
        'FI': 'Finland',
        'CH': 'Switzerland',
        'BE': 'Belgium',
        'AT': 'Austria',
        'GR': 'Greece',
        'PT': 'Portugal',
        'IE': 'Ireland',
        'NZ': 'New Zealand',
        'AR': 'Argentina',
        'CL': 'Chile',
        'CO': 'Colombia',
        'PE': 'Peru',
        'VE': 'Venezuela',
    }

    @staticmethod
    def fetch_nationality_data(name: str):
        try:
            response = requests.get(
                NationalizeClient.BASE_URL,
                params={'name': name},
                timeout=NationalizeClient.TIMEOUT
            )

            response.raise_for_status()
            data = response.json()

            # Edge case: no country data
            if not data.get("country") or len(data["country"]) == 0:
                return None
            
            # Pick top country with highest probability
            top_country = max(data["country"], key=lambda x: x["probability"])

            country_id = top_country["country_id"]

            # Get full country name from mapping, or use ID as fallback
            country_name = NationalizeClient.COUNTRY_NAMES.get(country_id, country_id)

            country_probability = round(top_country["probability"], 2)
            
            return {
                "country_id": top_country["country_id"],
                "country_name": country_name,
                "country_probability": country_probability
            }
        except requests.RequestException:
            return None