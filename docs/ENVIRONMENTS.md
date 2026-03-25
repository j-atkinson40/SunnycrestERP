# Environment Setup Guide

## Overview

| Environment | Database | URL | Branch |
|------------|----------|-----|--------|
| **Local Dev** | PostgreSQL localhost/bridgeable_dev | http://localhost:5173 | any |
| **Production** | Railway PostgreSQL | https://app.getbridgeable.com | main |
| **Staging** | (not yet created) | https://staging.getbridgeable.com | staging |

## Local Development Setup

### Prerequisites
- PostgreSQL 16+ (via Homebrew: `brew install postgresql@16`)
- Python 3.13+ with venv
- Node.js 22+

### First-Time Setup

```bash
# 1. Create local database
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
createdb bridgeable_dev

# 2. Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure local environment
# backend/.env should contain:
cat > .env << 'EOF'
DATABASE_URL=postgresql://localhost:5432/bridgeable_dev
SECRET_KEY=dev-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
EOF

# 4. Run all migrations
DATABASE_URL=postgresql://localhost:5432/bridgeable_dev alembic upgrade head

# 5. Start backend
uvicorn app.main:app --reload --port 8000

# 6. Frontend setup (separate terminal)
cd frontend
npm install
npm run dev
```

### Resetting Local Database

```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
dropdb bridgeable_dev
createdb bridgeable_dev
cd backend && source .venv/bin/activate
DATABASE_URL=postgresql://localhost:5432/bridgeable_dev alembic upgrade head
```

## Production (Railway)

### IMPORTANT RULES
- **NEVER** put the Railway DATABASE_URL in any local .env file
- **NEVER** point local code at the production database
- All production environment variables live in the Railway dashboard ONLY
- Production deploys automatically from the `main` branch

### Required Railway Environment Variables

**Backend service:**
```
DATABASE_URL=<Railway internal PostgreSQL URL>
SECRET_KEY=<secure random string>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=["https://app.getbridgeable.com"]
ANTHROPIC_API_KEY=<your key>
FRONTEND_URL=https://app.getbridgeable.com
PLATFORM_DOMAIN=getbridgeable.com
```

**Frontend service:**
```
VITE_API_URL=https://api.getbridgeable.com
VITE_APP_DOMAIN=getbridgeable.com
```

### Deployment
Push to `main` → Railway auto-deploys both services.
Backend runs `alembic upgrade head` on startup via `railway-start.sh`.

## Staging Environment Setup (Instructions)

### Step 1: Create Railway Staging Services

1. In Railway dashboard, create a new project or add services to existing project
2. Add a **new PostgreSQL database** (separate from production)
3. Add a **new backend service**:
   - Source: same GitHub repo
   - Branch: `staging` (create this branch first)
   - Build command: same as production
   - Start command: same as production
4. Add a **new frontend service**:
   - Source: same GitHub repo, `frontend/` directory
   - Branch: `staging`

### Step 2: Configure Staging Environment Variables

**Staging backend:**
```
DATABASE_URL=<staging PostgreSQL internal URL>
SECRET_KEY=<different from production>
CORS_ORIGINS=["https://staging.getbridgeable.com"]
FRONTEND_URL=https://staging.getbridgeable.com
PLATFORM_DOMAIN=getbridgeable.com
```

**Staging frontend:**
```
VITE_API_URL=https://staging-api.getbridgeable.com
VITE_APP_DOMAIN=getbridgeable.com
```

### Step 3: Set Up Custom Domains

- Backend: `staging-api.getbridgeable.com`
- Frontend: `staging.getbridgeable.com`
- Add CNAME records in DNS pointing to Railway

### Step 4: Create Staging Branch

```bash
git checkout main
git checkout -b staging
git push origin staging
```

### Step 5: Deploy to Staging

Push to `staging` branch → Railway staging services auto-deploy.

### Staging Workflow

1. Develop on feature branches
2. Merge to `staging` → auto-deploys to staging
3. Test on staging.getbridgeable.com
4. Merge `staging` to `main` → auto-deploys to production
