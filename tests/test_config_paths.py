"""DATA_ROOT is anchored to the project, so the download folder cannot fork by cwd."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from opendiscourse_research.config import PROJECT_ROOT, Settings


def test_relative_data_root_is_anchored_to_the_project_not_the_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Settings(data_root="./lake/raw", _env_file=None).data_root == str(
        PROJECT_ROOT / "lake" / "raw"
    )


def test_absolute_and_home_relative_paths_are_kept(monkeypatch):
    assert Settings(data_root="/somewhere/raw", _env_file=None).data_root == "/somewhere/raw"
    monkeypatch.setenv("HOME", "/home/someone")
    assert Settings(data_root="~/lake", _env_file=None).data_root == "/home/someone/lake"


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_data_root_is_rejected_not_the_checkout(blank):
    with pytest.raises(ValidationError, match="DATA_ROOT"):
        Settings(data_root=blank, _env_file=None)


def test_env_file_is_read_from_the_project_root_regardless_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Settings.model_config["env_file"] == PROJECT_ROOT / ".env"
