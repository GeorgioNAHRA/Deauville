import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from deauville.errors import StorageError


def performance_body(**changes):
    body = {
        "kind": "solo",
        "title": "Extra Show",
        "venue": "grand-casino",
        "start": "2027-06-10T10:00",
        "duration_minutes": 60,
        "artist": "nora-lebrun",
        "min_age": 0,
    }
    body.update(changes)
    return body


def test_read_routes_and_static_files(client):
    info = client.get("/api/festival").json()
    assert info["days"] == ["2027-06-10", "2027-06-11", "2027-06-12", "2027-06-13"]
    assert len(client.get("/api/venues").json()) == 4
    assert len(client.get("/api/artists").json()) == 12
    artist = client.get("/api/artists/nora-lebrun").json()
    assert len(artist["performances"]) == 4
    programme = client.get("/api/programme?day=2027-06-11&venue=le-kiosque").json()
    assert programme[-1]["id"] == "le-kiosque-2027-06-12-0100"
    assert len(programme) == 3
    show = client.get("/api/performances/" + programme[-1]["id"]).json()
    assert show["artists"][0]["slug"] == "tom-vasseur"
    assert show["capacity"] == 120
    result = client.get("/api/now?at=2027-06-12T01:00").json()
    assert result["now_playing"][0]["title"] == "After Hours"
    assert len(result["up_next"]) == 3
    assert client.get("/api/now").status_code == 200
    for path in [
        "/",
        "/app.js",
        "/style.css",
        "/artist.html",
        "/admin/",
        "/admin/admin.js",
        "/admin/admin.css",
        "/docs",
        "/openapi.json",
    ]:
        assert client.get(path).status_code == 200


def test_artist_creation_and_duplicate(client, data_path):
    response = client.post("/api/artists", json={"name": "  New Artist  "})
    assert response.status_code == 201
    assert response.json()["name"] == "New Artist"
    assert client.get("/api/artists/new-artist").status_code == 200
    assert any(
        a["name"] == "New Artist" for a in json.loads(data_path.read_text())["artists"]
    )
    assert client.post("/api/artists", json={"name": "New Artist!"}).status_code == 409


def test_create_move_delete(client, data_path):
    response = client.post("/api/performances", json=performance_body())
    assert response.status_code == 201
    old_id = response.json()["id"]
    response = client.put(
        "/api/performances/" + old_id,
        json=performance_body(venue="le-kiosque", start="2027-06-10T12:00"),
    )
    assert response.status_code == 200
    new_id = response.json()["id"]
    assert new_id != old_id
    assert client.get("/api/performances/" + old_id).status_code == 404
    assert client.get("/api/performances/" + new_id).status_code == 200
    response = client.delete("/api/performances/" + new_id)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/api/performances/" + new_id).status_code == 404
    assert len(json.loads(data_path.read_text())["performances"]) == 23


def test_failed_move_preserves_disk_and_programme(client, data_path):
    original = data_path.read_bytes()
    before = client.get("/api/programme").json()
    response = client.put(
        "/api/performances/le-kiosque-2027-06-12-0100",
        json=performance_body(venue="le-kiosque", start="2027-06-11T23:45"),
    )
    assert response.status_code == 409
    assert "busy" in response.json()["detail"]
    assert client.get("/api/programme").json() == before
    assert data_path.read_bytes() == original


def test_register_and_persistence(client, data_path):
    path = "/api/performances/la-cabane-2027-06-13-1030/participants"
    response = client.post(path, json={"name": "  Camille R.  "})
    assert response.status_code == 201
    assert response.json()["places_left"] == 11
    assert client.post(path, json={"name": "camille r."}).status_code == 409
    assert any(
        p.get("participants") == ["Camille R."]
        for p in json.loads(data_path.read_text())["performances"]
    )
    assert (
        client.post(
            "/api/performances/le-kiosque-2027-06-13-1500/participants",
            json={"name": "A"},
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/artists/missing",
        "/api/performances/missing",
        "/api/programme?venue=missing",
    ],
)
def test_missing_objects(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


@pytest.mark.parametrize(
    "path",
    [
        "/api/programme?day=June%2011",
        "/api/programme?day=2027-02-30",
        "/api/now?at=tomorrow",
        "/api/now?at=2027-02-30T10:00",
        "/api/now?at=2027-06-11T10:00Z",
    ],
)
def test_bad_queries(client, path):
    response = client.get(path)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize("body", [{}, {"name": 3}, {"name": "A", "extra": "B"}, []])
def test_bad_body_shape(client, body):
    response = client.post("/api/artists", json=body)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"duration_minutes": 0}, 422),
        ({"title": " "}, 422),
        ({"artist": "missing"}, 404),
        ({"venue": "missing"}, 404),
        ({"start": "2027-06-15T12:00"}, 409),
    ],
)
def test_domain_errors(client, changes, status):
    response = client.post("/api/performances", json=performance_body(**changes))
    assert response.status_code == status
    assert isinstance(response.json()["detail"], str)


def test_storage_errors(client, data_path, monkeypatch):
    original = data_path.read_bytes()

    def fail_save(festival):
        raise StorageError("Cannot save festival data.")

    monkeypatch.setattr(client.app.state.service.storage, "save", fail_save)
    response = client.post("/api/artists", json={"name": "Unsaved Artist"})
    assert response.status_code == 500
    assert data_path.read_bytes() == original
    assert client.get("/api/artists/unsaved-artist").status_code == 404
    data_path.write_text("broken")
    assert client.get("/api/festival").status_code == 500


def test_concurrent_registration_does_not_lose_names(client):
    path = "/api/performances/la-cabane-2027-06-13-1030/participants"

    def register(number):
        return client.post(path, json={"name": f"Participant {number}"}).status_code

    with ThreadPoolExecutor(max_workers=4) as executor:
        statuses = list(executor.map(register, range(14)))
    assert statuses.count(201) == 12
    assert statuses.count(409) == 2
    workshop = client.get("/api/performances/la-cabane-2027-06-13-1030").json()
    assert len(workshop["participants"]) == 12
    assert workshop["places_left"] == 0
