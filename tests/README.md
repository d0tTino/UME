# Test Suite Dependencies

The test suite requires several optional packages that are not installed with the default environment. To run the tests locally ensure the following packages are available:

- `pydantic-settings`
- `fastapi`
- `httpx`
- `pyyaml`
- `neo4j`
- `numpy`
- `jsonschema`
- `prometheus-client`
- `confluent-kafka`
- `networkx`
- `structlog`
- `fastapi-limiter`
- `sse-starlette`
- `watchdog`
- `python-multipart`
- `grpcio`
- `grpcio-tools`

Many tests also rely on `faiss` and `sentence-transformers`, but these are optional. Tests that require them will be skipped if the packages are not available.

Install all of the above dependencies in one step with:
```bash
poetry install --with dev --all-extras
```
