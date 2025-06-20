# LLM Ferry

`LLMFerry` is a lightweight [GraphListener](docs/GRAPH_LISTENERS.md) that sends summary information about graph events to an external HTTP service. It can be used to notify an LLM-based agent or any other API whenever nodes or edges are created or updated.

## Example Usage

```python
from ume.llm_ferry import LLMFerry
from ume._internal.listeners import register_listener

ferry = LLMFerry(api_url="https://example.com/api", api_key="my-token")
register_listener(ferry)
```

Once registered, the ferry will POST a short description of each graph mutation to the configured URL. The payload includes only a `text` field, so the receiving service is free to interpret the message however it likes.

## Configuration

`LLMFerry` reads its defaults from environment variables:

- `LLM_FERRY_API_URL` &ndash; target endpoint used for POST requests.
- `LLM_FERRY_API_KEY` &ndash; optional bearer token for authentication.

These can be set directly in your environment or in a `.env` file:

```bash
LLM_FERRY_API_URL=https://example.com/api
LLM_FERRY_API_KEY=your-secret-key
```

When no API key is provided, the `Authorization` header is omitted.
