#!/usr/bin/env python3
"""
Daily Morning Briefing — collects AI + Frontend tech news from HN and RSS feeds.
Outputs raw structured data to ~/.cursor/briefing/YYYY-MM-DD.md
Cursor AI handles summarization at read time.

Gap detection: if previous days are missing, uses HN "best stories" endpoint
and increases fetch volume to compensate for missed content.
"""

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    sys.exit("Missing 'requests'. Run: pip3 install requests feedparser")

try:
    import feedparser
except ImportError:
    sys.exit("Missing 'feedparser'. Run: pip3 install requests feedparser")

BRIEFING_DIR = Path.home() / ".cursor" / "briefing"
MAX_HN_STORIES_NORMAL = 80
MAX_HN_STORIES_CATCHUP = 200
MAX_RSS_PER_FEED_NORMAL = 10
MAX_RSS_PER_FEED_CATCHUP = 30
KEEP_DAYS = 7

AI_KEYWORDS = re.compile(
    r"\b(ai|llm|gpt|claude|anthropic|openai|gemini|mistral|llama|"
    r"transformer|diffusion|embedding|rag|agent|copilot|cursor|"
    r"machine.?learning|deep.?learning|neural|chatbot|reasoning|"
    r"fine.?tun|prompt|token|model|benchmark|alignment|rlhf|"
    r"multimodal|vision.?model|code.?gen|agentic)\b",
    re.IGNORECASE,
)

FRONTEND_KEYWORDS = re.compile(
    r"\b(vue|nuxt|react|next\.?js|svelte|typescript|javascript|"
    r"tailwind|css|webpack|vite|tiptap|prosemirror|pinia|"
    r"component|frontend|web.?dev|browser|dom|ssr|ssg|"
    r"node\.?js|deno|bun)\b",
    re.IGNORECASE,
)

RSS_FEEDS = {
    "AI": [
        ("Anthropic Blog", "https://www.anthropic.com/rss.xml"),
        ("OpenAI Blog", "https://openai.com/blog/rss.xml"),
        ("HuggingFace Blog", "https://huggingface.co/blog/feed.xml"),
        ("MIT Tech Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
        ("Ars Technica AI", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
        ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
        ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("arXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI"),
        ("arXiv cs.CL", "https://rss.arxiv.org/rss/cs.CL"),
        ("36Kr AI", "https://36kr.com/feed"),
    ],
    "Frontend": [
        ("Vue.js Blog", "https://blog.vuejs.org/feed.rss"),
        ("Nuxt Blog", "https://nuxt.com/blog/rss.xml"),
        ("Dev.to Vue", "https://dev.to/feed/tag/vue"),
        ("Dev.to TypeScript", "https://dev.to/feed/tag/typescript"),
        ("CSS-Tricks", "https://css-tricks.com/feed/"),
        ("Smashing Magazine", "https://www.smashingmagazine.com/feed/"),
        ("web.dev", "https://web.dev/feed.xml"),
    ],
}


def detect_gap():
    """Check how many recent days are missing briefings. Returns gap count (0 = no gap)."""
    today = datetime.now().date()
    gap = 0
    for i in range(1, KEEP_DAYS + 1):
        check_date = today - timedelta(days=i)
        if not (BRIEFING_DIR / f"{check_date.isoformat()}.md").exists():
            gap += 1
        else:
            break
    return gap


def fetch_hn_stories(catchup=False):
    """Fetch HN stories. In catchup mode, also fetch 'best stories' with higher volume."""
    max_stories = MAX_HN_STORIES_CATCHUP if catchup else MAX_HN_STORIES_NORMAL
    endpoints = ["https://hacker-news.firebaseio.com/v0/topstories.json"]
    if catchup:
        endpoints.append("https://hacker-news.firebaseio.com/v0/beststories.json")

    all_story_ids = set()
    for endpoint in endpoints:
        try:
            resp = requests.get(endpoint, timeout=15)
            resp.raise_for_status()
            all_story_ids.update(resp.json()[:max_stories])
        except Exception as e:
            print(f"[HN] Failed to fetch from {endpoint}: {e}", file=sys.stderr, flush=True)

    if not all_story_ids:
        return []

    story_ids = list(all_story_ids)[:max_stories]

    def fetch_item(sid):
        try:
            r = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    items = []
    with ThreadPoolExecutor(max_workers=15) as pool:
        futures = {pool.submit(fetch_item, sid): sid for sid in story_ids}
        for future in as_completed(futures):
            item = future.result()
            if not item or item.get("type") != "story":
                continue
            title = item.get("title", "")
            url = item.get("url", f"https://news.ycombinator.com/item?id={item['id']}")
            score = item.get("score", 0)

            category = None
            if AI_KEYWORDS.search(title):
                category = "AI"
            if FRONTEND_KEYWORDS.search(title):
                category = "Frontend" if category is None else "Both"
            if category:
                items.append({
                    "title": title, "url": url, "score": score,
                    "source": "HN", "category": category,
                    "desc": "",
                })
    return items


def clean_html(text):
    """Strip HTML tags from RSS description."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:300] if len(clean) > 300 else clean


def fetch_rss_feed(name, url, max_items):
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        entries = []
        for entry in feed.entries[:max_items]:
            desc = clean_html(
                entry.get("summary", entry.get("description", ""))
            )
            entries.append({
                "title": entry.get("title", "Untitled"),
                "url": entry.get("link", ""),
                "score": "--", "source": name, "category": None,
                "desc": desc,
            })
        return entries
    except Exception as e:
        print(f"[RSS] Failed to fetch {name}: {e}", file=sys.stderr, flush=True)
        return []


RSS_TIMEOUT_PER_FEED = 30

def fetch_all_rss(catchup=False):
    max_per_feed = MAX_RSS_PER_FEED_CATCHUP if catchup else MAX_RSS_PER_FEED_NORMAL
    items_ai, items_fe = [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {}
        for category, feeds in RSS_FEEDS.items():
            for name, url in feeds:
                futures[pool.submit(fetch_rss_feed, name, url, max_per_feed)] = (category, name)
        try:
            for future in as_completed(futures, timeout=90):
                category, name = futures[future]
                try:
                    entries = future.result(timeout=RSS_TIMEOUT_PER_FEED)
                except Exception as e:
                    print(f"[RSS] Timed out or failed: {name}: {e}", file=sys.stderr, flush=True)
                    continue
                for entry in entries:
                    entry["category"] = category
                (items_ai if category == "AI" else items_fe).extend(entries)
        except TimeoutError:
            pending = [f for f in futures if not f.done()]
            names = [futures[f][1] for f in pending]
            print(f"[RSS] Overall timeout reached. Skipping {len(pending)} feeds: {', '.join(names)}", file=sys.stderr, flush=True)
            for f in pending:
                f.cancel()
    return items_ai, items_fe


def deduplicate(items):
    seen = set()
    result = []
    for item in items:
        url = item["url"]
        if url and url not in seen:
            seen.add(url)
            result.append(item)
    return result


def build_markdown(ai_items, fe_items, today, gap_days=0):
    catchup_note = ""
    if gap_days > 0:
        catchup_note = f"\n**Catch-up mode**: {gap_days} day(s) missed. Extended fetch to compensate.\n"

    lines = [
        f"# Raw Briefing Data — {today}",
        f"Generated at: {datetime.now().strftime('%H:%M')}",
        catchup_note,
        "---", "",
    ]

    def write_table(items, section_name):
        lines.append(f"## {section_name} ({len(items)} items)")
        lines.append("")
        if not items:
            lines.append("_No items found today._")
            lines.append("")
            return
        for item in items:
            title = item["title"]
            url = item["url"]
            score = item["score"]
            source = item["source"]
            desc = item.get("desc", "")
            lines.append(f"- **[{title}]({url})** (Score: {score} | {source})")
            if desc:
                lines.append(f"  > {desc}")
            lines.append("")

    write_table(ai_items, "AI / LLM")
    write_table(fe_items, "Frontend")
    return "\n".join(lines)


def cleanup_old_briefings():
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    for f in BRIEFING_DIR.glob("????-??-??.md"):
        try:
            file_date = datetime.strptime(f.stem, "%Y-%m-%d")
            if file_date < cutoff:
                f.unlink()
                print(f"[Cleanup] Removed {f.name}")
        except ValueError:
            pass


def main():
    BRIEFING_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = BRIEFING_DIR / f"{today}.md"

    gap = detect_gap()
    catchup = gap > 0

    if catchup:
        print(f"[Briefing] Catch-up mode: {gap} day(s) missing. Fetching more aggressively...", flush=True)
    print(f"[Briefing] Collecting news for {today}...", flush=True)

    hn_items = fetch_hn_stories(catchup=catchup)
    print(f"[HN] Found {len(hn_items)} relevant stories", flush=True)

    rss_ai, rss_fe = fetch_all_rss(catchup=catchup)
    print(f"[RSS] Found {len(rss_ai)} AI + {len(rss_fe)} Frontend items", flush=True)

    ai_items = deduplicate(sorted(
        [i for i in hn_items if i["category"] in ("AI", "Both")] + rss_ai,
        key=lambda x: (x["score"] if isinstance(x["score"], int) else 0),
        reverse=True,
    ))
    fe_items = deduplicate(sorted(
        [i for i in hn_items if i["category"] in ("Frontend", "Both")] + rss_fe,
        key=lambda x: (x["score"] if isinstance(x["score"], int) else 0),
        reverse=True,
    ))

    md = build_markdown(ai_items, fe_items, today, gap_days=gap)
    output_path.write_text(md, encoding="utf-8")
    print(f"[Briefing] Written to {output_path} ({len(ai_items)} AI + {len(fe_items)} FE items)", flush=True)

    cleanup_old_briefings()
    print("[Briefing] Done.", flush=True)


if __name__ == "__main__":
    main()
