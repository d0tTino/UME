"""Utility functions for the Document Guru workflow."""
from __future__ import annotations


def reformat_document(content: str) -> str:
    """Return a lightly cleaned version of ``content``."""
    lines = [line.strip() for line in content.splitlines()]
    cleaned_lines: list[str] = [line for line in lines if line]
    return "\n".join(cleaned_lines)
