import os
import pytest

from compiler import QUEST_AVAILABLE

if not QUEST_AVAILABLE:
    pytest.skip(
        "integration tests require QUEST_ROOT — skipping in CI",
        allow_module_level=True,
    )
