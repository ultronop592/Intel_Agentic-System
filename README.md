# Intel_Agentic-System

Intel Agent is a Competitive Intelligence Tracker that automatically monitors competitor websites for changes and generates AI-driven intelligence briefings using LLaMA. Built with Django, Celery, and LangGraph, this tool automates competitive analysis by taking website snapshots, detecting meaningful updates, and summarizing those changes into insightful briefings.

## Features

- **Competitor Tracking**: Add competitor URLs and periodically scrape their page content.
- **Change Detection**: Stores snapshots of scraped pages and calculates content hash differences to identify precisely when and what changed.
- **AI Intelligence Briefings**: Uses LangChain, LangGraph, and the Groq API (LLaMA 3.3 70B) to analyze changes and generate high-quality intelligence briefings.
- **Chat with Intelligence**: Ask questions about your competitors and get AI-powered answers based on scraped data.
- **SWOT Analysis**: Auto-generated strategic SWOT reports from competitor briefings.
- **Rate Limiting**: Per-user daily API limits (default: 20 requests/day) to prevent overuse.
- **Background Automation**: Web scraping (via Playwright) and LLM tasks run asynchronously using Celery and Redis.

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Competitor │────▶│  Scraping    │────▶│  Change     │
│  URLs       │     │  (Playwright)│     │  Detection  │
└─────────────┘     └──────────────┘     └─────────────┘
                                                  │
                                                  ▼
                    ┌──────────────┐     ┌─────────────┐
                    │  User Chat   │◀────│  LLM        │
                    │  Interface  │     │  (Groq)     │
                    └──────────────┘     └─────────────┘
```

### Core Components

1. **Scraper** (`agent/scraper.py`): Uses Playwright to fetch web pages
2. **Discovery** (`agent/discovery.py`): Finds sub-pages and links
3. **Parser** (`agent/parser.py`): Extracts clean text from HTML
4. **Diff Engine** (`agent/differ.py`): Computes content hashes & differences
5. **LangGraph Agent** (`agent/graph.py`): Orchestrates the scraping → analysis pipeline
6. **LLM Factory** (`agent/llm_factory.py`): Creates Groq LLM clients with rate limiting

### Rate Limiting System

- **Daily Limit**: 20 requests per user (configurable via `DAILY_API_LIMIT`)
- **Storage**: Redis-based counter
- **Where Enforced**:
  - `agent/chat.py` - Chat queries
  - `agent/graph.py` - Competitor briefings
  - `agent/swot.py` - SWOT analysis

```python
# Usage example
from agent.llm_factory import get_llm, invoke_llm, RateLimitExceeded

try:
    llm = get_llm(user_id=request.user.id)
    response = invoke_llm(llm, messages, user_id=request.user.id)
except RateLimitExceeded:
    return JsonResponse({"error": "Daily limit exceeded"}, status=429)
```

## Technology Stack

- **Backend**: Python 3.10+, Django 4.2
- **Database**: PostgreSQL (Production) / SQLite (Development)
- **Task Queue**: Celery & Redis
- **AI / LLM**: LangChain, LangGraph, Groq (`llama-3.3-70b-versatile`)
- **Web Scraping**: Playwright, BeautifulSoup4
- **Frontend**: HTML, CSS (Tailwind-style custom)

## Project Structure

```
intel_agent/
├── accounts/           # User authentication
│   ├── models.py      # User model extensions
│   └── templates/    # Login, signup, profile templates
├── agent/            # Core AI engine
│   ├── scraper.py    # Playwright page fetching
│   ├── discovery.py # Sub-page discovery
│   ├── parser.py    # HTML text extraction
│   ├── differ.py    # Hash & diff computation
│   ├── graph.py     # LangGraph orchestration
│   ├── chat.py     # User chat interface
│   ├── swot.py     # SWOT analysis generation
│   ├── llm_factory.py   # LLM client + rate limiting
│   └── rate_limiter.py  # Per-user rate limits
├── briefings/        # Intelligence briefings
│   ├── models.py    # Briefing, SwotReport models
│   └── views.py    # Briefing CRUD views
├── competitors/    # Competitor tracking
│   ├── models.py   # Competitor, Snapshot models
│   └── views.py   # Competitor management
├── config/          # Django settings
│   ├── settings/
│   │   ├── base.py    # Shared config
│   │   ├── local.py   # Development
│   │   └── production.py # Production settings
│   └── celery.py   # Celery configuration
├── static/          # CSS, JS assets
└── templates/      # Base templates
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | - | Groq API key from [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | LLM model to use |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis connection URL |
| `DATABASE_URL` | No | SQLite | PostgreSQL connection (production) |
| `DAILY_API_LIMIT` | No | `20` | API requests per user per day |
| `SECRET_KEY` | Yes | - | Django secret key |
| `ALLOWED_HOSTS` | No | - | Comma-separated allowed hosts |

## Local Development Setup

### Prerequisites
- Python 3.10+
- Redis (running locally)
- PostgreSQL (optional, SQLite for dev)

### Installation

```bash
# Clone and navigate
git clone <repo-url>
cd intel_agent

# Create virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
python -m playwright install chromium

# Copy environment file
cp .env.example .env
# Edit .env with your GROQ_API_KEY
```

### Database Setup

```bash
python manage.py migrate
python manage.py createsuperuser  # Optional
```

### Running the Application

```bash
# Terminal 1: Django server
python manage.py runserver

# Terminal 2: Celery worker
celery -A config worker --loglevel=info
```

Visit `http://127.0.0.1:8000`

## Deployment

### Railway (Recommended - Free Tier)

1. Go to [railway.app](https://railway.app)
2. Connect GitHub repo
3. Create project → Deploy from GitHub
4. Add Redis plugin (free)
5. Add environment variables in Railway dashboard:
   - `GROQ_API_KEY` (your key)
6. Deploy

```bash
# Railway CLI deployment
npm i -g @railway/cli
railway login
railway init
railway up
```

### Render + Neon + Upstash

1. **Neon (Database)**
   - Create project at [neon.tech](https://neon.tech)
   - Copy connection string from dashboard

2. **Upstash (Redis)**
   - Create database at [upstash.com](https://upstash.com)
   - Copy Redis URL (format: `redis://default:password@host:port`)

3. **Render**
   - Connect GitHub repo to Render
   - Create web + worker services
   - Add environment variables:
     ```
     DATABASE_URL=postgresql://...
     REDIS_URL=redis://...
     GROQ_API_KEY=your_key
     DAILY_API_LIMIT=20
     SECRET_KEY=generate_secure_key
     ALLOWED_HOSTS=your-app.onrender.com
     DEBUG=False
     ```
   - Deploy

### Docker

```bash
docker build -t intel-agent .
docker run -p 8000:8000 --env-file .env intel-agent
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Landing page |
| `/accounts/login/` | User login |
| `/accounts/signup/` | User registration |
| `/competitors/` | Competitor list |
| `/competitors/add/` | Add competitor |
| `/competitors/<id>/` | Competitor detail |
| `/briefings/` | Intelligence briefings |
| `/briefings/<id>/` | Briefing detail |
| `/agent/chat/` | AI chat interface |
| `/agent/swot/` | SWOT analysis |

## Troubleshooting

### Rate limit exceeded
- Check remaining: Use Django admin or add debug endpoint
- Wait 24 hours or increase `DAILY_API_LIMIT`

### Celery not running
- Ensure Redis is running
- Check `REDIS_URL` in environment

### Scraping errors
- Run `python -m playwright install chromium`
- Check website accessibility

### Groq API errors
- Verify `GROQ_API_KEY` is correct
- Check API quota at console.groq.com

## License

MIT