# Stories on Trends — Tavily + OpenAI

Automated short-form video script generator that discovers trending stories via **Tavily** (with pytrends fallback), researches them deeply, and generates camera-ready scripts using **OpenAI GPT-4o** — complete with a self-critique loop and automated verification.

## How It Works

```
Trending Topics (Tavily / pytrends)
        ↓
Story Discovery (Tavily search)
        ↓
Deep Research (Tavily advanced + OpenAI structuring)
        ↓
Script Writing (GPT-4o with style rules)
        ↓
Self-Critique (GPT-4o rejection rubric) ←──┐
        ↓                                   │
    Pass? ──── No ──────────────────────────┘
        ↓ Yes
Verification (word count, sentence length, formatting)
        ↓
Dashboard (ready-to-film scripts)
```

## Features

- **Trend Detection** — Tavily-powered trending topic discovery across science, space, news, and viral content lanes
- **Story Discovery** — Automated search and scoring of candidate stories with virality signals
- **Deep Research** — Structured research briefs with facts, numbers, organizations, and hook angles
- **Script Generation** — GPT-4o writer with strict style rules (word count, sentence length, contractions, no fluff)
- **Self-Critique Loop** — GPT-4o critic checks against a 10-point rejection rubric (up to 5 revision cycles)
- **Automated Verification** — Python verifier checks body word count (165–176), hook words, sentence length, banned words, formatting
- **Web Dashboard** — Dark-themed Django UI to browse scripts, stories, trends, and generate on demand

## Tech Stack

- **Backend**: Django 5.x, SQLite
- **AI**: OpenAI GPT-4o (writer + critic)
- **Search**: Tavily API (trends, discovery, research)
- **Fallback**: pytrends (Google Trends)
- **Frontend**: Django templates, Tailwind CSS (CDN)
- **Deployment**: Docker + Docker Compose

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API key
- Tavily API key

### Setup

1. **Clone the repo**
   ```bash
   git clone git@github.com:VisionOra/stories-on-trends-tivily-openai.git
   cd stories-on-trends-tivily-openai
   ```

2. **Create `.env` file**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start the app**
   ```bash
   docker compose up -d --build
   ```

4. **Open the dashboard**
   ```
   http://localhost:8001
   ```

### Generate Scripts

```bash
# Generate 5 scripts (default)
docker compose run --rm generate

# Generate a custom number
docker compose run --rm generate python manage.py generate_scripts --count 3
```

### Refresh Trends

Click **Refresh Trends** on the Trends page, or trends auto-refresh when stale (>24h).

## Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (GPT-4o access required) |
| `TAVILY_API_KEY` | Tavily API key for search and trends |
| `DJANGO_SECRET_KEY` | Django secret key (auto-generated if not set) |
| `DEBUG` | Set to `False` in production |

## Project Structure

```
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── manage.py
├── nickscripts/          # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── scriptgen/            # Main application
    ├── models.py         # 8 models (Story, Script, TrendSnapshot, etc.)
    ├── views.py          # Dashboard, trends, stories, script detail
    ├── urls.py
    ├── admin.py
    ├── services/
    │   ├── trends.py     # Tavily + pytrends trend detection
    │   ├── discovery.py  # Story discovery and scoring
    │   ├── research.py   # Deep research via Tavily + OpenAI
    │   ├── writer.py     # GPT-4o script generation
    │   ├── critic.py     # GPT-4o self-critique
    │   ├── loop.py       # Writer ↔ critic ↔ verifier orchestration
    │   ├── verifier.py   # Automated script verification
    │   └── pipeline.py   # Full pipeline orchestrator
    ├── management/commands/
    │   └── generate_scripts.py
    ├── templates/scriptgen/
    │   ├── base.html
    │   ├── dashboard.html
    │   ├── script_detail.html
    │   ├── stories.html
    │   └── trends.html
    └── skill/            # Verification script and reference materials
        └── verify.py
```

## Pages

| Route | Description |
|---|---|
| `/` | Dashboard — today's generated scripts |
| `/trends/` | Trending topics with click-to-generate |
| `/stories/` | Discovered stories with detail popups |
| `/script/<id>/` | Full script view with verification and revision history |
| `/admin/` | Django admin for model management |

## License

MIT
