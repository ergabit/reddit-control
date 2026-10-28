"""
Reddit Control — Universal Mission Control Backend
Multi-client support with MCP tool endpoints.
FastAPI app with SQLite, SSE live updates, Playwright browser posting.
"""

import asyncio
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "reddit_control.db"
DATA_DIR = BASE_DIR / "data"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
CONFIG_FILE = DATA_DIR / "config.json"
CLIENTS_FILE = DATA_DIR / "clients.json"

DB_PATH.parent.mkdir(exist_ok=True)

# ── Config defaults ────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "auto_mode": False,
    "auto_threshold": 65,
    "max_posts_per_account_per_day": 8,
    "max_comments_per_account_per_day": 25,
    "min_karma_per_account": 50,
}

DEFAULT_CLIENT = {
    "id": "default",
    "name": "Default Client",
    "slug": "default",
    "brand_name": "Reddit Control",
    "radar_subs": "r/SEO,r/bigseo,r/PPC,r/GoogleAds,r/localseo,r/agency,r/SaaS,r/Entrepreneur,r/marketing,r/digital_marketing",
    "radar_searches": [
        "isearchfrom OR \"isearch from\" OR searchfrom.com",
        "google results from another country",
        "see google results different city",
        "rank tracker local SEO",
        "competitor ads by location",
        "AI visibility tracking",
        "map pack rank tracker",
        "ChatGPT brand visibility",
    ],
    "posting_accounts": [],
    "auto_threshold": 65,
    "max_posts_per_day": 8,
    "max_comments_per_day": 25,
    "min_karma": 50,
}


# ── Database ───────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            brand_name TEXT DEFAULT 'Reddit Control',
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL DEFAULT 'default',
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            subreddit TEXT NOT NULL,
            author TEXT,
            score INTEGER DEFAULT 0,
            num_comments INTEGER DEFAULT 0,
            created_at REAL,
            updated_at REAL,
            topic TEXT,
            score_radar REAL DEFAULT 0,
            status TEXT DEFAULT 'new',
            body_preview TEXT,
            product_mention INTEGER DEFAULT 0,
            question_intent INTEGER DEFAULT 0,
            created_at_iso TEXT,
            updated_at_iso TEXT
        );

        CREATE TABLE IF NOT EXISTS drafts (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL DEFAULT 'default',
            thread_id TEXT NOT NULL,
            thread_title TEXT,
            thread_url TEXT,
            subreddit TEXT,
            account_id TEXT,
            body TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at REAL,
            updated_at REAL,
            feedback TEXT,
            post_url TEXT,
            upvotes INTEGER DEFAULT 0,
            created_at_iso TEXT,
            updated_at_iso TEXT
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL DEFAULT 'default',
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            email_code TEXT,
            karma INTEGER DEFAULT 0,
            post_count_today INTEGER DEFAULT 0,
            comment_count_today INTEGER DEFAULT 0,
            total_posts INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0,
            product_mentions INTEGER DEFAULT 0,
            total_mentions INTEGER DEFAULT 0,
            ban_risk REAL DEFAULT 0,
            last_active REAL,
            is_active INTEGER DEFAULT 1,
            cookies_file TEXT,
            created_at REAL,
            created_at_iso TEXT
        );

        CREATE TABLE IF NOT EXISTS tracker (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL DEFAULT 'default',
            thread_id TEXT,
            thread_url TEXT,
            thread_title TEXT,
            comment_url TEXT,
            account_id TEXT,
            posted_at REAL,
            upvotes INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            signups INTEGER DEFAULT 0,
            outcome TEXT DEFAULT 'posted',
            note TEXT,
            utm_link TEXT,
            posted_at_iso TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            data TEXT,
            client_id TEXT,
            created_at REAL
        );

        CREATE INDEX IF NOT EXISTS idx_threads_client ON threads(client_id, status, score_radar);
        CREATE INDEX IF NOT EXISTS idx_threads_status ON threads(status, score_radar);
        CREATE INDEX IF NOT EXISTS idx_drafts_client ON drafts(client_id, status);
        CREATE INDEX IF NOT EXISTS idx_accounts_client ON accounts(client_id);
        CREATE INDEX IF NOT EXISTS idx_tracker_client ON tracker(client_id);
        CREATE INDEX IF NOT EXISTS idx_events_client ON events(client_id);
    """)
    conn.commit()
    conn.close()


# ── Client helpers ─────────────────────────────────────────────────────
def load_clients() -> list[dict]:
    if CLIENTS_FILE.exists():
        with open(CLIENTS_FILE) as f:
            return json.load(f)
    save_clients([DEFAULT_CLIENT.copy()])
    return [DEFAULT_CLIENT.copy()]


def save_clients(clients: list[dict]):
    CLIENTS_FILE.parent.mkdir(exist_ok=True)
    with open(CLIENTS_FILE, "w") as f:
        json.dump(clients, f, indent=2)


def get_default_client() -> dict:
    clients = load_clients()
    for c in clients:
        if c.get("slug") == "default":
            return c
    return DEFAULT_CLIENT.copy()


def get_client_by_slug(slug: str) -> Optional[dict]:
    clients = load_clients()
    for c in clients:
        if c.get("slug") == slug:
            return c
    return None


def get_client_id_or_default(client_id: Optional[str] = None) -> str:
    if not client_id:
        return "default"
    clients = load_clients()
    for c in clients:
        if c.get("id") == client_id or c.get("slug") == client_id:
            return c["id"]
    return "default"


# ── Config helpers ─────────────────────────────────────────────────────
def load_config(client_id: Optional[str] = None) -> dict:
    cid = get_client_id_or_default(client_id)
    cfg_file = DATA_DIR / f"config_{cid}.json"
    if cfg_file.exists():
        with open(cfg_file) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    save_config({}, client_id)
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict, client_id: Optional[str] = None):
    cid = get_client_id_or_default(client_id)
    cfg_file = DATA_DIR / f"config_{cid}.json"
    cfg_file.parent.mkdir(exist_ok=True)
    with open(cfg_file, "w") as f:
        json.dump(cfg, f, indent=2)


# ── Account helpers ────────────────────────────────────────────────────
def load_accounts(client_id: Optional[str] = None) -> list[dict]:
    cid = get_client_id_or_default(client_id)
    acc_file = DATA_DIR / f"accounts_{cid}.json"
    if acc_file.exists():
        with open(acc_file) as f:
            return json.load(f)
    return []


def save_accounts(accounts: list[dict], client_id: Optional[str] = None):
    cid = get_client_id_or_default(client_id)
    acc_file = DATA_DIR / f"accounts_{cid}.json"
    acc_file.parent.mkdir(exist_ok=True)
    with open(acc_file, "w") as f:
        json.dump(accounts, f, indent=2)


# ── Models ─────────────────────────────────────────────────────────────
class ThreadCreate(BaseModel):
    url: str
    title: str
    subreddit: str
    author: Optional[str] = None
    score: int = 0
    num_comments: int = 0
    created_at: float = 0
    body_preview: str = ""
    topic: str = ""
    score_radar: float = 0
    product_mention: int = 0
    question_intent: int = 0
    client_id: Optional[str] = None


class DraftCreate(BaseModel):
    thread_id: str
    body: str
    account_id: Optional[str] = None
    client_id: Optional[str] = None


class AccountCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    client_id: Optional[str] = None


class ConfigUpdate(BaseModel):
    auto_mode: Optional[bool] = None
    auto_threshold: Optional[int] = None
    max_posts_per_day: Optional[int] = None
    max_comments_per_day: Optional[int] = None
    min_karma: Optional[int] = None


class FeedbackUpdate(BaseModel):
    feedback: str


class PostAction(BaseModel):
    account_id: str


class ClientCreate(BaseModel):
    name: str
    slug: str
    brand_name: Optional[str] = "Reddit Control"
    radar_subs: Optional[str] = "r/SEO,r/bigseo,r/PPC,r/GoogleAds"
    radar_searches: Optional[list[str]] = None


class RadarImport(BaseModel):
    threads: list[dict]
    client_id: Optional[str] = None


# ── SSE broadcast ──────────────────────────────────────────────────────
event_queue: asyncio.Queue = asyncio.Queue()


async def broadcast_event(event_type: str, data: dict, client_id: Optional[str] = None):
    await event_queue.put({"event": event_type, "data": json.dumps(data), "client_id": client_id})


# ── App lifecycle ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Seed default client if none exist
    if not CLIENTS_FILE.exists():
        save_clients([DEFAULT_CLIENT.copy()])
    # Seed default accounts file
    if not ACCOUNTS_FILE.exists():
        save_accounts([])
    yield


app = FastAPI(title="Reddit Control", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── SSE endpoint ───────────────────────────────────────────────────────
@app.get("/events")
async def events():
    """Server-Sent Events for live dashboard updates."""
    async def event_generator():
        while True:
            try:
                msg = await asyncio.wait_for(event_queue.get(), timeout=30)
                yield {"event": msg["event"], "data": msg["data"]}
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}

    return EventSourceResponse(event_generator())


# ── Clients ────────────────────────────────────────────────────────────
@app.get("/api/clients")
async def get_clients():
    """List all clients."""
    return load_clients()


@app.post("/api/clients")
async def create_client(c: ClientCreate):
    """Create a new client."""
    clients = load_clients()
    for existing in clients:
        if existing.get("slug") == c.slug:
            raise HTTPException(400, f"Client slug '{c.slug}' already exists")
    new_client = {
        "id": str(uuid.uuid4()),
        "name": c.name,
        "slug": c.slug,
        "brand_name": c.brand_name or "Reddit Control",
        "radar_subs": c.radar_subs or "r/SEO,r/bigseo",
        "radar_searches": c.radar_searches or [],
        "posting_accounts": [],
        "auto_threshold": 65,
        "max_posts_per_day": 8,
        "max_comments_per_day": 25,
        "min_karma": 50,
    }
    clients.append(new_client)
    save_clients(clients)
    await broadcast_event("client_created", {"id": new_client["id"], "name": c.name})
    return new_client


@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, data: dict):
    """Update a client."""
    clients = load_clients()
    for i, c in enumerate(clients):
        if c.get("id") == client_id or c.get("slug") == client_id:
            clients[i].update(data)
            break
    else:
        raise HTTPException(404, f"Client {client_id} not found")
    save_clients(clients)
    await broadcast_event("client_updated", {"id": client_id})
    return {"ok": True}


@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str):
    """Delete a client (not 'default')."""
    clients = load_clients()
    for i, c in enumerate(clients):
        if (c.get("id") == client_id or c.get("slug") == client_id) and c.get("id") != "default":
            clients.pop(i)
            break
    else:
        raise HTTPException(404, f"Client {client_id} not found or is default")
    save_clients(clients)
    await broadcast_event("client_deleted", {"id": client_id})
    return {"ok": True}


# ── Threads ────────────────────────────────────────────────────────────
@app.get("/api/threads")
async def get_threads(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Filter by status: new, digested, alerted, posted, skipped"),
    subreddit: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None, description="Minimum radar score"),
    limit: int = Query(50, le=200),
    sort: str = Query("score_radar", description="Sort: score_radar, created_at, comments"),
):
    cid = get_client_id_or_default(client_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = "SELECT * FROM threads WHERE client_id = ?"
    params: list = [cid]

    if status:
        query += " AND status = ?"
        params.append(status)
    if subreddit:
        query += " AND subreddit = ?"
        params.append(subreddit)
    if min_score is not None:
        query += " AND score_radar >= ?"
        params.append(min_score)

    if sort == "created_at":
        query += " ORDER BY created_at DESC"
    elif sort == "comments":
        query += " ORDER BY num_comments DESC"
    else:
        query += " ORDER BY score_radar DESC"

    query += " LIMIT ?"
    params.append(limit)

    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]

    for r in rows:
        if r.get("created_at"):
            r["created_at_iso"] = datetime.fromtimestamp(r["created_at"], tz=timezone.utc).isoformat()
        if r.get("updated_at"):
            r["updated_at_iso"] = datetime.fromtimestamp(r["updated_at"], tz=timezone.utc).isoformat()

    conn.close()
    return rows


@app.post("/api/threads")
async def create_thread(t: ThreadCreate):
    cid = get_client_id_or_default(t.client_id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO threads (id, client_id, url, title, subreddit, author, score, num_comments,
            created_at, body_preview, topic, score_radar, product_mention, question_intent, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
    """, (str(uuid.uuid4()), cid, t.url, t.title, t.subreddit, t.author, t.score, t.num_comments,
          t.created_at, t.body_preview, t.topic, t.score_radar, t.product_mention, t.question_intent))
    conn.commit()
    conn.close()
    await broadcast_event("thread_new", dict(t), cid)
    return {"ok": True}


@app.post("/api/threads/{thread_id}/status")
async def update_thread_status(thread_id: str, status: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE threads SET status = ? WHERE id = ?", (status, thread_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/api/threads/{thread_id}")
async def delete_thread(thread_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Drafts ─────────────────────────────────────────────────────────────
@app.get("/api/drafts")
async def get_drafts(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    cid = get_client_id_or_default(client_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = "SELECT * FROM drafts WHERE client_id = ?"
    params: list = [cid]

    if status:
        query += " AND status = ?"
        params.append(status)
    if account_id:
        query += " AND account_id = ?"
        params.append(account_id)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]

    for r in rows:
        if r.get("created_at"):
            r["created_at_iso"] = datetime.fromtimestamp(r["created_at"], tz=timezone.utc).isoformat()
        if r.get("updated_at"):
            r["updated_at_iso"] = datetime.fromtimestamp(r["updated_at"], tz=timezone.utc).isoformat()

    conn.close()
    return rows


@app.post("/api/drafts")
async def create_draft(d: DraftCreate):
    cid = get_client_id_or_default(d.client_id)
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO drafts (id, client_id, thread_id, thread_title, thread_url, subreddit, account_id,
            body, status, created_at, updated_at)
        VALUES (?, ?, (SELECT title FROM threads WHERE id=?), (SELECT url FROM threads WHERE id=?),
            (SELECT url FROM threads WHERE id=?), (SELECT subreddit FROM threads WHERE id=?),
            ?, ?, 'pending', ?, ?)
    """, (str(uuid.uuid4()), cid, d.thread_id, d.thread_id, d.thread_id, d.thread_id,
          d.account_id, d.body, now, now))
    conn.commit()
    conn.close()
    await broadcast_event("draft_new", {"id": str(uuid.uuid4()), **d.model_dump()}, cid)
    return {"ok": True}


@app.post("/api/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str):
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE drafts SET status = 'approved', updated_at = ? WHERE id = ?", (now, draft_id))
    conn.commit()
    conn.close()
    await broadcast_event("draft_approved", {"id": draft_id})
    return {"ok": True}


@app.post("/api/drafts/{draft_id}/post")
async def post_draft(draft_id: str, action: PostAction = None):
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE drafts SET status = 'posted', post_url = ?, updated_at = ?
        WHERE id = ?
    """, (action.account_id if action else None, now, draft_id))
    conn.commit()
    conn.close()
    await broadcast_event("draft_posted", {"id": draft_id})
    return {"ok": True}


@app.post("/api/drafts/{draft_id}/skip")
async def skip_draft(draft_id: str):
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE drafts SET status = 'skipped', updated_at = ? WHERE id = ?", (now, draft_id))
    conn.commit()
    conn.close()
    await broadcast_event("draft_skipped", {"id": draft_id})
    return {"ok": True}


@app.post("/api/drafts/{draft_id}/rewrite")
async def rewrite_draft(draft_id: str, fb: FeedbackUpdate):
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE drafts SET status = 'rewriting', feedback = ?, updated_at = ? WHERE id = ?
    """, (fb.feedback, now, draft_id))
    conn.commit()
    conn.close()
    await broadcast_event("draft_rewriting", {"id": draft_id, "feedback": fb.feedback})
    return {"ok": True}


@app.put("/api/drafts/{draft_id}/body")
async def update_draft_body(draft_id: str, body: str):
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE drafts SET body = ?, status = 'pending', updated_at = ? WHERE id = ?",
              (body, now, draft_id))
    conn.commit()
    conn.close()
    await broadcast_event("draft_updated", {"id": draft_id})
    return {"ok": True}


# ── Accounts ───────────────────────────────────────────────────────────
@app.get("/api/accounts")
async def get_accounts(client_id: Optional[str] = Query(None)):
    cid = get_client_id_or_default(client_id)
    accounts = load_accounts(cid)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT username, post_count_today, comment_count_today, total_posts, total_comments, product_mentions, total_mentions, ban_risk FROM accounts WHERE client_id = ?", (cid,))
    db_rows = {r["username"]: dict(r) for r in c.fetchall()}
    conn.close()

    result = []
    for acc in accounts:
        username = acc.get("username", "")
        db = db_rows.get(username, {})
        entry = {**acc, "post_count_today": db.get("post_count_today", 0),
                 "comment_count_today": db.get("comment_count_today", 0),
                 "total_posts": db.get("total_posts", 0),
                 "total_comments": db.get("total_comments", 0),
                 "product_mentions": db.get("product_mentions", 0),
                 "total_mentions": db.get("total_mentions", 0),
                 "ban_risk": db.get("ban_risk", 0)}
        result.append(entry)
    return result


@app.post("/api/accounts")
async def add_account(acc: AccountCreate):
    cid = get_client_id_or_default(acc.client_id)
    accounts = load_accounts(cid)
    for a in accounts:
        if a.get("username") == acc.username:
            a.update(acc.model_dump())
            break
    else:
        accounts.append({**acc.model_dump(), "is_active": True, "karma": 0, "ban_risk": 0,
                         "post_count_today": 0, "comment_count_today": 0,
                         "total_posts": 0, "total_comments": 0,
                         "product_mentions": 0, "total_mentions": 0})
    save_accounts(accounts, cid)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO accounts (id, client_id, username, password, email, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """, (str(uuid.uuid4()), cid, acc.username, acc.password, acc.email, time.time()))
    conn.commit()
    conn.close()

    await broadcast_event("account_added", {"username": acc.username}, cid)
    return {"ok": True}


@app.put("/api/accounts/{username}")
async def update_account(username: str, data: dict, client_id: Optional[str] = Query(None)):
    cid = get_client_id_or_default(client_id)
    accounts = load_accounts(cid)
    for i, a in enumerate(accounts):
        if a.get("username") == username:
            accounts[i].update(data)
            break
    else:
        raise HTTPException(404, f"Account {username} not found")
    save_accounts(accounts, cid)
    return {"ok": True}


@app.delete("/api/accounts/{username}")
async def delete_account(username: str, client_id: Optional[str] = Query(None)):
    cid = get_client_id_or_default(client_id)
    accounts = load_accounts(cid)
    accounts = [a for a in accounts if a.get("username") != username]
    save_accounts(accounts, cid)
    return {"ok": True}


# ── Config ─────────────────────────────────────────────────────────────
@app.get("/api/config")
async def get_config(client_id: Optional[str] = Query(None)):
    return load_config(client_id)


@app.put("/api/config")
async def update_config(cfg: ConfigUpdate, client_id: Optional[str] = Query(None)):
    current = load_config(client_id)
    if cfg.auto_mode is not None:
        current["auto_mode"] = cfg.auto_mode
    if cfg.auto_threshold is not None:
        current["auto_threshold"] = cfg.auto_threshold
    if cfg.max_posts_per_day is not None:
        current["max_posts_per_day"] = cfg.max_posts_per_day
    if cfg.max_comments_per_day is not None:
        current["max_comments_per_day"] = cfg.max_comments_per_day
    if cfg.min_karma is not None:
        current["min_karma"] = cfg.min_karma
    save_config(current, client_id)
    await broadcast_event("config_changed", current, client_id)
    return current


# ── Tracker ────────────────────────────────────────────────────────────
@app.get("/api/tracker")
async def get_tracker(
    client_id: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    cid = get_client_id_or_default(client_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = "SELECT * FROM tracker WHERE client_id = ?"
    params: list = [cid]
    if account_id:
        query += " AND account_id = ?"
        params.append(account_id)
    query += " ORDER BY posted_at DESC LIMIT ?"
    params.append(limit)

    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]

    for r in rows:
        if r.get("posted_at"):
            r["posted_at_iso"] = datetime.fromtimestamp(r["posted_at"], tz=timezone.utc).isoformat()

    conn.close()
    return rows


@app.post("/api/tracker")
async def add_tracker_entry(entry: dict, client_id: Optional[str] = Query(None)):
    cid = get_client_id_or_default(client_id)
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO tracker (id, client_id, thread_id, thread_url, thread_title, comment_url, account_id,
            posted_at, upvotes, replies, clicks, signups, outcome, note, utm_link)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), cid, entry.get("thread_id"), entry.get("thread_url"),
          entry.get("thread_title"), entry.get("comment_url"), entry.get("account_id"),
          now, entry.get("upvotes", 0), entry.get("replies", 0),
          entry.get("clicks", 0), entry.get("signups", 0),
          entry.get("outcome", "posted"), entry.get("note"), entry.get("utm_link")))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── KPIs / Stats ──────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats(client_id: Optional[str] = Query(None)):
    cid = get_client_id_or_default(client_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    stats = {}

    c.execute("SELECT status, COUNT(*) as cnt FROM threads WHERE client_id = ? GROUP BY status", (cid,))
    stats["threads_by_status"] = {r["status"]: r["cnt"] for r in c.fetchall()}

    c.execute("SELECT status, COUNT(*) as cnt FROM drafts WHERE client_id = ? GROUP BY status", (cid,))
    stats["drafts_by_status"] = {r["status"]: r["cnt"] for r in c.fetchall()}

    c.execute("SELECT COUNT(*) as cnt FROM accounts WHERE client_id = ? AND is_active = 1", (cid,))
    stats["active_accounts"] = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(upvotes),0) as uv, COALESCE(SUM(replies),0) as rp, COALESCE(SUM(clicks),0) as cl FROM tracker WHERE client_id = ?", (cid,))
    row = c.fetchone()
    stats["tracker"] = {"total": row["cnt"], "total_upvotes": row["uv"], "total_replies": row["rp"], "total_clicks": row["cl"]}

    c.execute("SELECT account_id, COUNT(*) as cnt, COALESCE(SUM(upvotes),0) as uv FROM tracker WHERE client_id = ? GROUP BY account_id ORDER BY cnt DESC LIMIT 10", (cid,))
    stats["top_accounts"] = [dict(r) for r in c.fetchall()]

    conn.close()
    return stats


# ── Radar import (bulk) ────────────────────────────────────────────────
@app.post("/api/radar/import")
async def import_radar_data(data: RadarImport):
    cid = get_client_id_or_default(data.client_id)
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    added = 0
    for t in data.threads:
        c.execute("""
            INSERT OR REPLACE INTO threads (id, client_id, url, title, subreddit, author, score, num_comments,
                created_at, body_preview, topic, score_radar, product_mention, question_intent, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """, (str(uuid.uuid4()), cid, t.get("url", ""), t.get("title", ""), t.get("subreddit", ""),
              t.get("author"), t.get("score", 0), t.get("num_comments", 0),
              t.get("created_at", now), t.get("body_preview", ""), t.get("topic", ""),
              t.get("score_radar", 0), t.get("product_mention", 0), t.get("question_intent", 0)))
        added += 1
    conn.commit()
    conn.close()
    await broadcast_event("radar_imported", {"count": added}, cid)
    return {"ok": True, "imported": added}


# ── MCP Tools ──────────────────────────────────────────────────────────
# These endpoints let the Hermes agent manage the system via MCP calls.

class McpToolCall(BaseModel):
    tool: str
    args: dict = {}


@app.post("/api/mcp/call")
async def mcp_tool_call(call: McpToolCall):
    """Execute an MCP tool call from the agent."""
    tool = call.tool
    args = call.args

    if tool == "list_clients":
        return {"result": load_clients()}

    elif tool == "create_client":
        c = ClientCreate(**args)
        return await create_client(c)

    elif tool == "update_client":
        return await update_client(args["client_id"], args.get("data", {}))

    elif tool == "delete_client":
        return await delete_client(args["client_id"])

    elif tool == "list_threads":
        return await get_threads(
            client_id=args.get("client_id"),
            status=args.get("status"),
            subreddit=args.get("subreddit"),
            min_score=args.get("min_score"),
            limit=args.get("limit", 50),
            sort=args.get("sort", "score_radar"),
        )

    elif tool == "get_thread":
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM threads WHERE id = ?", (args["thread_id"],))
        row = c.fetchone()
        conn.close()
        return {"result": dict(row) if row else None}

    elif tool == "update_thread_status":
        return await update_thread_status(args["thread_id"], args["status"])

    elif tool == "delete_thread":
        return await delete_thread(args["thread_id"])

    elif tool == "list_drafts":
        return await get_drafts(
            client_id=args.get("client_id"),
            status=args.get("status"),
            account_id=args.get("account_id"),
            limit=args.get("limit", 50),
        )

    elif tool == "create_draft":
        d = DraftCreate(**args)
        return await create_draft(d)

    elif tool == "approve_draft":
        return await approve_draft(args["draft_id"])

    elif tool == "post_draft":
        return await post_draft(args["draft_id"], PostAction(account_id=args.get("account_id")))

    elif tool == "skip_draft":
        return await skip_draft(args["draft_id"])

    elif tool == "rewrite_draft":
        return await rewrite_draft(args["draft_id"], FeedbackUpdate(feedback=args.get("feedback", "")))

    elif tool == "update_draft_body":
        return await update_draft_body(args["draft_id"], args["body"])

    elif tool == "list_accounts":
        return await get_accounts(client_id=args.get("client_id"))

    elif tool == "add_account":
        a = AccountCreate(**args)
        return await add_account(a)

    elif tool == "delete_account":
        return await delete_account(args["username"], client_id=args.get("client_id"))

    elif tool == "get_config":
        return await get_config(client_id=args.get("client_id"))

    elif tool == "update_config":
        return await update_config(ConfigUpdate(**args), client_id=args.get("client_id"))

    elif tool == "get_tracker":
        return await get_tracker(
            client_id=args.get("client_id"),
            account_id=args.get("account_id"),
            limit=args.get("limit", 100),
        )

    elif tool == "add_tracker_entry":
        return await add_tracker_entry(args, client_id=args.get("client_id"))

    elif tool == "get_stats":
        return await get_stats(client_id=args.get("client_id"))

    elif tool == "radar_import":
        return await import_radar_data(RadarImport(threads=args.get("threads", []), client_id=args.get("client_id")))

    elif tool == "health":
        return await health()

    else:
        raise HTTPException(400, f"Unknown MCP tool: {tool}")


# ── Health ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": load_config().get("auto_mode", False), "version": "2.0.0"}
