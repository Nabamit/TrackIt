# TrackIt — Full-Stack Productivity, Streaks, & Blocker Chain Board

TrackIt is a containerized, full-stack productivity dashboard designed for task, project, and habit streak management. It features a stunning glassmorphic UI, timezone-aware streak tracking, retro-active grace freeze protection, task blocker chain visualization, custom Machine Learning completion predictions, and an integrated Generative AI Task Copilot.

---

## 🚀 Tech Stack

- **Backend Framework:** Django 5.0 + Django REST Framework (DRF)
- **Frontend Framework:** Vanilla HTML5, CSS3 (with responsive Glassmorphism design tokens & micro-animations), and modular Javascript (SPA architecture)
- **Database:** PostgreSQL (with SQLite fallbacks for testing and fast local runs)
- **Authentication:** JWT (via `djangorestframework-simplejwt` + localStorage state management)
- **Asynchronous Tasks:** Celery + Redis (broker & results backend)
- **Machine Learning:** Custom Logistic Regression Classifier with online gradient descent training on user logs
- **Generative AI:** Google Gemini API Integration (`google-generativeai`) with custom heuristic offline fallbacks
- **Documentation:** `drf-spectacular` (OpenAPI 3 / Swagger UI)
- **Containerization:** Docker + Docker Compose
- **Testing:** `pytest` + `pytest-django` (31 unit/integration tests)

---

## 📁 Project Structure

```
trackit/
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env
├── .env.example
├── pytest.ini
├── README.md
├── trackit/                  # Project config & Celery init
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── celery.py             # Celery application initialization
├── accounts/                 # User Auth, Profiles, and Custom User model
│   ├── models.py
│   ├── serializers.py        # Added UserProfile & registration fields
│   ├── views.py              # Added UserProfileView
│   └── urls.py
├── projects/                 # Projects CRUD
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
├── tasks/                    # Tasks CRUD, Streaks, ML & AI Services
│   ├── models.py
│   ├── serializers.py
│   ├── views.py              # Mapped AICopilotView and detail actions
│   ├── ml.py                 # Custom Logistic Regression Classifier
│   ├── tasks.py              # Celery task definitions
│   ├── utils.py              # Webhook dispatcher
│   └── urls.py
├── templates/                
│   └── index.html            # Premium responsive glassmorphic SPA template
├── static/
│   ├── css/
│   │   └── styles.css        # Palette variables, dark mode layout, badges, animations
│   └── js/
│       └── app.js            # Auth state router, SVG chart rendering, API client, AI chat
└── tests/                    # isolatated Pytest suites
    ├── conftest.py
    ├── test_auth.py
    ├── test_projects.py
    ├── test_tasks.py
    └── test_advancements.py  # Mapped Profile, ML predictions & AI Copilot tests
```

---

## ⚙️ Core Architecture & Advanced Features

### 1. Modern Glassmorphic Single-Page Application (SPA)
- **Root URL `/`:** Renders a gorgeous dark-themed productivity board designed with Outfit typography, custom neon accents, smooth transitions, and hover lifting cards.
- **Kanban Board:** Groups one-off tasks by status (`Pending`, `In Progress`, `Done`) and features visual lock symbols on blocked tasks.
- **Habit Tracker:** Provides quick check-in and freeze actions directly on daily habit cards.
- **Analytics Center:** Dynamically draws custom radial progress circles for the Consistency Score, displays average completion velocities, and draws SVG bar charts representing weekday failure volatility (Danger Days).

### 2. Timezone-Aware Habit Streak Protection
- **Reset Windows:** Tracks check-ins based on the user's localized timezone (e.g. `America/New_York`) and daily `reset_hour` (e.g. `4` for 4:00 AM resets).
- **Grace Tokens:** Awards 1 Grace Token (up to 3) for every 15-day streak milestone hit. Freezing a habit consumes a token to prevent streak breaks.
- **Auto-Rescue:** Periodic worker tasks automatically apply retroactive freezes if tokens are available, protecting users from accidental streak breaks.

### 3. Task Dependency Blocker Chains
- **Blocker Checking:** Rejects updating task status to `in_progress` or `done` if a prerequisite blocker task is not `done`.
- **Cycle Prevention:** Serializers check for circular dependency loops at the validation layer and block updates forming cycles.

### 4. Custom Machine Learning Task Failure Predictor
- **Dynamic Training:** Implements a custom Logistic Regression Classifier in `tasks/ml.py`. It automatically fits weights on the user's history of checked-in/failed snapshots using online gradient descent.
- **Predictive Factors:** Evaluates task priority, blocker chain length, user's rolling 30-day consistency score, streak momentum, and danger weekday penalties to compute a completion probability.
- **Detail Route:** Accessible at `GET /api/tasks/{id}/predict/` returning success probability, risk level (`low`, `medium`, `high`), and detailed tips.

### 5. Generative AI Copilot Assistant
- **Gemini Core:** Uses the `google-generativeai` package to decompose complex tasks into actionable subtasks or generate motivational habit plans if `GEMINI_API_KEY` is present.
- **Smart Offline Fallback:** Gracefully falls back to custom heuristic breakdowns and streak recovery strategies if no API key is set, ensuring offline functionality.
- **Endpoint:** Mapped to `POST /api/tasks/ai-copilot/` supporting selected task contexts.

---

## 🛠️ Setup & Running

### Environment Configuration
Create a `.env` file in the project root:
```bash
cp .env.example .env
```
*(Optional)* Add your Gemini API key to enable real AI processing:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 1. Local Run (SQLite)
To run the full stack on your host machine:

1. **Activate Virtual Environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```
2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run Migrations & Static Setup:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
4. **Start Development Server:**
   ```bash
   python manage.py runserver
   ```
   Now navigate to `http://127.0.0.1:8000/` in your browser!

### 2. Multi-Container Orchestration (Docker Compose & PostgreSQL)
To spin up the complete full-stack environment with a Postgres Database, Redis broker, and Celery background task worker:
```bash
docker-compose up --build
```
This automatically boots:
- `trackit_db`: PostgreSQL 15 database.
- `trackit_redis`: Redis task broker.
- `trackit_web`: Django API & SPA server at `http://127.0.0.1:8000/`.
- `trackit_celery`: Background worker executing async tasks.

---

## 🧪 Running Tests & Celery Tasks

### Running Pytest
The test suite utilizes isolation with pytest. To execute all 31 unit and integration tests:
```bash
pytest
```

### Triggering Celery Tasks
You can run background operations asynchronously in python via Celery:
```python
from tasks.tasks import reset_streaks_task, send_deadline_reminders_task

# Run immediately in background worker
reset_streaks_task.delay()
send_deadline_reminders_task.delay()
```

---

## 📡 API Endpoints Reference

### 1. Authentication & Profiles (`/api/auth/`)
- `POST /api/auth/register/` - Register a new user (supports `timezone` and `reset_hour`).
- `POST /api/auth/login/` - Login and receive Access + Refresh JWT tokens.
- `GET/PATCH /api/auth/profile/` - View/update user's profile and timezone (Requires Bearer token).

### 2. Projects (`/api/projects/`)
- `GET/POST /api/projects/` - List/create projects.
- `GET/PUT/PATCH/DELETE /api/projects/{id}/` - Manage project.

### 3. Tasks & Advancements (`/api/tasks/`)
- `GET/POST /api/tasks/` - List/create tasks (supports priority/status filters).
- `POST /api/tasks/{id}/check-in/` - Record daily habit check-in, update streaks.
- `POST /api/tasks/{id}/freeze/` - Consume grace token to freeze habit.
- `GET /api/tasks/{id}/predict/` - Retrieve ML completion probability and insights.
- `POST /api/tasks/ai-copilot/` - Ask AI Copilot for task breakdowns or recovery tips.

### 4. Personal Analytics (`/api/analytics/`)
- `GET /api/analytics/dashboard/` - Fetch rolling consistency, completion velocity, and weekday failure volatility.
#   T r a c k I t 
 
 
