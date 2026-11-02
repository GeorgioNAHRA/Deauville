import shutil

import pytest
from fastapi.testclient import TestClient

from deauville.api import create_app
from deauville.festival import Festival
from deauville.storage import DEFAULT_DATA


@pytest.fixture
def festival():
    result = Festival("Test Festival", "2027-06-10", "2027-06-13")
    result.add_venue("First Hall", 2, "First Street")
    result.add_venue("Second Hall", 100, "Second Street")
    for name in ["Alice", "Bob", "Chloé", "David"]:
        result.add_artist(name)
    return result


@pytest.fixture
def solo():
    return {
        "kind": "solo",
        "title": "First Show",
        "venue": "first-hall",
        "start": "2027-06-11T20:00",
        "duration_minutes": 60,
        "artist": "alice",
    }


@pytest.fixture
def data_path(tmp_path):
    path = tmp_path / "festival.json"
    shutil.copyfile(DEFAULT_DATA, path)
    return path


@pytest.fixture
def client(data_path):
    with TestClient(create_app(data_path)) as result:
        yield result
