#!/usr/bin/env python3
import argparse

from ume_cli import _quickstart


def main() -> None:
    """Entry point for the ``ume`` console script."""
    parser = argparse.ArgumentParser(description="UME helper commands")
    sub = parser.add_subparsers(dest="command")

    up_parser = sub.add_parser(
        "up", help="Create .env, generate certs and start the stack"
    )
    up_parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Create .env and certs without prompting",
    )

    args = parser.parse_args()
    if args.command == "up":
        _quickstart(args.no_confirm)
    else:
        parser.print_help()


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
