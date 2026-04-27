# Intelligence Query Engine

A Django-based REST API that provides advanced demographic querying with filtering, sorting, pagination, and natural language search capabilities.

## 📋 Features

- **Advanced Filtering** - Filter by gender, age group, country, age ranges, and probability thresholds
- **Sorting** - Sort results by age, creation date, or probability scores (ascending/descending)
- **Pagination** - Navigate through large result sets with customizable page sizes (max 50 per page)
- **Natural Language Search** - Query profiles using plain English (e.g., "young males from nigeria")
- **Rule-Based Parsing** - No AI/LLM dependencies, pure keyword matching logic
- **Data Seeding** - Pre-populate database with 2026 profile data from JSON file
- **CORS Enabled** - Accessible from any frontend domain
- **Production Ready** - Proper error handling, timeouts, and status codes

## 🛠️ Tech Stack

- **Framework**: Django 6.0+
- **Database**: PostgreSQL (development and production)
- **HTTP Client**: Requests
- **CORS**: django-cors-headers
- **Package Manager**: uv
- **Linter**: Ruff
- **Server**: Gunicorn (production) / Django runserver (development)

## 📦 Installation

### Prerequisites
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) - Fast Python package manager

### Setup

```bash
# Clone repository
git clone https://github.com/jubriltayo/hng.git
cd 02-intelligence-query

# Install dependencies with uv
uv sync

# Activate virtual environment (uv creates it automatically)
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Run migrations
python manage.py migrate

# Seed database with 2026 profiles
python manage.py seed_profiles

# Start development server
python manage.py runserver
```

### Development Dependencies

```bash
# Install dev tools (ruff for linting)
uv sync --group dev

# Run linter
ruff check .
```

## 🔌 API Documentation

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/profiles` | Create a new profile (idempotent) |
| GET | `/api/profiles` | List all profiles with filtering, sorting, pagination |
| GET | `/api/profiles/search?q={query}` | Natural language search |
| GET | `/api/profiles/{id}` | Retrieve a specific profile |
| DELETE | `/api/profiles/{id}` | Delete a specific profile |

### 1. Get All Profiles with Filters

**GET** `/api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc&page=1&limit=10`

**Query Parameters (all optional):**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| gender | string | Filter by gender | male, female |
| age_group | string | Filter by age group | child, teenager, adult, senior |
| country_id | string | Filter by country code | NG, US, KE |
| min_age | integer | Minimum age | 18 |
| max_age | integer | Maximum age | 30 |
| min_gender_probability | float | Minimum gender confidence | 0.7 |
| min_country_probability | float | Minimum country confidence | 0.5 |
| sort_by | string | Field to sort by | age, created_at, gender_probability, country_probability |
| order | string | Sort direction | asc, desc (default: desc) |
| page | integer | Page number (default: 1) | 2 |
| limit | integer | Items per page, max 50 (default: 10) | 20 |

**Success Response (200 OK):**
```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 2026,
  "data": [
    {
      "id": "069ea26a-1b1e-7a69-8000-b003651e8942",
      "name": "Zodwa Girma",
      "gender": "female",
      "gender_probability": 0.91,
      "age": 71,
      "age_group": "senior",
      "country_id": "RW",
      "country_name": "Rwanda",
      "country_probability": 0.12,
      "created_at": "2026-04-23T14:03:13Z"
    }
  ]
}
```

### 2. Natural Language Search

**GET** `/api/profiles/search?q=young males from nigeria`

**Supported Query Patterns:**

| Query | Generated Filters |
|-------|-------------------|
| "young males from nigeria" | gender=male, min_age=16, max_age=24, country_id=NG |
| "females above 30" | gender=female, min_age=30 |
| "people from angola" | country_id=AO |
| "adult males from kenya" | gender=male, age_group=adult, country_id=KE |
| "teenagers between 15 and 18" | age_group=teenager, min_age=15, max_age=18 |
| "males from us above 40" | gender=male, country_id=US, min_age=40 |

**Success Response (200 OK):**
```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 9,
  "data": [
    {
      "id": "069ea26a-0fd1-7003-8000-3fa5aad63c76",
      "name": "Chidi Igwe",
      "gender": "male",
      "gender_probability": 0.86,
      "age": 19,
      "age_group": "teenager",
      "country_id": "NG",
      "country_name": "Nigeria",
      "country_probability": 0.95,
      "created_at": "2026-04-23T14:03:12Z"
    }
  ]
}
```

**Unable to Interpret Query (400 Bad Request):**
```json
{
  "status": "error",
  "message": "Unable to interpret query"
}
```

### 3. Create Profile

**POST** `/api/profiles`

**Request Body:**
```json
{
  "name": "ella"
}
```

**Success Response (201 Created):**
```json
{
  "status": "success",
  "data": {
    "id": "069ea2ec-8180-74a7-8000-f44041f055bd",
    "name": "ella",
    "gender": "female",
    "gender_probability": 0.99,
    "age": 53,
    "age_group": "adult",
    "country_id": "CM",
    "country_name": "Cameroon",
    "country_probability": 0.1,
    "created_at": "2026-04-23T14:38:00Z"
  }
}
```

### 4. Get Single Profile

**GET** `/api/profiles/{id}`

**Success Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "id": "069ea2ec-8180-74a7-8000-f44041f055bd",
    "name": "ella",
    "gender": "female",
    "gender_probability": 0.99,
    "age": 53,
    "age_group": "adult",
    "country_id": "CM",
    "country_name": "Cameroon",
    "country_probability": 0.1,
    "created_at": "2026-04-23T14:38:00Z"
  }
}
```

### 5. Delete Profile

**DELETE** `/api/profiles/{id}`

**Success Response:** `204 No Content`

## Error Responses

| Status Code | Scenario | Response |
|-------------|----------|----------|
| 400 | Missing or empty name (POST) | `{"status": "error", "message": "Missing or empty name"}` |
| 400 | Unable to interpret search query | `{"status": "error", "message": "Unable to interpret query"}` |
| 400 | Invalid query parameters | `{"status": "error", "message": "Invalid query parameters"}` |
| 404 | Profile not found | `{"status": "error", "message": "Profile not found"}` |
| 502 | External API failure (POST) | `{"status": "error", "message": "Genderize returned an invalid response"}` |

## Natural Language Parsing

### Approach

The parser uses **rule-based pattern matching** (no AI/LLMs) to convert plain English demographic queries into structured filters.

### Supported Keywords

**Gender Keywords:**
| Gender | Keywords |
|--------|----------|
| male | male, males, man, men, boy, boys, guy, guys, gentleman, gentlemen |
| female | female, females, woman, women, girl, girls, lady, ladies |

**Age Keywords & Ranges:**
| Category | Keywords | Age Range |
|----------|----------|-----------|
| child | child, children, kid, kids, young child | 0-12 |
| teenager | teen, teens, teenager, teenagers, adolescent | 13-19 |
| young | young, youth, youths, young people | 16-24 |
| adult | adult, adults, grown, grown-ups | 20-59 |
| senior | senior, seniors, elderly, old, older, aged | 60+ |

**Supported Countries (30+):**
| Country Code | Keywords |
|--------------|----------|
| NG | nigeria, nigerian |
| US | usa, united states, america, american, us |
| GB | uk, united kingdom, britain, british, england |
| KE | kenya, kenyan |
| ZA | south africa, south african |
| GH | ghana, ghanaian |
| ... | (full list in code) |

### Parsing Logic

1. **Token Extraction**: Query is lowercased and scanned for known keywords
2. **Gender Detection**: First matching gender keyword determines gender filter
3. **Age Extraction** (in priority order):
   - "above X", "over X" → `min_age = X`
   - "below X", "under X" → `max_age = X`
   - "between X and Y" → `min_age = X`, `max_age = Y`
   - Age group keywords → Apply predefined age range
   - Exact age patterns → `min_age = max_age = X`
4. **Country Detection**: First matching country keyword determines `country_id`

### Limitations

**What the parser DOES NOT handle:**

1. **Complex Boolean Logic**: "males OR females" → Not supported (use without OR)
2. **Negation**: "not from nigeria" → Not supported
3. **Multiple Countries**: "from nigeria or kenya" → Only first country used
4. **Age Comparisons with Keywords**: "younger than teenagers" → Not supported
5. **Relative Age Terms**: "middle-aged", "early twenties" → Not supported
6. **Compound Phrases**: "young adult males from south africa" → First matching keyword in each category wins
7. **Misspellings**: "nigerai" vs "nigeria" → Not handled
8. **Mixed Gender**: "men and women" → Only first gender detected

**Example Edge Cases:**

| Query | Result | Why |
|-------|--------|-----|
| "people" | Unable to interpret | No filters extracted |
| "young adults" | min_age=16, max_age=24 | "young" overrides "adult" |
| "males from" | gender=male only | Incomplete country phrase |
| "above 30 and below 40" | min_age=30, max_age=40 | AND logic works |
| "30 years old" | min_age=30, max_age=30 | Exact age matching |

## Age Group Classification

| Age Range | Age Group |
|-----------|-----------|
| 0–12 | child |
| 13–19 | teenager |
| 20–59 | adult |
| 60+ | senior |

## Idempotency

- Creating a profile with a name that already exists returns the existing profile
- No duplicate records are created
- Case-insensitive name matching

## 🧪 Testing

### Local Test

```bash
# Create profile
curl -X POST http://localhost:8000/api/profiles \
  -H "Content-Type: application/json" \
  -d '{"name": "ella"}'

# Get all profiles with filters
curl "http://localhost:8000/api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc&page=1&limit=10"

# Natural language search
curl "http://localhost:8000/api/profiles/search?q=young males from nigeria"

# Get single profile
curl "http://localhost:8000/api/profiles/{id}"

# Delete profile
curl -X DELETE "http://localhost:8000/api/profiles/{id}"
```

### Seed Database

```bash
# Seed with 2026 profiles (idempotent)
python manage.py seed_profiles
```

## 🏗️ Architecture

```
Request → URL Router → View → Filter/Parser → Database → Response
                ↓         ↓         ↓           ↓
              CORS    Validation  Natural    Query with
                               Language      filters,
                               Parser        sorting,
                                             pagination
```

### Key Components

| Component | Responsibility |
|-----------|---------------|
| `views.py` | Request handling, response formatting, error handling |
| `models.py` | Profile data model with comprehensive indexes |
| `filters/profile_filters.py` | Advanced filtering, sorting, pagination logic |
| `parsers/natural_language_parser.py` | Rule-based query parsing |
| `management/commands/seed_profiles.py` | Database seeding from JSON |

## 🚢 Deployment

### Railway (Recommended)

Deploy directly from your GitHub repository:
1. Create account at [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Railway auto-detects Django and deploys automatically

### Environment Variables

```env
# Production settings
DEBUG=False
SECRET_KEY=your-secret-key

# Hosts
ALLOWED_HOSTS=yourdomain.com,railway.app,localhost,127.0.0.1
```

## 📁 Project Structure

```
02-intelligence-query/
├── api/
│   ├── __init__.py
│   ├── views.py                      # 4 endpoints (list, search, detail, create)
│   ├── urls.py                       # URL routing
│   ├── models.py                     # Profile model with indexes
│   ├── admin.py
│   ├── management/
│   │   └── commands/
│   │       └── seed_profiles.py      # Database seeder
│   ├── filters/
│   │   └── profile_filters.py        # Filtering, sorting, pagination
│   ├── parsers/
│   │   └── natural_language_parser.py # NLQ parser
│   ├── services/                     # External API clients
│   │   ├── genderize_client.py
│   │   ├── agify_client.py
│   │   └── nationalize_client.py
│   └── migrations/
├── config/
│   ├── settings.py                   # Django config + CORS
│   ├── urls.py                       # Main URL config
│   └── wsgi.py
├── data/                             # Seed data directory
│   └── seed_profiles.json            # 2026 profiles
├── pyproject.toml                    # uv configuration
├── uv.lock
├── manage.py
└── README.md
```

## 🔧 Configuration

### CORS Settings (settings.py)

```python
INSTALLED_APPS = [
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True
```

### Model Indexes

```python
class Meta:
    ordering = ['-created_at']
    indexes = [
        # Compound index for combined filters (most efficient for queries filtering all three)
        models.Index(fields=['gender', 'age_group', 'country_id']),
    ]
```

## ⚡ Performance

- **Response Time**: <500ms (excluding external API latency for POST)
- **Concurrent Requests**: Handles multiple requests without blocking
- **Pagination Limit**: Max 50 records per page to prevent large responses
- **Database Indexes**: All filterable/sortable fields have indexes
- **Query Optimization**: Uses Django's `Q` objects for compound filters

## 🐛 Error Handling Matrix

| Scenario | HTTP Status | User Message |
|----------|-------------|--------------|
| Invalid query parameter | 400 | Invalid query parameters |
| Missing search query | 400 | Missing or empty parameter |
| Unparseable natural language | 400 | Unable to interpret query |
| Missing/empty name (POST) | 400 | Missing or empty name |
| Name as number/object (POST) | 422 | Invalid type |
| Profile not found | 404 | Profile not found |
| Genderize API fails (POST) | 502 | Genderize returned an invalid response |
| Agify API fails (POST) | 502 | Agify returned an invalid response |
| Nationalize API fails (POST) | 502 | Nationalize returned an invalid response |

## 📝 Development Notes

### Filtering Logic

```python
# Age range filters
if min_age:
    query &= Q(age__gte=int(min_age))
if max_age:
    query &= Q(age__lte=int(max_age))

# Probability filters
if min_gender_probability:
    query &= Q(gender_probability__gte=float(min_gender_probability))
```

### Pagination Logic

```python
page = int(params.get('page', 1))
limit = min(int(params.get('limit', 10)), 50)  # Max 50
start = (page - 1) * limit
paginated = queryset[start:start + limit]
```

### Natural Language Parser Flow

```python
def parse(query):
    filters = {}
    
    # Extract gender
    if gender := _extract_gender(query):
        filters['gender'] = gender
    
    # Extract age (ranges, keywords, exact)
    if age_filters := _extract_age(query):
        filters.update(age_filters)
    
    # Extract country
    if country := _extract_country(query):
        filters['country_id'] = country
    
    return filters if filters else None
```

### Testing Strategy

```bash
# Test composite filters
curl "http://localhost:8000/api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc"

# Test pagination
curl "http://localhost:8000/api/profiles?page=2&limit=20"

# Test natural language
curl "http://localhost:8000/api/profiles/search?q=young females from kenya"

# Test seeding (idempotent)
python manage.py seed_profiles  # Second run should skip duplicates
```

## 🔄 External APIs (POST only)

| API | Endpoint | Fields Used |
|-----|----------|-------------|
| Genderize | `https://api.genderize.io` | gender, probability |
| Agify | `https://api.agify.io` | age |
| Nationalize | `https://api.nationalize.io` | country[].country_id, country[].probability |
