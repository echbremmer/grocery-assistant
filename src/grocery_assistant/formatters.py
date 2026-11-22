"""Markdown for Mattermost, split into posts under the length limit."""
from datetime import date

from grocery_assistant.models import Offer

MAX_POST = 15000  # Mattermost allows 16,383 characters per post
DAYS = ["ma", "di", "wo", "do", "vr", "za", "zo"]
MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def euro(v: float | None) -> str:
    return f"€{v:.2f}".replace(".", ",") if v is not None else ""


def nl_day(d: date) -> str:
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


def offer_line(o: Offer, day: date) -> str:
    """One Markdown bullet.

    AH:   - [AH Kipfilet](url) — **2 VOOR 5.00** (€4,49 → €3,49)
    Lidl: - [Zwagerman Verse rookworst](url) (275 g) — €2,69 · **€1,99 met Lidl Plus** (-26%)
    """
    parts = []
    if o.mechanism:
        price = (f"{euro(o.price_before)} → {euro(o.price)}" if o.price_before is not None
                 else euro(o.price))
        parts.append(f"**{o.mechanism}**" + (f" ({price})" if price else ""))
    else:
        if o.price_before is not None:
            parts.append(f"~~{euro(o.price_before)}~~ **{euro(o.price)}**")
        elif o.price is not None:
            parts.append(f"**{euro(o.price)}**" if o.member_price is None else euro(o.price))
    if o.member_price is not None:
        member = " ".join(x for x in (euro(o.member_price), o.member_label) if x)
        parts.append(f"**{member}**" + (f" ({o.member_discount})" if o.member_discount else ""))
    if o.start and o.start > day:
        parts.append(f"_vanaf {nl_day(o.start)}_")
    size = f" ({o.size})" if o.size and o.store != "ah" else ""
    return f"- [{o.title}]({o.url}){size} — " + " · ".join(parts)


def build_posts(title: str, sections: list[tuple[str, list[Offer]]], day: date) -> list[str]:
    """sections: (label, offers) in display order; empty sections are skipped."""
    total = sum(len(os) for _, os in sections)
    ends = sorted({o.end for _, os in sections for o in os if o.end})
    heading = "#### " + title.format(week=day.isocalendar().week)
    summary = f"{total} offers" if total else "No offers found"
    if ends:
        summary += ", valid until " + ", ".join(d.strftime("%a %-d %b") for d in ends)
    lines = [heading, summary + "."]
    for label, offers in sections:
        if offers:
            lines += ["", f"**{label} ({len(offers)})**", *(offer_line(o, day) for o in offers)]
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
