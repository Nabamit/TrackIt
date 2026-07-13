# Project Overview & Deployment Guide

This document outlines the resources provided, how to integrate databases (SQLite and PostgreSQL), deploy using Docker, and configure/deploy to Vercel.

---

## 1. What You Provided to Complete This Project

To design, develop, and deliver this project, you provided:
1. **Developer Job Requirements:** A detailed job description specifying:
   - **Key Responsibilities:** Full lifecycle Python backend/fullstack development, writing clean/testable code, troubleshooting, and API integrations.
   - **Required Skills:** Strong proficiency in Python frameworks (Django), database management (relational/NoSQL), RESTful APIs, and version control (Git).
   - **Preferred Qualifications:** Cloud platforms, Docker, frontend technologies (HTML, CSS, JS), asynchronous tasks (Celery), and ML/AI capabilities.
2. **Initial Base Django API Codebase:** A structural Django 5.0 project with:
   - Customized JWT-based user authentication.
   - Relational tables for Projects and Tasks (with streak counters and blocker rules).
   - A command-line script setup for habit resets and deadline check-ins.
   - An isolated testing suite containing 26 test cases.

Using these inputs, I built a **Full-Stack Productivity Platform** including a premium CSS glassmorphism dashboard UI, a custom dynamic Machine Learning completion predictor, Celery worker routines, and a simulated/real Gemini AI Copilot assistant.

---

## 2. Step-by-Step Database Integration

TrackIt supports two databases: **SQLite** (for easy local testing) and **PostgreSQL** (for production-grade containerized deployment).

### Step 2.1: Local SQLite Integration (Development Default)
SQLite is self-contained and requires no server installation.
1. In your `.env` file, ensure the flag is set:
   ```env
   USE_SQLITE=True
   ```
2. Run database migrations to construct tables:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
3. SQLite creates a single file `db.sqlite3` in your root folder automatically.

### Step 2.2: Production PostgreSQL Integration
To hook up a standalone or cloud PostgreSQL database (e.g. AWS RDS or local server):
1. Install the Postgres binary driver (already in requirements.txt):
   ```bash
   pip install psycopg2-binary
   ```
2. Change the `.env` settings to point to your Postgres instance:
   ```env
   USE_SQLITE=False
   DB_HOST=127.0.0.1       # Or cloud endpoint (e.g. database.amazonaws.com)
   DB_PORT=5432
   DB_NAME=trackit_db
   DB_USER=trackit_user
   DB_PASSWORD=trackit_pass
   ```
3. Run migrations. Django will automatically establish the tables inside the Postgres database:
   ```bash
   python manage.py migrate
   ```

---

## 3. Step-by-Step Docker Deployment

Docker packages the entire stack—web server, database, Redis broker, and Celery worker—into isolated containers.

### Step 3.1: Build & Launch the Services
1. Install Docker Desktop on your machine.
2. Open a terminal in the project root and run:
   ```bash
   docker-compose up --build
   ```
   *What this does:*
   - Downloads and starts `postgres:15-alpine` (db) on port 5432.
   - Downloads and starts `redis:7-alpine` (redis) on port 6379.
   - Builds the python application container from `Dockerfile`, runs database migrations, and exposes the Django app at `http://127.0.0.1:8000/`.
   - Starts the `celery` container running the worker process to execute background tasks.

### Step 3.2: Shutdown the Containers
To stop the services while preserving your Postgres database volume:
```bash
docker-compose down
```
To wipe all containers and data volumes:
```bash
docker-compose down -v
```

---

## 4. Deploying to Vercel (Step-by-Step Guide)

Vercel is designed for serverless architectures. While perfect for frontend apps, deploying full-stack Django backends with background task queues (Celery) requires careful configuration because **serverless functions are stateless and time-limited**.

### Step 4.1: Serverless DB & Redis Preparation
Because Vercel serverless containers spin down, they cannot host local databases or persistent Redis processes.
1. **PostgreSQL:** Spin up a serverless Postgres instance on [Neon.tech](https://neon.tech/) or Supabase. Get the connection string.
2. **Redis:** Register a serverless Redis database on [Upstash Redis](https://upstash.com/) to act as the cloud Celery broker. Get the URL.

### Step 4.2: Configure `vercel.json`
Create a `vercel.json` file in the project root to route requests to the Django WSGI entrypoint using the `vercel-wsgi` builder:
```json
{
  "version": 2,
  "builds": [
    {
      "src": "trackit/wsgi.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "dest": "static/$1"
    },
    {
      "src": "/(.*)",
      "dest": "trackit/wsgi.py"
    }
  ]
}
```

### Step 4.3: Adjust `trackit/wsgi.py`
Open `trackit/wsgi.py` and expose the wsgi application under an alias `app` (which Vercel looks for):
```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trackit.settings')

application = get_wsgi_application()
app = application  # Vercel needs this reference
```

### Step 4.4: Handle Celery Worker limitations in Serverless
> [!WARNING]
> **Vercel cannot run a continuous `celery worker` process.** Serverless functions terminate after executing.
> To run background tasks, choose one of these options:
> - **Option A (Recommended):** Use a serverless scheduling service like **Vercel Cron Jobs** to make recurring HTTP GET/POST requests to endpoints that call the logic directly.
> - **Option B:** Deploy the backend on **Render**, **Railway**, or **AWS ECS/App Runner** instead, which supports persistent worker processes.

### Step 4.5: Perform the Deployment
1. Install the Vercel CLI:
   ```bash
   npm install -g vercel
   ```
2. Log in and initiate deployment in your project directory:
   ```bash
   vercel login
   vercel
   ```
3. Set your production environment variables in the Vercel Dashboard settings:
   - `USE_SQLITE = False`
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` (Neon connection details)
   - `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (Upstash connection details)
4. Deploy to production:
   ```bash
   vercel --prod
   ```
