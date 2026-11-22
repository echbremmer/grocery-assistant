"""Markdown for Mattermost, split into posts under the length limit."""
from datetime import date

from grocery_assistant.models import Product

MAX_POST = 15000  # Mattermost allows 16,383 characters per post


def euro(v: float | None) -> str:
    return f"€{v:.2f}".replace(".", ",") if v is not None else ""


def product_line(p: Product) -> str:
    offer = p.bonus_mechanism or "bonus"
    before, now = euro(p.price_before), euro(p.price_now)
    price = f"{before} → {now}" if before and now else before
    return f"- [{p.title}]({p.url}) — **{offer}**" + (f" ({price})" if price else "")


def build_posts(title: str, sections: list[tuple[str, list[Product]]], day: date) -> list[str]:
    """sections: (label, products) in display order; empty sections are skipped."""
    total = sum(len(ps) for _, ps in sections)
    ends = sorted({p.bonus_end for _, ps in sections for p in ps if p.bonus_end})
    heading = "#### " + title.format(week=day.isocalendar().week)
    summary = f"{total} in-store offers" if total else "No bonus offers found"
    if ends:
        summary += ", valid until " + ", ".join(d.strftime("%a %-d %b") for d in ends)
    lines = [heading, summary + "."]
    for label, products in sections:
        if products:
            lines += ["", f"**{label} ({len(products)})**", *map(product_line, products)]
    return split(lines)


def split(lines: list[str], limit: int = MAX_POST) -> list[str]:
    posts, cur = [], ""
    for line in lines:
        if cur and len(cur) + 1 + len(line) > limit:
            posts.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line
    posts.append(cur)
    return posts
