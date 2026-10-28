"""
iSearchFrom Reddit Control — Mission Control Backend
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

DB_PATH.parent.mkdir(exist_ok=True)

# ── Config defaults ────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "auto_mode": False,
    "auto_threshold": 65,
    "max_posts_per_account_per_day": 8,
    "max_comments_per_account_per_day": 25,
    "min_karma_per_account": 50,
    "radar_subs": ["r/SEO,r/bigseo,r/PPC,r/GoogleAds,r/localseo,r/agency,r/SaaS,r/Entrepreneur,r/marketing,r/digital_marketing"],
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
}


# ── Database ───────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
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
            created_at REAL
        );

        CREATE INDEX IF NOT EXISTS idx_threads_status ON threads(status, score_radar);
        CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status);
        CREATE INDEX IF NOT EXISTS idx_tracker_account ON tracker(account_id);
    """)
    conn.commit()
    conn.close()


# ── Config helpers ─────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ── Account helpers ────────────────────────────────────────────────────
def load_accounts() -> list[dict]:
    if ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE) as f:
            return json.load(f)
    return []


def save_accounts(accounts: list[dict]):
    ACCOUNTS_FILE.parent.mkdir(exist_ok=True)
    with open(ACCOUNTS_FILE, "w") as f:
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


class DraftCreate(BaseModel):
    thread_id: str
    body: str
    account_id: Optional[str] = None


class AccountCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


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


# ── SSE broadcast ──────────────────────────────────────────────────────
event_queue: asyncio.Queue = asyncio.Queue()


async def broadcast_event(event_type: str, data: dict):
    await event_queue.put({"event": event_type, "data": json.dumps(data)})


# ── App lifecycle ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Seed default accounts if none exist
    if not ACCOUNTS_FILE.exists():
        save_accounts([])
    yield


app = FastAPI(title="iSearchFrom Reddit Control", lifespan=lifespan)
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


# ── Threads ────────────────────────────────────────────────────────────
@app.get("/api/threads")
async def get_threads(
    status: Optional[str] = Query(None, description="Filter by status: new, digested, alerted, posted, skipped"),
    subreddit: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None, description="Minimum radar score"),
    limit: int = Query(50, le=200),
    sort: str = Query("score_radar", description="Sort: score_radar, created_at, comments"),
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = "SELECT * FROM threads WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if subreddit:
        query += " AND subreddit = ?"
        params.append(subreddit)
    if min_score is not None:
        query += " AND score_radar >= ?"
        params.append(min_score)

    # Sort
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

    # Convert timestamps
    for r in rows:
        if r.get("created_at"):
            r["created_at_iso"] = datetime.fromtimestamp(r["created_at"], tz=timezone.utc).isoformat()
        if r.get("updated_at"):
            r["updated_at_iso"] = datetime.fromtimestamp(r["updated_at"], tz=timezone.utc).isoformat()

    conn.close()
    return rows


@app.post("/api/threads")
async def create_thread(t: ThreadCreate):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = time.time()
    c.execute("""
        INSERT OR REPLACE INTO threads (id, url, title, subreddit, author, score, num_comments,
            created_at, body_preview, topic, score_radar, product_mention, question_intent, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
    """, (str(uuid.uuid4()), t.url, t.title, t.subreddit, t.author, t.score, t.num_comments,
          t.created_at, t.body_preview, t.topic, t.score_radar, t.product_mention, t.question_intent))
    conn.commit()
    conn.close()
    await broadcast_event("thread_new", dict(t))
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
    status: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = "SELECT * FROM drafts WHERE 1=1"
    params = []

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
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO drafts (id, thread_id, thread_title, thread_url, subreddit, account_id,
            body, status, created_at, updated_at)
        VALUES (?, (SELECT title FROM threads WHERE id=?), (SELECT url FROM threads WHERE id=?),
            (SELECT url FROM threads WHERE id=?), (SELECT subreddit FROM threads WHERE id=?),
            ?, ?, 'pending', ?, ?)
    """, (str(uuid.uuid4()), d.thread_id, d.thread_id, d.thread_id, d.thread_id,
          d.account_id, d.body, now, now))
    conn.commit()
    conn.close()
    await broadcast_event("draft_new", {"id": str(uuid.uuid4()), **d.model_dump()})
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
    """Mark draft as posted."""
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
async def get_accounts():
    accounts = load_accounts()
    # Also read from DB for counts
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT username, post_count_today, comment_count_today, total_posts, total_comments, product_mentions, total_mentions, ban_risk FROM accounts")
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
    accounts = load_accounts()
    # Check duplicate
    for a in accounts:
        if a.get("username") == acc.username:
            a.update(acc.model_dump())
            break
    else:
        accounts.append({**acc.model_dump(), "is_active": True, "karma": 0, "ban_risk": 0,
                         "post_count_today": 0, "comment_count_today": 0,
                         "total_posts": 0, "total_comments": 0,
                         "product_mentions": 0, "total_mentions": 0})
    save_accounts(accounts)

    # Also store in DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO accounts (id, username, password, email, is_active, created_at)
        VALUES (?, ?, ?, ?, 1, ?)
    """, (str(uuid.uuid4()), acc.username, acc.password, acc.email, time.time()))
    conn.commit()
    conn.close()

    await broadcast_event("account_added", {"username": acc.username})
    return {"ok": True}


@app.put("/api/accounts/{username}")
async def update_account(username: str, data: dict):
    accounts = load_accounts()
    for i, a in enumerate(accounts):
        if a.get("username") == username:
            accounts[i].update(data)
            break
    else:
        raise HTTPException(404, f"Account {username} not found")
    save_accounts(accounts)
    return {"ok": True}


@app.delete("/api/accounts/{username}")
async def delete_account(username: str):
    accounts = load_accounts()
    accounts = [a for a in accounts if a.get("username") != username]
    save_accounts(accounts)
    return {"ok": True}


# ── Config ─────────────────────────────────────────────────────────────
@app.get("/api/config")
async def get_config():
    return load_config()


@app.put("/api/config")
async def update_config(cfg: ConfigUpdate):
    current = load_config()
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
    save_config(current)
    await broadcast_event("config_changed", current)
    return current


# ── Tracker ────────────────────────────────────────────────────────────
@app.get("/api/tracker")
async def get_tracker(
    account_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = "SELECT * FROM tracker WHERE 1=1"
    params = []
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
async def add_tracker_entry(entry: dict):
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO tracker (id, thread_id, thread_url, thread_title, comment_url, account_id,
            posted_at, upvotes, replies, clicks, signups, outcome, note, utm_link)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), entry.get("thread_id"), entry.get("thread_url"),
          entry.get("thread_title"), entry.get("comment_url"), entry.get("account_id"),
          now, entry.get("upvotes", 0), entry.get("replies", 0),
          entry.get("clicks", 0), entry.get("signups", 0),
          entry.get("outcome", "posted"), entry.get("note"), entry.get("utm_link")))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── KPIs / Stats ──────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    stats = {}

    # Thread counts by status
    c.execute("SELECT status, COUNT(*) as cnt FROM threads GROUP BY status")
    stats["threads_by_status"] = {r["status"]: r["cnt"] for r in c.fetchall()}

    # Draft counts by status
    c.execute("SELECT status, COUNT(*) as cnt FROM drafts GROUP BY status")
    stats["drafts_by_status"] = {r["status"]: r["cnt"] for r in c.fetchall()}

    # Total accounts
    c.execute("SELECT COUNT(*) as cnt FROM accounts WHERE is_active = 1")
    stats["active_accounts"] = c.fetchone()["cnt"]

    # Tracker totals
    c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(upvotes),0) as uv, COALESCE(SUM(replies),0) as rp, COALESCE(SUM(clicks),0) as cl FROM tracker")
    row = c.fetchone()
    stats["tracker"] = {"total": row["cnt"], "total_upvotes": row["uv"], "total_replies": row["rp"], "total_clicks": row["cl"]}

    # Top accounts by activity
    c.execute("SELECT account_id, COUNT(*) as cnt, COALESCE(SUM(upvotes),0) as uv FROM tracker GROUP BY account_id ORDER BY cnt DESC LIMIT 10")
    stats["top_accounts"] = [dict(r) for r in c.fetchall()]

    conn.close()
    return stats


# ── Radar import (bulk) ────────────────────────────────────────────────
@app.post("/api/radar/import")
async def import_radar_data(threads: list[dict]):
    """Import threads from radar scan (called by cron job)."""
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    added = 0
    for t in threads:
        c.execute("""
            INSERT OR REPLACE INTO threads (id, url, title, subreddit, author, score, num_comments,
                created_at, body_preview, topic, score_radar, product_mention, question_intent, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """, (str(uuid.uuid4()), t.get("url", ""), t.get("title", ""), t.get("subreddit", ""),
              t.get("author"), t.get("score", 0), t.get("num_comments", 0),
              t.get("created_at", now), t.get("body_preview", ""), t.get("topic", ""),
              t.get("score_radar", 0), t.get("product_mention", 0), t.get("question_intent", 0)))
        added += 1
    conn.commit()
    conn.close()
    await broadcast_event("radar_imported", {"count": added})
    return {"ok": True, "imported": added}


# ── Health ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": load_config().get("auto_mode", False)}
