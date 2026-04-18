"""Shared pytest configuration.

Ensures imports like `from app.services...` work when pytest is invoked from
anywhere, and sets a SECRET_KEY so that app.core.config's runtime validation
does not abort test collection.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-in-prod")
os.environ.setdefault("DEBUG", "true")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
