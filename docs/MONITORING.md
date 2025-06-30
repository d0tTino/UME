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

## Example Grafana Panels

Here are a few Prometheus queries you can use when building graphs:

| Metric | Purpose | Example Query |
| ------ | ------- | ------------- |
| `ume_request_latency_seconds` | Average request latency | `rate(ume_request_latency_seconds_sum[5m]) / rate(ume_request_latency_seconds_count[5m])` |
| `ume_vector_query_latency_seconds` | Latency of vector similarity search | `rate(ume_vector_query_latency_seconds_sum[5m]) / rate(ume_vector_query_latency_seconds_count[5m])` |
| `ume_vector_index_size` | Number of vectors stored | `ume_vector_index_size` |
| `ume_stale_vector_count` | Vectors older than the freshness limit | `ume_stale_vector_count` |

You can combine these metrics in Grafana to visualize API performance and index
growth over time.

## Distributed Tracing with OpenTelemetry

Set the `UME_OTLP_ENDPOINT` environment variable to enable trace export via OTLP.
When configured, UME will emit spans for HTTP endpoints and graph operations.
You can point this endpoint at an OpenTelemetry Collector or any backend that
accepts OTLP over HTTP.

Example collector service in `docker-compose.yml`:

```yaml
  collector:
    image: otel/opentelemetry-collector-contrib
    ports:
      - "4318:4318"
```

Configure the collector to forward traces to Jaeger, Tempo, or another tracing
backend. With the collector running and `UME_OTLP_ENDPOINT=http://localhost:4318`,
traces will include spans for API calls and key graph operations.
