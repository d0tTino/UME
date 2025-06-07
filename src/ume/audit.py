from .config import settings
import json
import time
import hmac
import hashlib
import logging
from typing import List, Dict

try:
    import boto3  # type: ignore
except Exception:  # pragma: no cover - boto3 optional
    boto3 = None  # type: ignore

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = settings.UME_AUDIT_LOG_PATH
SIGNING_KEY = settings.UME_AUDIT_SIGNING_KEY.encode()


def _parse_s3(path: str) -> tuple[str, str]:
    _, rest = path.split("://", 1)
    bucket, key = rest.split("/", 1)
    return bucket, key


def _read_lines(path: str) -> List[str]:
    if path.startswith("s3://"):
        if not boto3:
            raise ImportError(
                "boto3 is required to read from S3 paths but is not installed"
            )
        bucket, key = _parse_s3(path)
        s3 = boto3.client("s3")
        try:
            obj = s3.get_object(Bucket=bucket, Key=key)
            data = obj["Body"].read().decode()
        except Exception:
            return []
        return data.splitlines()
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return [line.rstrip("\n") for line in f]
        except FileNotFoundError:
            return []


def _write_lines(path: str, lines: List[str]) -> None:
    data = "\n".join(lines) + "\n"
    if path.startswith("s3://"):
        if not boto3:
            raise ImportError(
                "boto3 is required to write to S3 paths but is not installed"
            )
        bucket, key = _parse_s3(path)
        s3 = boto3.client("s3")
        s3.put_object(Bucket=bucket, Key=key, Body=data.encode())
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)


def log_audit_entry(user_id: str, reason: str, timestamp: int | None = None) -> None:
    ts = timestamp or int(time.time())
    lines = _read_lines(AUDIT_LOG_PATH)
    prev_sig = ""
    if lines:
        try:
            prev = json.loads(lines[-1])
            prev_sig = prev.get("signature", "")
        except json.JSONDecodeError:
            prev_sig = ""

    entry: Dict[str, str | int] = {
        "timestamp": ts,
        "user_id": user_id,
        "reason": reason,
        "prev": prev_sig,
    }
    msg = json.dumps(entry, sort_keys=True).encode()
    signature = hmac.new(SIGNING_KEY, msg, hashlib.sha256).hexdigest()
    entry["signature"] = signature
    lines.append(json.dumps(entry))
    _write_lines(AUDIT_LOG_PATH, lines)


def get_audit_entries() -> List[Dict[str, str | int]]:
    lines = _read_lines(AUDIT_LOG_PATH)
    entries: List[Dict[str, str | int]] = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries
