"""Lidl: parsing the offers page and selecting a week, against a trimmed copy."""
from datetime import date
from pathlib import Path

import httpx
import pytest

from grocery_assistant import notify
from grocery_assistant.config import load_queries
from grocery_assistant.formatters import offer_line
from grocery_assistant.runner import collect, run
from grocery_assistant.stores.lidl import LidlClient, PageChanged, parse_offers_page

ROOT = Path(__file__).parent.parent
PAGE = (ROOT / "tests/fixtures/lidl_offers.html").read_text()
MON, SUN = date(2026, 11, 23), date(2026, 11, 22)


def lidl_transport(page: str = PAGE, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "www.lidl.nl"
        assert request.headers["User-Agent"].startswith("grocery-assistant/")
        return httpx.Response(status, text=page)

    return httpx.MockTransport(handler)


@pytest.fixture
def query():
    return load_queries(ROOT / "config/queries.yaml")["lidl-meat-fish-meals"]


def by_title(day=MON):
    return {o.title: o for o in parse_offers_page(PAGE)}


def test_parse():
    offers = by_title()
    rib = offers["Runderriblappen"]  # "- Runderriblappen" on the page
    assert rib.category == "Vlees & gevogelte"
    assert (rib.price, rib.member_price, rib.size) == (10.96, 9.49, "700 g")
    assert (rib.start, rib.end) == (date(2026, 11, 23), date(2026, 11, 29))
    assert rib.url.startswith("https://www.lidl.nl/p/")
    assert offers["Chipolataworstjes"].start == date(2026, 11, 26)  # Thursday offer
    assert offers["Kipfilet"].member_price is None


def test_week_window_and_categories(query):
    with LidlClient(transport=lidl_transport()) as c:
        sections = dict(collect(query, c, MON))
    meat = [o.title for o in sections["Meat & cold cuts"]]
    # Monday offers first, then Thursday's; vegetables and beer are left out
    assert meat[-1] == "Chipolataworstjes" and set(meat) == {
        "Runderriblappen", "Kipfilet", "Chipolataworstjes"}
    assert [o.title for o in sections["Fish"]] == ["Nautica Gerookte zalm"]
    assert [o.title for o in sections["Ready meals"]] == ["Stamppotaardappelen"]


def test_day_window_drops_thursday(query):
    q = query.model_copy(update={"window": "day"})
    with LidlClient(transport=lidl_transport()) as c:
        meat = [o.title for o in dict(collect(q, c, MON))["Meat & cold cuts"]]
    assert "Chipolataworstjes" not in meat


def test_lines():
    o = by_title()
    assert offer_line(o["Runderriblappen"], MON).endswith(
        "(700 g) — €10,96 · **€9,49 met Lidl Plus**")
    assert offer_line(o["Kipfilet"], MON).endswith("— **€9,49**")
    assert "_vanaf do 26 nov_" in offer_line(o["Chipolataworstjes"], MON)
    assert "vanaf" not in offer_line(o["Chipolataworstjes"], date(2026, 11, 26))


def test_dry_run(query, capsys):
    posts = run(query, day=MON, dry_run=True, client=LidlClient(transport=lidl_transport()))
    assert posts[0].startswith("#### Lidl week 48: meat, fish & ready meals\n5 offers")
    assert "**Meat & cold cuts (3)**" in capsys.readouterr().out


def test_changed_page_is_reported(query, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "post", lambda name, texts: sent.append(texts[0]))
    with pytest.raises(PageChanged):
        run(query, day=MON, client=LidlClient(transport=lidl_transport("<html></html>")))
    assert "lidl-meat-fish-meals: fetching failed" in sent[0]


def test_sunday_run_sees_nothing_of_next_week_in_day_mode(query):
    q = query.model_copy(update={"window": "day"})
    with LidlClient(transport=lidl_transport()) as c:
        assert all(not os for _, os in collect(q, c, SUN))
