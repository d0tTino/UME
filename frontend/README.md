# UME Frontend

This directory contains a small React application that fetches graph data from
the running UME API and visualizes it using `vis-network`.

## Running the Demo

1. **Start the API**

   Launch the FastAPI server from the repository root:

   ```bash
   uvicorn ume.api:app --reload
   ```

   The default API token is `secret-token` (see `src/ume/config.py`).

2. **Serve the Frontend**

   In another terminal, start a simple static web server:

   ```bash
   cd frontend && python -m http.server 8001
   ```

   Then open `http://localhost:8001/index.html` in your browser.

3. **Load the Graph**

   Enter the API token when prompted and click **Load Graph** to fetch the
   `/analytics/subgraph` endpoint. You can also input a comma-separated vector
   to query `/vectors/search` via the optional search box.
