"""Command line: grocery-assistant {serve,run,list}."""
import argparse
import logging
import sys
from datetime import date

from grocery_assistant.config import Settings, load_queries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="grocery-assistant")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="run the scheduler (container default)")
    sub.add_parser("list", help="list the configured queries")
    r = sub.add_parser("run", help="run one query now")
    r.add_argument("query")
    r.add_argument("--dry-run", action="store_true", help="print instead of posting")
    r.add_argument("--date", type=date.fromisoformat, help="pretend today is YYYY-MM-DD")
    args = parser.parse_args(argv)

    settings = Settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # it logs every request at INFO
    queries = load_queries(settings.config)

    if args.cmd == "list":
        for q in queries.values():
            print(f"{q.name}\t{q.schedule}\t-> {q.webhook}")
        return 0
    if args.cmd == "run":
        if args.query not in queries:
            parser.error(f"unknown query {args.query!r}; known: {', '.join(queries)}")
        from grocery_assistant.runner import run

        try:
            run(queries[args.query], day=args.date, dry_run=args.dry_run)
        except Exception:
            return 1
        return 0

    from grocery_assistant.scheduler import serve

    serve(queries, settings.tz)
    return 0


if __name__ == "__main__":
    sys.exit(main())
