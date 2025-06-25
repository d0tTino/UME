# UME Frontend

This directory contains a small React dashboard for the UME API. It allows you to log in, view graph statistics and recent audit events, and toggle alignment policies.

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
