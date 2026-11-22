"""Runs one query: fetch, filter, format, post."""
import logging
from datetime import date, timedelta

from grocery_assistant import notify
from grocery_assistant.config import Query
from grocery_assistant.formatters import build_posts
from grocery_assistant.models import Offer
from grocery_assistant.stores.ah import AHClient
from grocery_assistant.stores.lidl import LidlClient

log = logging.getLogger(__name__)

Sections = list[tuple[str, list[Offer]]]


def fetch_ah(query: Query, client: AHClient, day: date) -> list[Offer]:
    offers = []
    for cat in query.categories:
        for p in client.bonus_products(cat.id):
            if query.in_store_only and not p.in_store:
                continue
            offers.append(p.to_offer())
    return offers


def fetch_lidl(query: Query, client: LidlClient, day: date) -> list[Offer]:
    return client.offers()


def select(query: Query, offers: list[Offer], day: date) -> Sections:
    """Keep the offers in the query's categories and date window, per section."""
    last = day + timedelta(days=6) if query.window == "week" else day
    section_of = {name: c.label for c in query.categories for name in c.match}
    by_label: dict[str, dict[str, Offer]] = {c.label: {} for c in query.categories}
    for o in offers:
        label = section_of.get(o.category or "")
        if label and o.overlaps(day, last):
            by_label[label].setdefault(o.product_id, o)
    return [
        (c.label, sorted(by_label[c.label].values(),
                         key=lambda o: (o.start or day, o.sub_category or "", o.title)))
        for c in query.categories
    ]


def collect(query: Query, client, day: date) -> Sections:
    fetch = fetch_ah if query.store == "ah" else fetch_lidl
    return select(query, fetch(query, client, day), day)


def new_client(query: Query):
    return AHClient() if query.store == "ah" else LidlClient()


def run(query: Query, day: date | None = None, dry_run: bool = False, client=None) -> list[str]:
    day = day or date.today()
    log.info("running %s for %s", query.name, day)
    try:
        with client or new_client(query) as c:
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
