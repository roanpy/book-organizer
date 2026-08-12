import os
import sys

from book_organizer.logger import get_log_dir


def test_frozen_log_dir_is_outside_app_bundle(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    log_dir = get_log_dir()

    assert log_dir == os.path.expanduser("~/.book_organizer/logs")
