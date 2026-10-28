# Reddit Control — Universal Mission Control

Multi-client mission control dashboard for Reddit visibility campaigns. Manage multiple clients, each with their own radar, bot accounts, drafts, and performance tracking.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    nginx (port 80/443)                   │
│  ┌──────────────┐  ┌──────────────────────────────────┐ │
│  │  Frontend    │  │         Backend (FastAPI)        │ │
│  │  SvelteKit   │  │  Port 8000                       │ │
│  │  SPA + CSS   │  │  - Multi-client API              │ │
│  │  :3000       │  │  - MCP tools                     │ │
│  └──────┬───────┘  │  - SSE live updates              │ │
│         │          └────────────┬─────────────────────┘ │
│         │                       │                        │
│  ┌──────┴───────────────────────┴──────────────────┐    │
│  │           SQLite Database (volume)              │    │
│  │  clients / threads / drafts / accounts / tracker│    │
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
git clone https://github.com/ergabit/isf-reddit-control.git
cd isf-reddit-control
```

### 2. Add Reddit bot accounts

Accounts are stored per-client in `data/accounts_{client_id}.json` (created on first run). The default client uses `data/accounts.json`.

### 3. Start with Docker Compose

```bash
docker compose up -d --build
```

### 4. Access the dashboard

- **Dashboard**: http://localhost:3900 (or your server IP:3900)
- **Backend API**: http://localhost:8900
- **Health check**: http://localhost:8900/api/health

### 5. Run the radar

```bash
# Manual sweep
docker exec reddit-control-backend python radar_scanner.py all

# Or let the radar-scanner container run automatically
docker compose up -d radar-scanner
```

## Multi-Client Support

The system supports multiple clients, each with their own:
- **Radar searches** — different keywords/subredditors per client
- **Bot accounts** — separate account pools per client
- **Settings** — auto-mode, thresholds, daily limits
- **Data** — threads, drafts, tracker entries are isolated per client

### Managing Clients via API

```bash
# List all clients
curl http://localhost:8900/api/clients

# Create a new client
curl -X POST http://localhost:8900/api/clients \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "slug": "acme", "brand_name": "Acme", "radar_subs": "r/marketing,r/SaaS", "radar_searches": ["acme OR acmecorp"]}'

# Switch context (set in frontend via client selector)
# All API calls accept ?client_id=acme parameter
```

### MCP Tools

The backend exposes an MCP-compatible endpoint at `POST /api/mcp/call` for agent management. The Hermes agent can call any tool via a single JSON payload:

```bash
# List all clients (MCP)
curl -X POST http://localhost:8900/api/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_clients"}'

# List threads for a client (MCP)
curl -X POST http://localhost:8900/api/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_threads", "args": {"client_id": "acme", "status": "new", "limit": 10}}'

# Approve a draft (MCP)
curl -X POST http://localhost:8900/api/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "approve_draft", "args": {"draft_id": "abc-123"}}'

# Add an account (MCP)
curl -X POST http://localhost:8900/api/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "add_account", "args": {"username": "bot1", "password": "pass123", "client_id": "acme"}}'
```

**Available MCP tools:**
| Tool | Description |
|------|-------------|
| `list_clients` | List all clients |
| `create_client` | Create a new client |
| `update_client` | Update client details |
| `delete_client` | Delete a client |
| `list_threads` | List threads (filterable) |
| `get_thread` | Get a single thread |
| `update_thread_status` | Update thread status |
| `delete_thread` | Delete a thread |
| `list_drafts` | List drafts (filterable) |
| `create_draft` | Create a draft |
| `approve_draft` | Approve a draft |
| `post_draft` | Post a draft |
| `skip_draft` | Skip a draft |
| `rewrite_draft` | Request draft rewrite |
| `update_draft_body` | Edit draft body |
| `list_accounts` | List accounts |
| `add_account` | Add an account |
| `delete_account` | Delete an account |
| `get_config` | Get client config |
| `update_config` | Update client config |
| `get_tracker` | List tracker entries |
| `add_tracker_entry` | Add tracker entry |
| `get_stats` | Get KPI stats |
| `radar_import` | Bulk import threads |
| `health` | Health check |

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
- Add/remove bot accounts per client
- View karma, daily limits, ban risk
- Toggle active/inactive

### 📊 Tracker
- All posted replies with engagement metrics
- Upvotes, replies, UTM clicks

### ⚙️ Settings
- **Supervised vs Auto mode** toggle
- Auto-post threshold slider (40-90)
- Daily limits per account
- Client management

## API Endpoints

|| Method | Path | Description |
||--------|------|-------------|
|| GET | `/api/clients` | List all clients |
|| POST | `/api/clients` | Create client |
|| PUT | `/api/clients/:id` | Update client |
|| DELETE | `/api/clients/:id` | Delete client |
|| GET | `/api/threads` | List threads (filterable, `?client_id=`) |
|| POST | `/api/threads` | Add a thread |
|| GET | `/api/drafts` | List drafts (filterable, `?client_id=`) |
|| POST | `/api/drafts` | Create draft |
|| POST | `/api/drafts/:id/approve` | Approve draft |
|| POST | `/api/drafts/:id/post` | Mark as posted |
|| POST | `/api/drafts/:id/skip` | Skip draft |
|| POST | `/api/drafts/:id/rewrite` | Request rewrite |
|| PUT | `/api/drafts/:id/body` | Edit draft body |
|| GET | `/api/accounts` | List accounts (`?client_id=`) |
|| POST | `/api/accounts` | Add account |
|| DELETE | `/api/accounts/:username` | Delete account |
|| GET | `/api/config` | Get config (`?client_id=`) |
|| PUT | `/api/config` | Update config (`?client_id=`) |
|| GET | `/api/tracker` | List tracker entries (`?client_id=`) |
|| GET | `/api/stats` | KPI stats (`?client_id=`) |
|| POST | `/api/radar/import` | Bulk import threads |
|| POST | `/api/mcp/call` | MCP tool execution |
|| GET | `/api/health` | Health check |
|| GET | `/events` | SSE live events |

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
reddit-control/
├── backend/
│   ├── app.py              # FastAPI main app (multi-client + MCP)
│   ├── radar_scanner.py    # Radar CLI wrapper
│   ├── reddit_poster.py    # Playwright poster
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +layout.svelte      # Sidebar with client selector
│   │   │   ├── +page.svelte        # Dashboard
│   │   │   ├── findings/
│   │   │   ├── drafts/
│   │   │   ├── accounts/
│   │   │   ├── tracker/
│   │   │   └── settings/
│   │   └── lib/
│   │       ├── constants.ts
│   │       └── api.ts
│   ├── static/
│   │   └── app.css           # Tailwind dark theme
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
- **Multi-client** — isolate campaigns per client

## MCP Integration

The backend is designed for agent-first management. The Hermes agent can:
1. Call `POST /api/mcp/call` with any tool name and args
2. Manage clients, threads, drafts, accounts programmatically
3. Push radar data, approve drafts, post replies — all via API
4. Get real-time stats and tracker data

This makes the dashboard fully manageable without the UI — perfect for automation pipelines.
