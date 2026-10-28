#!/usr/bin/env python3
"""
Reddit browser poster — uses Playwright to post comments via stealth browser sessions.
Supports multiple accounts with cookie management.
"""

import asyncio
import json
import os
import time
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PwTimeout

DATA_DIR = Path(__file__).parent.parent / "data"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
COOKIES_DIR = DATA_DIR / "cookies"


async def load_accounts() -> list[dict]:
    if ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE) as f:
            return json.load(f)
    return []


async def save_cookies(username: str, cookies: list):
    COOKIES_DIR.mkdir(exist_ok=True)
    path = COOKIES_DIR / f"{username}.json"
    with open(path, "w") as f:
        json.dump(cookies, f)


async def load_cookies(username: str) -> list:
    path = COOKIES_DIR / f"{username}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


async def login_account(page, username: str, password: str, email: str = None):
    """Log in a Reddit account via the browser form."""
    await page.goto("https://www.reddit.com/login", wait_until="domcontentloaded")

    # Fill username
    try:
        await page.fill('input[name="username"]', username, timeout=10000)
        await page.fill('input[name="password"]', password, timeout=10000)

        # Handle email verification if needed
        if email:
            email_input = await page.query_selector('input[name="email"]')
            if email_input:
                await page.fill('input[name="email"]', email, timeout=10000)

        await page.click('button[type="submit"]', timeout=10000)
        await page.wait_for_load_state("domcontentloaded", timeout=30000)

        # Save cookies
        cookies = await page.context.cookies()
        await save_cookies(username, cookies)
        return True
    except PwTimeout:
        return False


async def post_comment(url: str, body: str, username: str, password: str, email: str = None) -> dict:
    """Post a comment on a Reddit thread using browser automation."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Load existing cookies
        existing_cookies = await load_cookies(username)
        if existing_cookies:
            await context.add_cookies(existing_cookies)

        page = await context.new_page()

        try:
            # Navigate to the comment form
            comment_url = f"{url}#comment_" + str(int(time.time() * 1000))
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Click the comment button
            try:
                await page.click('a[href*="comment"]', timeout=5000)
            except PwTimeout:
                pass

            # Check if logged in, if not login
            login_link = await page.query_selector('a[href*="login"]')
            if login_link:
                logged_in = await login_account(page, username, password, email)
                if not logged_in:
                    return {"ok": False, "error": "Login failed"}

            # Wait for comment textarea
            try:
                await page.wait_for_selector('textarea[name="body"], [data-testid="comment-textbox"]', timeout=15000)
            except PwTimeout:
                # Try alternative selectors
                textareas = await page.query_selector_all('textarea')
                if textareas:
                    await textareas[0].click()
                else:
                    return {"ok": False, "error": "No comment textarea found"}

            # Fill comment body
            await page.keyboard.press("Control+A")
            await page.keyboard.type(body, delay=20)

            # Submit
            submit_btn = await page.query_selector('button[type="submit"], [data-testid="comment-submit"]')
            if submit_btn:
                await submit_btn.click()
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            else:
                # Try keyboard submit
                await page.keyboard.press("Enter")
                await asyncio.sleep(2)

            # Get the comment URL
            new_url = page.url
            return {"ok": True, "url": new_url, "comment": body}

        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            await browser.close()


async def auto_post(draft_id: str, thread_url: str, body: str, account_username: str, account_password: str, account_email: str = None) -> dict:
    """Auto-post a draft using the specified account."""
    result = await post_comment(thread_url, body, account_username, account_password, account_email)
    result["draft_id"] = draft_id
    return result


async def main():
    """CLI interface for posting."""
    if len(sys.argv) < 5:
        print("Usage: poster.py <url> <body> <username> <password> [email]")
        sys.exit(1)

    url = sys.argv[1]
    body = sys.argv[2]
    username = sys.argv[3]
    password = sys.argv[4]
    email = sys.argv[5] if len(sys.argv) > 5 else None

    result = await post_comment(url, body, username, password, email)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import sys
    asyncio.run(main())
