# Intel_Agentic-System

Intel Agent is a Competitive Intelligence Tracker that automatically monitors competitor websites for changes and generates AI-driven intelligence briefings using LLaMA. Built with Django, Celery, and LangGraph, this tool automates competitive analysis by taking website snapshots, detecting meaningful updates, and summarizing those changes into insightful briefings.

## 🚀 Features

- **Competitor Tracking**: Add competitor URLs and periodically scrape their page content.
- **Change Detection**: Stores snapshots of scraped pages and calculates content hash differences to identify precisely when and what changed.
- **AI Intelligence Briefings**: Utilizes LangChain, LangGraph, and the Groq API (LLaMA 3.3 70B) to analyze changes and generate high-quality intelligence briefings summarizing competitor updates.
- **Background Automation**: Web scraping (via Playwright & BeautifulSoup) and LLM tasks run asynchronously using Celery and Redis to handle heavy processing seamlessly.
- **User Dashboard**: A Django-powered interface for managing tracked competitors, viewing reports, and reading generated briefings.

## 🛠️ Technology Stack

- **Backend**: Python, Django 4.2
- **Database**: PostgreSQL / SQLite (Development)
- **Task Queue**: Celery & Redis
- **AI / LLM Orchestration**: LangChain, LangGraph
- **LLM Provider**: Groq (`llama-3.3-70b-versatile`)
- **Web Scraping**: Playwright, BeautifulSoup4
- **Deployment**: Gunicorn, WhiteNoise, Docker/Procfile readiness

## 📂 Project Structure

```text
intel_agent/
│
├── accounts/          # User authentication and management
├── agent/             # Core AI and scraping engine (LangGraph, Playwright, Scraper, Parsers)
├── briefings/         # Models and logic for generated AI intelligence briefings
├── competitors/       # Models for competitor tracking and snapshot differences
├── config/            # Django settings (Local and Production configurations)
├── static/            # Static assets (CSS, JS, Images)
├── templates/         # Django HTML templates for the UI
│
├── .env.example       # Example environment variables
├── build.sh           # Build script for deployment (installs deps, playwright, migrates)
├── manage.py          # Django management script
├── Procfile           # Process definitions for deployments (web & worker)
└── requirements.txt   # Python dependencies
```

## ⚙️ Local Development Setup

### 1. Prerequisites
Ensure you have the following installed:
- Python 3.10+
- Redis (running locally or accessible via URL)
- PostgreSQL (Optional, defaults to SQLite for local development)

### 2. Installation

Clone the repository and navigate into the project directory:
```bash
git clone <repository-url>
cd Intel_Agent/intel_agent
```

Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Install the dependencies:
```bash
pip install -r requirements.txt
```

Install Playwright Chromium browser for scraping:
```bash
python -m playwright install chromium
```

### 3. Environment Variables

Create a `.env` file in the project root by copying the provided example:
```bash
cp .env.example .env
```
Update your `.env` file with the required credentials. Make sure to provide your **Groq API Key**:
```dotenv
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
REDIS_URL=redis://localhost:6379/0
```

### 4. Database Setup

Run the migrations to setup the database schema:
```bash
python manage.py migrate
```

(Optional) Create a superuser to access the Django admin:
```bash
python manage.py createsuperuser
```

### 5. Running the Application

You will need to run two processes: the Django web server and the Celery worker.

**Terminal 1: Django Server**
```bash
python manage.py runserver
```

**Terminal 2: Celery Worker**
```bash
# On Windows, you might need to run Celery with `--pool=solo` depending on your environment
celery -A config worker --loglevel=info
```

Your application should now be accessible at `http://127.0.0.1:8000`.

## 🚀 Deployment

The project is structured to easily deploy on PaaS platforms like Render or Heroku. 
The included `build.sh` script automates dependency installation, Playwright browser setup, and database migrations. The `Procfile` declares the necessary web and worker processes.

Ensure you configure all environment variables (e.g., `DATABASE_URL`, `REDIS_URL`, `GROQ_API_KEY`) correctly in your deployment platform's dashboard.
