# Insighta Labs+ Backend

A secure, production-ready Django REST API that powers the Profile Intelligence System. This backend provides advanced demographic querying with filtering, sorting, pagination, natural language search, and full authentication via GitHub OAuth (PKCE) with role-based access control. It serves as the single source of truth for both the CLI tool and web portal.

## 📋 Features

### Core Data Features
- **Advanced Filtering** – Gender, age group, country, age ranges, probability thresholds
- **Sorting** – By age, creation date, gender probability, country probability (asc/desc)
- **Pagination** – Customizable page size (max 50), with HATEOAS-style `links` object
- **Natural Language Search** – e.g., *"young males from nigeria"* → structured filters
- **Rule‑Based Parsing** – No AI/LLM, pure keyword matching for gender, age, country
- **Data Seeding** – Pre‑populate with 2026 profiles from `seed_profiles.json`

### Authentication & Security
- **GitHub OAuth with PKCE** – Supports both browser‑based (web portal) and device (CLI) flows
- **JWT Access Tokens** – Expire in **3 minutes**, signed with user ID, username, role
- **Refresh Tokens** – Expire in **5 minutes**, stored in DB, revoked on use (one‑time use)
- **Role‑Based Access Control (RBAC)**  
  - `admin` – Full access (create/delete profiles, query)  
  - `analyst` – Read‑only (list, search, export, view details)  
  - Default: `analyst`
- **API Versioning** – All `/api/*` requests require `X-API-Version: 1`
- **Rate Limiting** –  
  - `/auth/*` → 10 requests/minute (by IP)  
  - Others → 60 requests/minute per authenticated user (or IP if anonymous)
- **Request Logging** – Every request logs method, path, status code, response time
- **CSV Export** – Filterable, sortable profile export with `Content-Disposition`

## 🛠️ Tech Stack

| Category       | Technologies                                                                 |
|----------------|------------------------------------------------------------------------------|
| Framework      | Django 6.0+, Django REST Framework                                          |
| Database       | PostgreSQL                                                                  |
| Auth           | PyJWT, `secrets`, `hashlib` (PKCE), `uuid7` for primary keys               |
| HTTP Client    | `requests` (external APIs: genderize, agify, nationalize)                  |
| Middleware     | CORS, custom auth, versioning, rate limiting, request logging              |
| Package Manager| `uv`                                                                        |
| Linter         | Ruff                                                                        |
| Server         | Gunicorn (production) / Django runserver (development)                     |
| CI/CD          | GitHub Actions (lint, test on PR to main)                                  |

## 📦 Installation & Setup

### Prerequisites
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) – Fast Python package manager
- PostgreSQL database (local or cloud)
- GitHub OAuth App – Create one at [GitHub Developer Settings](https://github.com/settings/developers)

### Environment Variables
Create a `.env` file in the project root:

```env
# Django
SECRET_KEY=your-django-secret-key
DEBUG=False (or True for development)
ALLOWED_HOSTS=yourdomain.com,railway.app,localhost,127.0.0.1

# Database
PGDATABASE=your_db_name
PGUSER=your_db_user
PGPASSWORD=your_db_password
PGHOST=localhost (or your host)
PGPORT=5432

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_CALLBACK_URL=http://localhost:8000/auth/github/callback  # For web portal
# For production, use your live backend URL

WEB_PORTAL_URL=http://localhost:3000  # URL of your web portal
```

### Setup Steps

```bash
# Clone the repository
git clone https://github.com/your-org/insighta-backend.git
cd insighta-backend

# Install dependencies with uv
uv sync

# Activate virtual environment (uv creates .venv)
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Run migrations
python manage.py migrate

# Seed database with 2026 profiles (idempotent)
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

## 🔐 Authentication & Authorization

### How It Works

1. **Auth Middleware** (`authentication.middleware.AuthMiddleware`)  
   - Reads `Authorization: Bearer <token>` (CLI) or `access_token` cookie (web)  
   - Decodes JWT and attaches `request.auth_user`  
   - No DB lookup per request – role, user_id, username are inside the JWT

2. **Role Enforcement** (`api.permissions.admin_required`)  
   - Decorator checks `request.auth_user.role`  
   - Applied to POST (`/api/profiles`) and DELETE (`/api/profiles/<id>`)  
   - All GET endpoints are allowed for both roles (analyst and admin)

3. **Token Lifecycle**  
   - **Access token** – 3 minutes, carries `{user_id, username, role, exp, iat}`  
   - **Refresh token** – 5 minutes, stored in DB, revoked after use (one‑time use)  
   - **Refresh flow** – `POST /auth/refresh` with refresh token returns new token pair

4. **PKCE Flow for CLI**  
   - CLI generates `code_verifier` and `code_challenge`  
   - Opens GitHub OAuth page, listens on `http://127.0.0.1:port/callback`  
   - Exchanges `code` + `code_verifier` with backend → tokens returned as JSON

5. **Web Flow**  
   - `/auth/github` initiates OAuth with PKCE (state & challenge stored in session)  
   - GitHub redirects to `/auth/github/callback` → access & refresh tokens set as **HttpOnly cookies**

### Auth Endpoints

| Method | Endpoint                     | Description                                                                 |
|--------|------------------------------|-----------------------------------------------------------------------------|
| GET    | `/auth/github`               | Initiates GitHub OAuth (web flow) – redirects to GitHub                    |
| GET    | `/auth/github/callback`      | OAuth callback (web) – sets cookies, redirects to web portal dashboard     |
| POST   | `/auth/cli/token`            | CLI token exchange – expects `{code, code_verifier, redirect_uri?}`        |
| POST   | `/auth/refresh`              | Refresh token pair – body or cookie `refresh_token`                        |
| POST   | `/auth/logout`               | Revokes refresh token (server‑side), clears cookies                        |
| GET    | `/auth/me`                   | Returns authenticated user’s profile (id, username, role, etc.)            |

> **Note:** All auth endpoints are **public** (no version header required).  
> Rate limiting applies: 10 req/min per IP for `/auth/*`.

## 🔌 API Documentation (Protected Endpoints)

All `/api/*` endpoints require:
- `X-API-Version: 1` header (otherwise `400`)
- Valid access token (via `Authorization: Bearer <token>` or `access_token` cookie)
- Active user (`is_active=True`)

### Profile Endpoints

| Method | Endpoint                           | Role       | Description                         |
|--------|------------------------------------|------------|-------------------------------------|
| GET    | `/api/profiles`                    | analyst+   | List profiles (filter, sort, paginate) |
| GET    | `/api/profiles/search?q=...`       | analyst+   | Natural language search             |
| GET    | `/api/profiles/export?format=csv`  | analyst+   | Export filtered profiles to CSV     |
| GET    | `/api/profiles/<id>`               | analyst+   | Retrieve single profile             |
| POST   | `/api/profiles`                    | **admin**  | Create profile (calls genderize/agify/nationalize) |
| DELETE | `/api/profiles/<id>`               | **admin**  | Delete profile                      |

### 1. GET `/api/profiles` – List with Filters, Sorting, Pagination

**Headers:** `X-API-Version: 1`, `Authorization: Bearer <token>`  
**Query parameters** (all optional):

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `gender` | string | `male` / `female` | `female` |
| `age_group` | string | `child`, `teenager`, `adult`, `senior` | `adult` |
| `country_id` | string | ISO 2‑letter code | `NG` |
| `min_age` | int | Minimum age | `18` |
| `max_age` | int | Maximum age | `30` |
| `min_gender_probability` | float | Gender confidence ≥ | `0.7` |
| `min_country_probability` | float | Country confidence ≥ | `0.5` |
| `sort_by` | string | `age`, `created_at`, `gender_probability`, `country_probability` | `age` |
| `order` | string | `asc` or `desc` (default `desc`) | `asc` |
| `page` | int | Page number (default 1) | `2` |
| `limit` | int | Items per page, max 50 (default 10) | `20` |

**Response (200 OK):**
```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 2026,
  "total_pages": 203,
  "links": {
    "self": "/api/profiles?page=1&limit=10",
    "next": "/api/profiles?page=2&limit=10",
    "prev": null
  },
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

### 2. GET `/api/profiles/search` – Natural Language Query

**Headers:** `X-API-Version: 1`, `Authorization: Bearer <token>`  
**Query:** `?q=young males from nigeria&page=1&limit=10` (supports pagination same as above)

Supported patterns:
- `"young males from nigeria"` → gender=male, min_age=16, max_age=24, country=NG
- `"females above 30"` → gender=female, min_age=30
- `"teenagers between 15 and 18"` → age_group=teenager, min_age=15, max_age=18
- `"people from angola"` → country=AO

**Response** – same paginated shape as `GET /api/profiles`.

For uninterpretable query returns `400` with `"message": "Unable to interpret query"`.

### 3. POST `/api/profiles` – Create Profile (Admin Only)

**Headers:** `X-API-Version: 1`, `Authorization: Bearer <token>` (admin role)  
**Body:**
```json
{ "name": "Harriet Tubman" }
```

Behavior:
- Checks idempotency – if name already exists, returns existing profile (`200 OK`)
- Calls Genderize, Agify, Nationalize APIs in sequence
- Stores enriched data using UUID v7 primary key
- **Returns `502 Bad Gateway`** if any external API fails

**Response (201 Created):**
```json
{
  "status": "success",
  "data": {
    "id": "069ea2ec-8180-74a7-8000-f44041f055bd",
    "name": "harriet tubman",
    "gender": "female",
    "gender_probability": 0.97,
    "age": 28,
    "age_group": "adult",
    "country_id": "US",
    "country_name": "United States",
    "country_probability": 0.89,
    "created_at": "2026-04-23T14:38:00Z"
  }
}
```

### 4. GET `/api/profiles/export?format=csv` – CSV Export

**Headers:** `X-API-Version: 1`, `Authorization: Bearer <token>`  
**Query parameters:** Same filters & sorting as `GET /api/profiles` (except pagination not applied).  
**Example:**  
`/api/profiles/export?format=csv&gender=male&country_id=NG&sort_by=age&order=asc`

**Response:**  
- `Content-Type: text/csv`  
- `Content-Disposition: attachment; filename="profiles_<timestamp>.csv"`  
- Columns in order: `id,name,gender,gender_probability,age,age_group,country_id,country_name,country_probability,created_at`

### 5. GET / DELETE `/api/profiles/<id>`

- **GET** → returns single profile (same object shape as in list)
- **DELETE** (admin only) → `204 No Content`

### Error Responses (Standard Format)

All errors follow:
```json
{ "status": "error", "message": "description" }
```

| Status | Scenario |
|--------|----------|
| 400 | Missing API version header / wrong version / invalid query param / unparseable search / missing name on POST |
| 401 | No / invalid / expired access token |
| 403 | Inactive user or insufficient role (admin required) |
| 404 | Profile not found |
| 429 | Rate limit exceeded |
| 502 | External API (genderize/agify/nationalize) failure on profile creation |

## ⚡ Rate Limiting & Logging

### Rate Limiting (`api.rate_limit.RateLimitMiddleware`)

- **Auth endpoints** (`/auth/*`) – 10 requests per minute, keyed by IP (no user required)
- **All other endpoints** – 60 requests per minute per authenticated user (or IP if anonymous)

When limit is exceeded: `429 Too Many Requests`.

### Request Logging (`api.logging_middleware.RequestLoggingMiddleware`)

Every request logs to stdout/console in the format:
```
GET /api/profiles 200 45.23ms
```

## 🌐 Natural Language Parsing

The `NaturalLanguageParser` (rule‑based, no AI) converts plain English queries into structured filters.  
- **Gender** – maps keywords like `male`/`man`/`guy` → `gender=male`; `female`/`woman`/`lady` → `female`  
- **Age** – supports `above X`, `below X`, `between X and Y`, exact `X years old`, and group keywords (`young` → 16‑24, `teenager` → 13‑19, etc.)  
- **Country** – maps keywords (`nigeria`→`NG`, `usa`/`america`→`US`, `uk`→`GB`, etc.)  

See the [full keyword table and edge cases](./README.md#natural-language-parsing) in the original Stage 2 documentation.

## 🧪 Testing

The backend includes **65 tests** covering:
- Authentication enforcement (401/403)
- API versioning
- Role‑based access (admin vs analyst)
- Profile list filters, sorting, pagination
- Natural language search
- CSV export
- Profile creation (idempotency, external API mocks, failures)
- Rate limiting (auth endpoints)
- Token refresh, logout, whoami

### Run tests
```bash
python manage.py test
```

All tests pass on main branch (verified via CI).

## 🏗️ Architecture

```
Client (CLI or Web Portal)
       │
       ▼
┌─────────────────────────────────────────────┐
│  Django Middleware Stack                     │
│  ┌─────────────────────────────────────────┐ │
│  │ RequestLoggingMiddleware                │ │
│  │ AuthMiddleware (attaches request.auth_user)│
│  │ APIVersionMiddleware (enforces X-API-Version)│
│  │ RateLimitMiddleware (per‑user/IP limits)│ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│  URL Routing (config/urls.py)               │
│  ├── /auth/*  → authentication.views       │
│  └── /api/*   → api.views                  │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│  View Layer                                 │
│  ├── ProfileListCreateView (GET, POST)     │
│  ├── ProfileSearchView (GET)               │
│  ├── ProfileExportView (GET)               │
│  ├── ProfileDetailView (GET, DELETE)       │
│  └── Auth views (github, refresh, etc.)    │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│  Business Logic & Helpers                   │
│  ├── ProfileFilter (filter/sort/paginate)  │
│  ├── NaturalLanguageParser (parse query)   │
│  ├── Genderize/Agify/Nationalize clients   │
│  └── Token service (issue/decode JWT)      │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│  PostgreSQL                                 │
│  ├── profiles table (UUIDv7, indexes)      │
│  ├── users table (github_id, role, active) │
│  └── refresh_tokens table (one‑time use)   │
└─────────────────────────────────────────────┘
```

### Key Components

| Component                           | Responsibility |
|-------------------------------------|----------------|
| `authentication.middleware.AuthMiddleware` | Decodes JWT, attaches `auth_user` to request |
| `api.permissions.admin_required`    | Decorator to restrict views to admin users |
| `api.base.AuthenticatedAPIView`     | Base class enforcing auth + active user for DRF APIViews |
| `api.rate_limit.RateLimitMiddleware`| Per‑endpoint rate limiting using Django cache |
| `api.filters.profile_filters`       | Q‑object filtering, sorting, pagination logic |
| `api.parsers.natural_language_parser`| Rule‑based query parsing |
| `authentication.tokens`             | JWT access token (3 min) & refresh token DB records |
| `api.services.*`                    | External API clients (genderize, agify, nationalize) |

## 🚢 Deployment

### Environment Variables (Production)
```env
DEBUG=False
SECRET_KEY=...
ALLOWED_HOSTS=your-backend.com,railway.app
# Database (use cloud PostgreSQL, e.g., Railway, Neon, AWS)
PGDATABASE=...
PGUSER=...
PGPASSWORD=...
PGHOST=...
PGPORT=5432
# GitHub OAuth (production callback URL)
GITHUB_CALLBACK_URL=https://your-backend.com/auth/github/callback
WEB_PORTAL_URL=https://your-webportal.com
```

### CI/CD (GitHub Actions)

Each PR to `main` triggers:
- Linting (`ruff check .`)
- Unit tests (`python manage.py test`)
- Build check (ensures migrations & dependencies are valid)

Example workflow: `.github/workflows/ci.yml`

### Hosting (Recommended: Railway)

1. Push backend repository to GitHub.
2. Create new Railway project → Deploy from GitHub.
3. Add environment variables in Railway dashboard.
4. Railway automatically runs `migrate` (use `release` phase).

## 📁 Project Structure (Selected)

```
insighta-backend/
├── api/
│   ├── __init__.py
│   ├── base.py                     # AuthenticatedAPIView, AuthenticatedView
│   ├── views.py                    # ProfileListCreate, Search, Export, Detail
│   ├── urls.py                     # /api/ routes
│   ├── models.py                   # Profile (UUIDv7, indexes)
│   ├── serializers.py              # ProfileSerializer, CreateProfileSerializer
│   ├── filters/profile_filters.py  # Filtering, sorting, pagination
│   ├── parsers/natural_language_parser.py
│   ├── services/                   # genderize, agify, nationalize clients
│   ├── middleware.py               # APIVersionMiddleware
│   ├── rate_limit.py               # RateLimitMiddleware
│   ├── logging_middleware.py       # RequestLoggingMiddleware
│   ├── permissions.py              # admin_required decorator
│   ├── management/commands/seed_profiles.py
│   └── tests.py                    # 65 tests
├── authentication/
│   ├── __init__.py
│   ├── models.py                   # User, RefreshToken
│   ├── views.py                    # GitHub OAuth, cli/token, refresh, logout, me
│   ├── urls.py
│   ├── middleware.py               # AuthMiddleware
│   ├── tokens.py                   # issue_access_token, decode, issue_refresh_record
│   └── tests.py
├── config/
│   ├── settings.py                 # Django settings, middleware order
│   ├── urls.py                     # Root routing (include api, auth)
│   └── wsgi.py
├── data/seed_profiles.json
├── manage.py
├── pyproject.toml (uv)
├── .env.example
└── README.md
```
