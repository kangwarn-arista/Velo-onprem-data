"""Shared test configuration.

Sets VCO_TOKEN and VCO_HOST environment variables before any test module
imports vco_edge_export, preventing module-level load_dotenv() and
os.getenv() from using real credentials.

Uses unittest.mock.patch.dict so the original environment is restored
after the test session completes (via pytest_unconfigure).
"""
import os
from unittest.mock import patch

# These must be set before vco_edge_export is imported (it reads env at
# module level).  conftest.py is loaded by pytest before test modules,
# so this runs early enough.
_env_patcher = patch.dict(os.environ, {
    "VCO_TOKEN": "Token test",
    "VCO_HOST": "test.example.com",
})
_env_patcher.start()


def pytest_unconfigure(config):
    """Restore original environment after all tests complete."""
    _env_patcher.stop()
