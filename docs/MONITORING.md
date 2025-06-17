# Monitoring

UME exposes Prometheus metrics at `/metrics`. This guide shows how to collect
those metrics with Prometheus and visualize them in Grafana.

## Scraping Metrics with Prometheus

Add a job for UME in your `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ume'
    metrics_path: /metrics
    static_configs:
      - targets: ['ume:8000']
```

## Docker Compose Example

The following compose file runs UME, Prometheus and Grafana:

```yaml
version: '3'
services:
  ume:
    build: ..
    ports:
      - "8000:8000"
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

Start the stack with `docker-compose up`. Prometheus will scrape
`ume:8000/metrics`, and Grafana will be available at `http://localhost:3000`.

## Viewing Results in Grafana

1. Open `http://localhost:3000` and log in with the default `admin`/`admin`
   credentials.
2. Add a Prometheus data source pointing to `http://prometheus:9090`.
3. Create a dashboard and add graphs using the `ume_http_requests_total` and
   other metrics exposed by UME.
