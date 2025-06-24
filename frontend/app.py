import json

import httpx
from httpx import QueryParams
import argparse


def fetch_token(api_url: str, username: str, password: str) -> str:
    resp = httpx.post(
        f"{api_url}/token", data={"username": username, "password": password}
    )
    resp.raise_for_status()
    return resp.json()["access_token"]



def run_query(api_url: str, token: str, cypher: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get(f"{api_url}/query", params={"cypher": cypher}, headers=headers)
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2))


def search_vectors(api_url: str, token: str, vector: str, k: int) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    floats = [float(x) for x in vector.split(',') if x.strip()]
    params_list: list[tuple[str, str | int | float | bool | None]] = [
        ("vector", str(v)) for v in floats
    ] + [("k", k)]
    params = QueryParams(params_list)
    resp = httpx.get(
        f"{api_url}/vectors/search", params=params, headers=headers
    )
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Interact with the UME API")
    parser.add_argument("command", choices=["query", "search"], help="Operation to perform")
    parser.add_argument("value", help="Cypher query or comma-separated vector")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Base API URL")
    parser.add_argument("--username", required=True, help="API username")
    parser.add_argument("--password", required=True, help="API password")
    parser.add_argument("--k", type=int, default=5, help="Neighbors to return when searching")
    args = parser.parse_args()

    token = fetch_token(args.api_url, args.username, args.password)
    if args.command == "query":
        run_query(args.api_url, token, args.value)
    else:
        search_vectors(args.api_url, token, args.value, args.k)


if __name__ == "__main__":
    main()
