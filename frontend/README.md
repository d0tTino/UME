# UME Frontend

This directory contains a small React dashboard for the UME API. It allows you to log in, view graph statistics and recent audit events, toggle alignment policies, monitor PII redaction activity, and edit Rego policies.

## Development

Install dependencies with npm (Node 18+ required):

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

The app will be available at <http://localhost:5173>. The development server proxies requests to the running API at `http://localhost:8000`.

Run the frontend unit tests with Vitest (after `npm install` has installed all
dependencies):

```bash
npm test
```

The dashboard shows a counter of how many event payloads have been redacted for PII. It polls the `/pii/redactions` endpoint every second. Clicking a policy name opens an inline editor where you can modify the Rego code, validate it via the API, and save your changes.

## Building

Create an optimized build under `dist/`:

```bash
npm run build
```

You can preview the production build locally:

```bash
npm run preview
```

To deploy, serve the files in `frontend/dist/` with any static web server alongside the UME API.

### Serving the Dashboard

After building you can launch a small FastAPI server that mounts the static files at `/dashboard`:

```bash
poetry run python frontend/app.py
```

By default the server listens on port `8001`. Open <http://localhost:8001/dashboard/> to use the UI.
