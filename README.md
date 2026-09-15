# Web Page Intelligence

A small Flask service that analyzes public HTML pages and returns structured content and basic SEO signals. It includes a browser interface, a JSON API, a health endpoint, and an A2A-compatible agent card.

## Features

- Analyze a public URL with `POST /api/analyze`.
- Analyze supplied HTML directly for deterministic integrations.
- Extract title, meta description, headings, word count, links, images, and image alt-text coverage.
- Reject localhost and private-network targets to reduce SSRF risk.
- JSON health check at `/health`.
- Agent metadata at `/.well-known/agent-card.json`.

## Local setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

Open <http://127.0.0.1:5000> in a browser.

## API

```bash
curl -X POST http://127.0.0.1:5000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}'
```

For tests or trusted integrations, HTML can be supplied without a network request:

```bash
curl -X POST http://127.0.0.1:5000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"html":"<html><title>Example</title><h1>Hello</h1></html>"}'
```

## Deployment

The repository includes both `render.yaml` and `Procfile` for Render-style Python deployment. The service listens on the port supplied by Gunicorn/Render.

## Security notes

Only analyze public pages that you are authorized to access. The URL fetcher blocks localhost and private, loopback, link-local, and reserved IP addresses. It applies a timeout and a 2 MB HTML limit, but a production deployment should also add rate limiting, logging controls, and an outbound proxy/firewall policy.

## License

MIT
