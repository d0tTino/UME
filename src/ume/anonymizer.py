import hashlib
from typing import Dict, Tuple, Any


def anonymize_email(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Return a copy of payload with the email field hashed.

    Parameters
    ----------
    payload: Dict[str, Any]
        Dictionary possibly containing an "email" key.

    Returns
    -------
    Tuple[Dict[str, Any], bool]
        A tuple containing the new payload and a boolean indicating whether
        anonymization occurred.
    """
    if "email" not in payload or not isinstance(payload["email"], str):
        return payload.copy(), False
    email = payload["email"]
    hashed = hashlib.sha256(email.encode()).hexdigest()
    new_payload = payload.copy()
    new_payload["email"] = hashed
    return new_payload, True
