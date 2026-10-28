# iSearchFrom — Reddit Control

Mission control dashboard for the iSearchFrom Reddit visibility campaign.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    nginx (port 80/443)                   │
│  ┌──────────────┐  ┌──────────────────────────────────┐ │
│  │  Frontend    │  │         Backend (FastAPI)        │ │
│  │  SvelteKit   │  │  Port 8000                       │ │
│  │  SPA + CSS   │  │  - Threads API                   │ │
│  │  :3000       │  │  - Drafts API                    │ │
│  └──────┬───────┘  │  - Accounts API                  │ │
│         │          │  - SSE live updates              │ │
│         │          └────────────┬─────────────────────┘ │
│         │                       │                        │
│  ┌──────┴───────────────────────┴──────────────────┐    │
│  │           SQLite Database (volume)              │    │
│  │           threads / drafts / accounts / tracker │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │         Radar Scanner (cron job)                │    │
│  │  Reads Reddit → Scores → Pushes to API          │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │         Reddit Poster (Playwright)              │    │
│  │  Browser-based commenting via bot accounts      │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Clone & configure

```bash
git clone git@github.com:ergabit/isf-reddit-control.git
cd isf-reddit-control
cp .env.example .env
```

### 2. Add Reddit bot accounts

Edit `data/accounts.json` (created on first run):

```json
[
  {
    "username": "searchnerd42",
    "password": "bot_pass_123",
    "email": "searchnerd42+reddit@gmail.com",
    "is_active": true,
    "karma": 0,
    "ban_risk": 0
  },
  {
    "username": "seo_watcher",
    "password": "bot_pass_456",
    "email": "seo_watcher+reddit@gmail.com",
    "is_active": true,
    "karma": 0,
    "ban_risk": 0
  }
]
```

### 3. Start with Docker Compose

```bash
docker compose up -d --build
```

### 4. Access the dashboard

- **Dashboard**: http://localhost:3000 (or your server IP)
- **Backend API**: http://localhost:8000
- **Health check**: http://localhost:8000/api/health

### 5. Run the radar

```bash
# Manual sweep
docker exec isf-reddit-backend python radar_scanner.py all

# Or let the radar-scanner container run automatically
docker compose up -d radar-scanner
```

## Dashboard Features

### 🔍 Findings
- Real-time thread feed from the radar
- Filter by status, subreddit, minimum score
- Score visualization (0-100 radar score)
- Direct links to Reddit threads

### 📝 Drafts
- AI-drafted replies for each thread
- **Edit** inline
- **Approve** to mark for posting
- **Rewrite** with feedback
- **Post** via selected bot account
- **Skip** to discard

### 👥 Accounts
- Add/remove bot accounts
- View karma, daily limits, ban risk
- Toggle active/inactive

### 📊 Tracker
- All posted replies with engagement metrics
- Upvotes, replies, UTM clicks

### ⚙️ Settings
- **Supervised vs Auto mode** toggle
- Auto-post threshold slider (40-90)
- Daily limits per account
- Quick actions

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/threads` | List threads (filterable) |
| POST | `/api/threads` | Add a thread |
| GET | `/api/drafts` | List drafts (filterable) |
| POST | `/api/drafts` | Create draft |
| POST | `/api/drafts/:id/approve` | Approve draft |
| POST | `/api/drafts/:id/post` | Mark as posted |
| POST | `/api/drafts/:id/skip` | Skip draft |
| POST | `/api/drafts/:id/rewrite` | Request rewrite |
| PUT | `/api/drafts/:id/body` | Edit draft body |
| GET | `/api/accounts` | List accounts |
| POST | `/api/accounts` | Add account |
| DELETE | `/api/accounts/:username` | Delete account |
| GET | `/api/config` | Get config |
| PUT | `/api/config` | Update config |
| GET | `/api/tracker` | List tracker entries |
| GET | `/api/stats` | KPI stats |
| POST | `/api/radar/import` | Bulk import threads |
| GET | `/api/health` | Health check |
| GET | `/events` | SSE live events |

## Deployment to Server

```bash
# On your server (192.168.0.38)
cd /home/hermes/workspaces/personal/isf-reddit-control
docker compose up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f backend
docker compose logs -f frontend
```

## File Structure

```
isf-reddit-control/
├── backend/
│   ├── app.py              # FastAPI main app
│   ├── radar_scanner.py    # Radar CLI wrapper
│   ├── reddit_poster.py    # Playwright poster
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── routes/
│   │   │   └── +page.svelte   # Main dashboard
│   │   └── lib/
│   │       ├── constants.ts
│   │       └── api.ts
│   ├── static/
│   │   └── app.css           # Dark theme styles
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── Dockerfile
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Gray Hat Strategy

- **No disclosure** — bots post as regular users
- **Load balancing** — spread posts across accounts
- **Daily limits** — max 8 posts + 25 comments per account/day
- **Ban risk tracking** — monitor per-account risk
- **Natural patterns** — vary posting times, use different account pools
- **Thread diversity** — don't post in the same thread twice

## Future Enhancements

- [ ] Bot-to-bot interactions (replies between accounts)
- [ ] Browser-based radar (scrape directly via Playwright)
- [ ] Email notifications for critical threads
- [ ] Basic auth on the dashboard
- [ ] Analytics integration (GA4 UTM tracking)
- [ ] Reddit Pro analytics integration
