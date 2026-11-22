"""Runs one query: fetch, filter, format, post."""
import logging
from datetime import date

from grocery_assistant import notify
from grocery_assistant.config import Query
from grocery_assistant.formatters import build_posts
from grocery_assistant.models import Product
from grocery_assistant.stores.ah import AHClient

log = logging.getLogger(__name__)


def collect(query: Query, client: AHClient, day: date) -> list[tuple[str, list[Product]]]:
    wanted = {c.main_category for c in query.categories}
    by_cat: dict[str, dict[int, Product]] = {c.main_category: {} for c in query.categories}
    for cat in query.categories:
        for p in client.bonus_products(cat.id):
            if p.main_category not in wanted or not p.valid_on(day):
                continue
            if query.in_store_only and not p.in_store:
                continue
            by_cat[p.main_category].setdefault(p.webshop_id, p)
    sections = []
    for cat in query.categories:
        products = sorted(by_cat[cat.main_category].values(),
                          key=lambda p: (p.sub_category or "", p.title))
        sections.append((cat.label, products))
    return sections


def run(query: Query, day: date | None = None, dry_run: bool = False,
        client: AHClient | None = None) -> list[str]:
    day = day or date.today()
    log.info("running %s for %s", query.name, day)
    try:
        with client or AHClient() as c:
            posts = build_posts(query.title, collect(query, c, day), day)
    except Exception as e:
        log.exception("query %s failed", query.name)
        if not dry_run:
            msg = f"#### {query.name}: fetching failed\n`{type(e).__name__}: {e}`"
            notify.post(query.webhook, [msg])
        raise
    if dry_run:
        print("\n\n---\n\n".join(posts))
    else:
        notify.post(query.webhook, posts)
    log.info("%s: %s %s post(s)", query.name, "printed" if dry_run else "sent", len(posts))
    return posts
