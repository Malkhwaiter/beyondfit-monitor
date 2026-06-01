#!/usr/bin/env python3
"""
beyondfit-sa.com (Salla store) size-availability monitor.

For each product listed in `products.json`, fetches the product page and
reads the `<salla-product-options>` blob embedded in the HTML. That blob
contains the size option group (القياس) where every size carries an
`is_out` flag (true = sold out, false = in stock).

The monitor tracks the availability of the *watched* sizes (default: M)
and sends a Telegram notification the moment a watched size flips from
sold-out (or unseen) to in-stock. It does NOT notify on every run while a
size stays available — only on the sold-out → available transition.

State lives in `state/known_stock.json` and is committed back to the repo
so the next run knows what was already in stock. On the very first run a
baseline is saved and no notifications are sent.
"""

from __future__ import annotations

import html as html_mod
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

CONFIG_FILE = Path("products.json")
STATE_FILE = Path("state/known_stock.json")
SUMMARY_STATE_FILE = Path("state/summary_state.json")
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# Heartbeat summary cadence. GitHub's free cron is unreliable (runs are often
# delayed or skipped entirely), so instead of firing at exact slots we send the
# summary on the first successful run once this many hours have passed since the
# last summary, and remember when we sent it — robust against skipped slots.
KSA_OFFSET_HOURS = 3              # Saudi Arabia is UTC+3, no DST
SUMMARY_EVERY_HOURS = 3          # send a heartbeat roughly every 3 hours

# Salla calls the size option group "القياس"; allow a few aliases just in case.
SIZE_GROUP_NAMES = {"القياس", "المقاس", "مقاس", "size", "Size", "الحجم"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
}

OPTIONS_RE = re.compile(r'<salla-product-options\s+options="(.*?)"', re.S)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
PRODUCT_ID_RE = re.compile(r"/p(\d+)/?$")


def http_get(url: str, *, retries: int = 3, timeout: int = 30) -> requests.Response:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")


def product_key(url: str) -> str:
    """Stable key for a product, e.g. 'p51278165'."""
    m = PRODUCT_ID_RE.search(url.rstrip("/"))
    return f"p{m.group(1)}" if m else url


def parse_title(doc: str) -> str:
    m = TITLE_RE.search(doc)
    if not m:
        return ""
    title = html_mod.unescape(m.group(1)).strip()
    # Strip the " - Beyoned Fit" store suffix.
    title = re.sub(r"\s*[-|]\s*Beyoned?\s*Fit\s*$", "", title, flags=re.I)
    return title.strip()


def parse_sizes(doc: str) -> dict[str, bool] | None:
    """Return {size_name: available_bool} for the size option group.

    Returns None if no <salla-product-options> blob is present (page shape
    changed or product has no variants) so the caller can skip safely.
    """
    m = OPTIONS_RE.search(doc)
    if not m:
        return None
    try:
        groups = json.loads(html_mod.unescape(m.group(1)))
    except json.JSONDecodeError:
        return None

    # Pick the size group by name; fall back to the first single-option group
    # whose values look like clothing sizes.
    size_group = None
    for g in groups:
        if (g.get("name") or "").strip() in SIZE_GROUP_NAMES:
            size_group = g
            break
    if size_group is None:
        for g in groups:
            names = {(v.get("name") or "").strip().upper() for v in g.get("details", [])}
            if names & {"S", "M", "L", "XL", "XXL", "2XL", "3XL"}:
                size_group = g
                break
    if size_group is None:
        return None

    out: dict[str, bool] = {}
    for v in size_group.get("details", []):
        name = (v.get("name") or "").strip()
        if not name:
            continue
        # is_out == True  -> sold out; available is the negation.
        out[name] = not bool(v.get("is_out", True))
    return out


def collect_product(url: str) -> dict | None:
    """Fetch one product and return {key,title,url,sizes}. None on hard failure."""
    doc = http_get(url).text
    sizes = parse_sizes(doc)
    if sizes is None:
        print(f"  WARN: no size options found for {url}", file=sys.stderr)
        return None
    return {
        "key": product_key(url),
        "title": parse_title(doc) or url,
        "url": url,
        "sizes": sizes,
    }


# ---------------- State + Telegram ---------------- #

def load_state() -> dict[str, dict]:
    if not STATE_FILE.exists():
        return {}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, dict]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
    tmp.replace(STATE_FILE)


def send_telegram(token: str, chat_id: str, text: str, *, retries: int = 3) -> None:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.post(
                TELEGRAM_API.format(token=token),
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=30,
            )
            if resp.status_code == 429:
                wait = 5
                try:
                    wait = int(resp.json().get("parameters", {}).get("retry_after", 5))
                except Exception:  # noqa: BLE001
                    pass
                print(f"  rate limited, sleeping {wait}s", file=sys.stderr)
                time.sleep(min(wait, 30))
                continue
            if not resp.ok:
                if 400 <= resp.status_code < 500:
                    raise RuntimeError(f"Telegram {resp.status_code}: {resp.text[:200]}")
                last_err = RuntimeError(f"Telegram {resp.status_code}: {resp.text[:200]}")
                time.sleep(2 ** attempt)
                continue
            return
        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Telegram send failed after {retries} attempts: {last_err}")


def ksa_now() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=KSA_OFFSET_HOURS)


def load_last_summary() -> datetime | None:
    if not SUMMARY_STATE_FILE.exists():
        return None
    try:
        with SUMMARY_STATE_FILE.open("r", encoding="utf-8") as f:
            raw = json.load(f).get("last_sent_utc", "")
        return datetime.fromisoformat(raw) if raw else None
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def save_last_summary(dt_utc: datetime) -> None:
    SUMMARY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SUMMARY_STATE_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump({"last_sent_utc": dt_utc.isoformat()}, f)
    tmp.replace(SUMMARY_STATE_FILE)


def summary_due(now_utc: datetime, last: datetime | None) -> bool:
    if last is None:
        return True  # never sent -> send now
    return (now_utc - last) >= timedelta(hours=SUMMARY_EVERY_HOURS)


def build_summary(current: dict[str, dict], watch_sizes: list[str],
                  fetch_failures: int) -> str:
    """A daily heartbeat: current status of every watched size per product."""
    lines = ["📋 <b>ملخص — beyondfit-monitor</b>", ""]
    lines.append(f"حالة المقاسات {', '.join(watch_sizes)} الحين:")
    for info in current.values():
        states = []
        for size in watch_sizes:
            ok = info["sizes"].get(size)
            mark = "✅ متوفر" if ok else "❌ نافد"
            states.append(f"{size}: {mark}")
        lines.append(f"• <b>{info['title']}</b> — {' | '.join(states)}")
    if fetch_failures:
        lines.append(f"\n⚠️ تعذّر قراءة {fetch_failures} منتج هذي المرة.")
    lines.append("\nالبوت شغّال ✅ وراح ينبهك أول ما ينزل مقاسك.")
    return "\n".join(lines)


def load_config() -> tuple[list[str], list[str]]:
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    products = [u.strip() for u in cfg.get("products", []) if u.strip()]
    watch = [s.strip() for s in cfg.get("watch_sizes", ["M"]) if s.strip()]
    return products, watch


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def perform_check(token: str, chat_id: str, products: list[str],
                  watch_sizes: list[str], force_summary: bool) -> int:
    """Run ONE full check: read every product, notify watched-size
    sold-out -> in-stock transitions, persist the updated state, and emit the
    heartbeat summary if due. Returns 0 on success, 1 if anything failed.

    State is saved at the end of every call, so when this is invoked several
    times within a single run, a size that already triggered an alert won't
    alert again on the next check inside the same run.
    """
    now_utc = datetime.now(timezone.utc)
    now_ksa = now_utc + timedelta(hours=KSA_OFFSET_HOURS)
    want_summary = force_summary or summary_due(now_utc, load_last_summary())
    print(f"Watching sizes {watch_sizes} across {len(products)} products. "
          f"KSA now {now_ksa.strftime('%Y-%m-%d %H:%M')}; "
          f"summary {'DUE' if want_summary else 'not due'}.")

    # Collect current availability for every product.
    current: dict[str, dict] = {}
    fetch_failures = 0
    for url in products:
        try:
            info = collect_product(url)
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED to fetch {url}: {e}", file=sys.stderr)
            fetch_failures += 1
            continue
        if info is None:
            fetch_failures += 1
            continue
        avail = [s for s in watch_sizes if info["sizes"].get(s)]
        print(f"  {info['key']}  {info['title'][:40]!r}  "
              f"watched-in-stock={avail or '—'}")
        current[info["key"]] = info
        time.sleep(0.5)  # polite spacing between product fetches

    if not current:
        print("No products could be read — aborting without touching state.", file=sys.stderr)
        return 1

    previous = load_state()
    first_run = not previous

    if first_run:
        save_state(current)
        print("First run: baseline saved, no notifications sent.")
        if want_summary:
            try:
                send_telegram(token, chat_id, build_summary(current, watch_sizes, fetch_failures))
                save_last_summary(now_utc)
                print("Heartbeat summary sent.")
            except Exception as e:  # noqa: BLE001
                print(f"  failed to send summary: {e}", file=sys.stderr)
        return 0

    # Detect sold-out -> in-stock transitions for watched sizes.
    notifications: list[str] = []
    for key, info in current.items():
        prev_sizes = (previous.get(key) or {}).get("sizes", {})
        for size in watch_sizes:
            now_avail = bool(info["sizes"].get(size))
            was_avail = bool(prev_sizes.get(size))  # missing -> treated as False
            if now_avail and not was_avail:
                notifications.append(
                    "🎉 <b>رجع متوفر!</b>\n\n"
                    f"<b>{info['title']}</b>\n"
                    f"المقاس <b>{size}</b> صار متوفر الحين.\n"
                    f"{info['url']}"
                )

    print(f"Transitions to notify: {len(notifications)}")

    failed = False
    for msg in notifications:
        try:
            send_telegram(token, chat_id, msg)
            time.sleep(0.5)
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED to send notification: {e}", file=sys.stderr)
            failed = True

    # Build new state: keep previous entries for products we couldn't read this
    # run, and overwrite with fresh data for the ones we did read. This way a
    # transient fetch failure doesn't wipe history or cause a false "back in
    # stock" alert next run.
    merged = dict(previous)
    merged.update(current)
    save_state(merged)

    if want_summary:
        try:
            send_telegram(token, chat_id, build_summary(current, watch_sizes, fetch_failures))
            save_last_summary(now_utc)
            print("Heartbeat summary sent.")
        except Exception as e:  # noqa: BLE001
            print(f"  failed to send summary: {e}", file=sys.stderr)

    if failed:
        print("Some notifications failed — surfacing as failure.", file=sys.stderr)
        return 1
    if fetch_failures:
        print(f"{fetch_failures} product(s) could not be read this check.", file=sys.stderr)

    return 0


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.", file=sys.stderr)
        return 2

    truthy = {"1", "true", "yes"}
    force_summary = (
        os.environ.get("FORCE_SUMMARY", "").strip().lower() in truthy
        or os.environ.get("SEND_SUMMARY", "").strip().lower() in truthy
    )

    products, watch_sizes = load_config()
    if not products:
        print("ERROR: no products configured in products.json.", file=sys.stderr)
        return 2

    # One run performs several checks spaced apart, so a single hourly GitHub
    # schedule covers the whole hour (e.g. 4 checks 15 min apart) instead of
    # relying on GitHub's delayed/skipped cron to fire 4 separate runs.
    checks = max(1, _int_env("CHECKS_PER_RUN", 4))
    interval = max(0, _int_env("CHECK_INTERVAL_SECONDS", 900))
    total_min = (checks - 1) * interval // 60
    print(f"Run plan: {checks} check(s), {interval}s apart (~{total_min} min total).",
          flush=True)

    worst = 0
    for i in range(checks):
        if i > 0:
            print(f"--- sleeping {interval}s before check {i + 1}/{checks} ---", flush=True)
            time.sleep(interval)
        print(f"\n===== CHECK {i + 1}/{checks} =====", flush=True)
        rc = perform_check(token, chat_id, products, watch_sizes, force_summary)
        worst = max(worst, rc)

    return worst


if __name__ == "__main__":
    sys.exit(main())
