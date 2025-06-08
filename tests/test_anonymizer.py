from ume.anonymizer import anonymize_email


def test_anonymize_email_basic():
    payload = {"email": "user@example.com"}
    result, flag = anonymize_email(payload)
    assert flag is True
    assert result["email"] == "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514"
