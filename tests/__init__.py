# This file makes the tests directory a Python package.
"""Test package initialization and environment configuration."""

import os

# Ensure config validation passes when tests import ume.config
os.environ.setdefault("UME_AUDIT_SIGNING_KEY", "test-key")
