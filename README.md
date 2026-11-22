# grocery-assistant

Posts supermarket bonus offers to Mattermost on a schedule. The first and only
query so far: every Monday at 08:00, this week's **in-store Albert Heijn bonus**
for meat, cold cuts, fish and ready meals goes to the channel
**Supermarket prices**.

It runs as a Docker Compose stack on a home server. The image is published to
Docker Hub as `takecharge/grocery-assistant`.

## How it works

- One long-running container (`grocery-assistant serve`). APScheduler runs each
  query from `config/queries.yaml` on its cron schedule, in the container's
  `TZ` (Europe/Amsterdam).
- A query searches the **AH app API** (`api.ah.nl`, the API the Appie app uses)
  with an anonymous token, per top-level category, for bonus products. It keeps
  in-store (`NATIONAL`) offers that are valid today, and only products whose
  `mainCategory` matches the query.
- The result is posted as Markdown to a Mattermost **incoming webhook**, split
  into several posts if it is longer than Mattermost allows.
- If fetching fails, the error is posted to the same webhook and logged. The
  scheduler keeps running.

The AH API is undocumented and can change without notice. ah.nl itself refuses
automated requests (HTTP 403). Responses are validated with pydantic, so a
changed field fails loudly instead of producing a wrong list.

## Layout

| Path | What |
| --- | --- |
| `config/queries.yaml` | The scheduled queries (name, title, store, schedule, webhook, categories) |
| `src/grocery_assistant/stores/ah.py` | AH API client: token, per-category bonus search |
| `src/grocery_assistant/models.py` | pydantic `Product` |
| `src/grocery_assistant/runner.py` | Runs a query: fetch, filter, format, post |
| `src/grocery_assistant/formatters.py` | Markdown and post splitting |
| `src/grocery_assistant/notify.py` | Mattermost webhook |
| `src/grocery_assistant/scheduler.py` | APScheduler, one cron job per query |
| `src/grocery_assistant/cli.py` | `serve`, `run <query> [--dry-run] [--date]`, `list` |
| `tests/` | pytest with recorded API responses, no network |
| `Dockerfile` | Multi-stage build with uv; runs as `568:568` |
| `compose.example.yml` | The stack definition |
| `.github/workflows/publish.yml` | Tests, then builds and pushes the image to Docker Hub |

## Configuration

Environment (in the stack's `.env`, never in git):

| Variable | Meaning |
| --- | --- |
| `MATTERMOST_WEBHOOK_<NAME>` | Webhook URL for the `webhook: <name>` used in a query, e.g. `MATTERMOST_WEBHOOK_SUPERMARKET_PRICES`. Use `http://mattermost:8065/hooks/<id>` (container network) |
| `TZ` | Timezone for the schedules (from `defaults.env`) |
| `GA_LOG_LEVEL` | Default `INFO` |
| `GA_CONFIG` | Path of the queries file; the image sets `/app/config/queries.yaml` |

To add a query, add an entry to `config/queries.yaml`, and a webhook variable if
it posts to a new channel. AH top-level category ids found so far are listed at
the bottom of that file.

## Commands

```sh
# in the stack folder
docker compose exec grocery-assistant grocery-assistant list
docker compose exec grocery-assistant grocery-assistant run ah-meat-fish-meals --dry-run
docker compose exec grocery-assistant grocery-assistant run ah-meat-fish-meals   # posts now
docker compose logs -f
```

## Release and deploy

GitHub Actions (`.github/workflows/publish.yml`) runs the tests on every push
and pull request. On a push to `main` it publishes
`takecharge/grocery-assistant:latest` and `:<short sha>`.

To release, push a version tag:

```sh
git tag v0.2.0 && git push origin v0.2.0
```

That publishes `takecharge/grocery-assistant:0.1.0` and commits the new tag
into `compose.example.yml` and this README on `main`.

The server runs a pinned version: takecharge/grocery-assistant:0.1.0 To
upgrade, change the tag in the stack's `docker-compose.yml` and run
`docker compose up -d`. Nothing deploys by itself.

Repository secrets: `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (a Docker Hub
access token with read and write access).

## Development

```sh
uv sync
uv run pytest
uv run ruff check .
```

Without a local uv:
`docker run --rm -v "$PWD":/w -w /w ghcr.io/astral-sh/uv:0.9.5-python3.13-bookworm-slim sh -c 'uv sync && uv run pytest'`
