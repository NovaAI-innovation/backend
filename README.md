# mm-bmad-v2 Backend

Backend API repository for the showcase gallery and booking portal.

## Project Description

This is a Python FastAPI backend API that provides endpoints for gallery management, CMS operations, and booking submissions. The backend is deployed on Vercel as serverless functions.

## Setup Instructions

### Prerequisites

- Python 3.12+
- `uv` package manager (required - do NOT use pip)

### Installation

1. Clone this repository
2. Install `uv` if not already installed:
   ```bash
   pip install uv
   ```
3. Install dependencies using `uv`:
   ```bash
   uv sync
   ```
4. Copy `.env.example` to `.env` and configure environment variables
5. Run the development server:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

## Environment Variables

Copy `.env.example` to `.env` and configure:

- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase API key
- `DATABASE_URL`: PostgreSQL connection string
- `CLOUDINARY_CLOUD_NAME`: Cloudinary cloud name
- `CLOUDINARY_API_KEY`: Cloudinary API key
- `CLOUDINARY_API_SECRET`: Cloudinary API secret
- `ADMIN_PASSWORD_HASH`: bcrypt hashed password for CMS access (see below)
- `API_BASE_URL`: Backend API base URL

### Generating Admin Password Hash

The `ADMIN_PASSWORD_HASH` must be a bcrypt-hashed password, NOT a plaintext password.

**Generate password hash using one of these methods:**

1. **Using Python REPL:**
   ```bash
   python -c "import bcrypt; print(bcrypt.hashpw(b'your_password', bcrypt.gensalt()).decode())"
   ```

2. **Using the auth utility (after installing dependencies):**
   ```bash
   uv run python -c "from app.utils.auth import hash_password; print(hash_password('your_password'))"
   ```

3. **Create a temporary script:**
   Create `generate_hash.py`:
   ```python
   from app.utils.auth import hash_password
   password = "your_secure_password"
   hashed = hash_password(password)
   print(f"ADMIN_PASSWORD_HASH={hashed}")
   ```
   Then run: `uv run python generate_hash.py`

**Security Best Practices:**
- Use a strong password (minimum 12 characters recommended)
- Never commit the `.env` file to version control
- Store the hash in the environment variable, NOT the plaintext password
- For production (Vercel), set `ADMIN_PASSWORD_HASH` in Vercel environment variables

## File Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Application configuration
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── routes/              # API route handlers
│   │   ├── __init__.py
│   │   ├── gallery.py
│   │   ├── cms.py
│   │   └── booking.py
│   ├── services/            # Business logic
│   │   ├── __init__.py
│   │   ├── cloudinary_service.py
│   │   └── supabase_service.py
│   └── utils/               # Helper functions
│       ├── __init__.py
│       └── auth.py
├── tests/                   # Test files
│   ├── __init__.py
│   ├── test_gallery.py
│   ├── test_cms.py
│   └── test_auth.py
└── alembic/                 # Database migrations
    ├── versions/
    └── env.py
```

## Development Server

Run the FastAPI development server:

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Package Management

**CRITICAL: Always use `uv` for package management**

- Add dependencies: `uv add <package>`
- Remove dependencies: `uv remove <package>`
- Install from lock file: `uv sync`
- Run scripts: `uv run <script>`

**DO NOT use `pip` - always use `uv`**

## Testing

Run tests using pytest:

```bash
uv run pytest
```

## Deployment

This backend is configured for Vercel deployment. The `vercel.json` configuration file will be created in Epic 2.

Deploy to Vercel:
1. Connect repository to Vercel
2. Configure environment variables in Vercel dashboard
3. Push to main branch (auto-deploys)

## Technology Stack

- **Framework:** FastAPI
- **ORM:** SQLAlchemy 2.0 (async)
- **Database:** Supabase (PostgreSQL)
- **Image Storage:** Cloudinary
- **Package Manager:** uv
- **Testing:** pytest


