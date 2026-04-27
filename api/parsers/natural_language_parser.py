import re
from ..filters.profile_filters import ProfileFilter

class NaturalLanguageParser:
    """
    Rule-based natural language parser for demographic queries.
    Supports keywords for gender, age, and country
    """

    # Keyword mappings
    GENDER_KEYWORDS = {
        'male': ['male', 'males', 'man', 'men', 'boy', 'boys', 'guy', 'guys', 'gentleman', 'gentlemen'],
        'female': ['female', 'females', 'woman', 'women', 'girl', 'girls', 'lady', 'ladies']
    }

    AGE_KEYWORDS = {
        'child': ['child', 'children', 'kid', 'kids', 'young child'],
        'teenager': ['teen', 'teens', 'teenager', 'teenagers', 'adolescent', 'adolescents'],
        'young': ['young', 'youth', 'youths', 'young people'],
        'adult': ['adult', 'adults', 'grown', 'grown-ups'],
        'senior': ['senior', 'seniors', 'elderly', 'old', 'older', 'aged']
    }

    AGE_RANGES = {
        'young': {'min': 16, 'max': 24},
        'child': {'min': 0, 'max': 12},
        'teenager': {'min': 13, 'max': 19},
        'adult': {'min': 20, 'max': 59},
        'senior': {'min': 60, 'max': 120}
    }

    COUNTRY_KEYWORDS = {
        'NG': ['nigeria', 'nigerian'],
        'US': ['usa', 'united states', 'america', 'american', 'us'],
        'GB': ['uk', 'united kingdom', 'britain', 'british', 'england'],
        'CA': ['canada', 'canadian'],
        'AU': ['australia', 'australian'],
        'IN': ['india', 'indian'],
        'FR': ['france', 'french'],
        'DE': ['germany', 'german'],
        'IT': ['italy', 'italian'],
        'ES': ['spain', 'spanish'],
        'BR': ['brazil', 'brazilian'],
        'MX': ['mexico', 'mexican'],
        'ZA': ['south africa', 'south african'],
        'CN': ['china', 'chinese'],
        'JP': ['japan', 'japanese'],
        'KR': ['korea', 'korean', 'south korea'],
        'RU': ['russia', 'russian'],
        'AO': ['angola', 'angolan'],
        'BJ': ['benin', 'beninese'],
        'GH': ['ghana', 'ghanaian'],
        'KE': ['kenya', 'kenyan'],
        'EG': ['egypt', 'egyptian'],
        'DZ': ['algeria', 'algerian'],
        'MA': ['morocco', 'moroccan'],
        'SA': ['saudi arabia', 'saudi'],
        'AE': ['uae', 'united arab emirates'],
        'PK': ['pakistan', 'pakistani'],
        'BD': ['bangladesh', 'bangladeshi'],
        'PH': ['philippines', 'filipino'],
        'VN': ['vietnam', 'vietnamese'],
        'TH': ['thailand', 'thai'],
        'MY': ['malaysia', 'malaysian'],
        'SG': ['singapore', 'singaporean'],
    }

    @classmethod
    def parse(cls, query_string):
        """
        Parse natural language query and return filter parameters
        
        Returns:
            dict: Filter parameters for ProfileFilter
        """
        if not query_string:
            return None
        
        query = query_string.lower().strip()
        filters = {}

        # Parse gender
        gender = cls._extract_gender(query)
        if gender:
            filters['gender'] = gender

        # Parse age
        age_filters = cls._extract_age(query)
        if age_filters:
            filters.update(age_filters)

        # Parse country
        country = cls._extract_country(query)
        if country:
            filters['country_id'] = country

        return filters if filters else None

    @classmethod
    def _extract_gender(cls, query):
        """Extract gender from query"""
        for gender, keywords in cls.GENDER_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    return gender
        return None
    
    @classmethod
    def _extract_age(cls, query):
        """Extract age-related filter from query"""
        filters = {}

         # Check for "above X", "below X", "over X", "under X"
        above_match = re.search(r'(?:above|over|greater than|older than)\s+(\d+)', query)
        if above_match:
            filters['min_age'] = int(above_match.group(1))
        
        below_match = re.search(r'(?:below|under|less than|younger than)\s+(\d+)', query)
        if below_match:
            filters['max_age'] = int(below_match.group(1))
        
        # Check for "between X and Y"
        between_match = re.search(r'between\s+(\d+)\s+and\s+(\d+)', query)
        if between_match:
            filters['min_age'] = int(between_match.group(1))
            filters['max_age'] = int(between_match.group(2))

        for age_group, keywords in cls.AGE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    if age_group in cls.AGE_RANGES:
                        age_range = cls.AGE_RANGES[age_group]
                        if 'min_age' not in filters:
                            filters['min_age'] = age_range['min']
                        if 'max_age' not in filters:
                            filters['max_age'] = age_range['max']
                    
                    # Also set age_group filter if exact match is found
                    if age_group in ['child', 'teenager', 'adult', 'senior']:
                        filters['age_group'] = age_group
                    break
        
        # Extract exact age (e.g. "age 25", "25 years old")
        exact_age_match = re.search(r'(?:age|at age)\s+(\d+)|(\d+)\s+(?:years? old|yo)', query)
        if exact_age_match:
            age = exact_age_match.group(1) or exact_age_match.group(2)
            filters['min_age'] = int(age)
            filters['max_age'] = int(age)

        return filters
    
    @classmethod
    def _extract_country(cls, query):
        """Extract country from query"""
        for country_code, keywords in cls.COUNTRY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    return country_code
        return None
    