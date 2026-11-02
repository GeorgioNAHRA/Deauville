import json
from pathlib import Path

import pytest

from deauville.errors import StorageError
from deauville.service import FestivalService
from deauville.storage import JsonStorage


def test_round_trip(data_path):
    storage = JsonStorage(data_path)
    festival = storage.load()
    festival.add_artist("  New Artist  ")
    storage.save(festival)
    assert storage.load().to_dict() == festival.to_dict()
    saved = json.loads(data_path.read_text())
    assert "id" not in saved["performances"][0]


@pytest.mark.parametrize("content", ["{", "[]", "{}", '{"name": 5}', "null"])
def test_broken_file(tmp_path, content):
    path = tmp_path / "broken.json"
    path.write_text(content)
    with pytest.raises(StorageError, match="festival data"):
        JsonStorage(path).load()


@pytest.mark.parametrize(
    "change", ["reference", "conflict", "participants", "duration", "structure"]
)
def test_load_rechecks_rules(data_path, change):
    data = json.loads(data_path.read_text())
    if change == "reference":
        data["performances"][0]["venue"] = "missing"
    elif change == "conflict":
        data["performances"].append(data["performances"][0])
    elif change == "participants":
        data["performances"][3]["participants"] = ["A", "a"]
    elif change == "duration":
        data["performances"][0]["duration_minutes"] = 0
    else:
        data["artists"] = [None]
    data_path.write_text(json.dumps(data))
    with pytest.raises(StorageError, match="Invalid festival data"):
        JsonStorage(data_path).load()


def test_missing_file(tmp_path):
    with pytest.raises(StorageError, match="Cannot read"):
        JsonStorage(tmp_path / "missing.json").load()


def test_failed_save_keeps_original(data_path, monkeypatch):
    original = data_path.read_bytes()
    files = set(data_path.parent.iterdir())

    def fail_replace(self, target):
        raise PermissionError("Read-only folder")

    monkeypatch.setattr(Path, "replace", fail_replace)
    service = FestivalService(JsonStorage(data_path))
    with pytest.raises(StorageError, match="Cannot save"):
        service.change("add_artist", "Unsaved Artist")
    assert data_path.read_bytes() == original
    assert set(data_path.parent.iterdir()) == files
    assert all(a["slug"] != "unsaved-artist" for a in service.read("artists"))
