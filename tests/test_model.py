import pytest

from deauville.errors import ConflictError, InvalidValueError, NotFoundError
from deauville.festival import Festival
from deauville.models import Artist, Venue, create_performance
from deauville.storage import JsonStorage


def workshop(solo, **changes):
    data = dict(solo)
    data.pop("artist")
    data.update(kind="workshop", teacher="alice", max_participants=3)
    data.update(changes)
    return data


def lineup(solo, **changes):
    data = dict(solo)
    data.pop("artist")
    data.update(kind="lineup", host="alice", acts=["bob", "chloe"])
    data.update(changes)
    return data


def test_original_data():
    festival = JsonStorage().load()
    assert len(festival.programme()) == 23
    assert len(festival.artists()) == 12
    assert len(festival.venues()) == 4
    assert len(festival.programme("2027-06-11")) == 7
    assert festival.artists()[0]["slug"] == "elodie-marchal"


def test_names_and_slug(festival):
    artist = festival.add_artist("  Élodie  Marchal !  ")
    assert artist["slug"] == "elodie-marchal"
    assert artist["name"] == "Élodie  Marchal !"
    assert Venue("Théâtre des Planches", 1, "Street").slug == "theatre-des-planches"
    with pytest.raises(ConflictError):
        festival.add_artist("Elodie Marchal")
    with pytest.raises(ConflictError):
        festival.add_venue("First Hall!", 5, "Street")
    assert [item["slug"] for item in festival.artists()] == sorted(
        item["slug"] for item in festival.artists()
    )
    assert [item["slug"] for item in festival.venues()] == ["first-hall", "second-hall"]


@pytest.mark.parametrize("name", ["", "  ", "!!!", None, 3])
def test_invalid_artist(name):
    with pytest.raises(InvalidValueError):
        Artist(name)


@pytest.mark.parametrize("capacity", [0, -1, 1.5, True, "10"])
def test_invalid_venue_capacity(capacity):
    with pytest.raises(InvalidValueError):
        Venue("Hall", capacity, "Street")


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "  "),
        ("duration_minutes", 0),
        ("duration_minutes", 361),
        ("duration_minutes", True),
        ("duration_minutes", 2.5),
        ("min_age", -1),
        ("min_age", 19),
        ("start", "2027-02-30T20:00"),
        ("start", "2027-06-11T20:00+02:00"),
        ("start", "2027-06-11T20:00:30"),
        ("kind", "other"),
    ],
)
def test_invalid_performance(festival, solo, field, value):
    solo[field] = value
    with pytest.raises(InvalidValueError):
        festival.add_performance(solo)
    assert festival.programme() == []


@pytest.mark.parametrize(
    "start,expected",
    [
        ("2027-06-12T00:30", "2027-06-11"),
        ("2027-06-12T05:59", "2027-06-11"),
        ("2027-06-12T06:00", "2027-06-12"),
        ("2027-06-14T05:59", "2027-06-13"),
    ],
)
def test_festival_day(festival, solo, start, expected):
    solo["start"] = start
    show = festival.add_performance(solo)
    assert show["festival_day"] == expected
    assert festival.programme(expected)[0]["id"] == show["id"]


@pytest.mark.parametrize("start", ["2027-06-10T05:59", "2027-06-14T06:00"])
def test_outside_festival(festival, solo, start):
    solo["start"] = start
    with pytest.raises(ConflictError):
        festival.add_performance(solo)


@pytest.mark.parametrize(
    "start", ["2027-06-11T18:31", "2027-06-11T20:15", "2027-06-11T21:29"]
)
@pytest.mark.parametrize("same_venue", [True, False])
def test_conflicts_in_both_directions(festival, solo, start, same_venue):
    festival.add_performance(solo)
    other = dict(solo, start=start)
    if same_venue:
        other["artist"] = "bob"
    else:
        other["venue"] = "second-hall"
    with pytest.raises(ConflictError, match="Leave 30 minutes"):
        festival.add_performance(other)
    assert len(festival.programme()) == 1


@pytest.mark.parametrize("start", ["2027-06-11T18:30", "2027-06-11T21:30"])
def test_exact_break_allowed(festival, solo, start):
    festival.add_performance(solo)
    festival.add_performance(dict(solo, start=start))
    assert len(festival.programme()) == 2


@pytest.mark.parametrize("artist", ["alice", "bob", "chloe"])
def test_lineup_roles_block_other_venues(festival, solo, artist):
    festival.add_performance(lineup(solo))
    with pytest.raises(ConflictError):
        festival.add_performance(dict(solo, venue="second-hall", artist=artist))


def test_teacher_blocks_other_venue(festival, solo):
    festival.add_performance(workshop(solo))
    with pytest.raises(ConflictError):
        festival.add_performance(dict(solo, venue="second-hall"))


@pytest.mark.parametrize(
    "changes",
    [
        {"acts": ["bob"]},
        {"acts": ["bob", "bob"]},
        {"acts": ["alice", "bob"]},
        {"acts": ["bob", "chloe", "david"], "duration_minutes": 35},
        {"acts": "bob"},
    ],
)
def test_lineup_rules(festival, solo, changes):
    with pytest.raises(InvalidValueError):
        festival.add_performance(lineup(solo, **changes))


def test_lineup_minimum(festival, solo):
    show = festival.add_performance(
        lineup(solo, acts=["bob", "chloe", "david"], duration_minutes=36)
    )
    assert [artist["slug"] for artist in show["artists"]] == [
        "alice",
        "bob",
        "chloe",
        "david",
    ]


def test_registration(festival, solo):
    show = festival.add_performance(workshop(solo))
    assert show["capacity"] == 2
    festival.register(show["id"], "  Camille R.  ")
    with pytest.raises(ConflictError, match="already registered"):
        festival.register(show["id"], "camille r.")
    with pytest.raises(InvalidValueError):
        festival.register(show["id"], " ")
    result = festival.register(show["id"], "Bob")
    assert result["participants"] == ["Camille R.", "Bob"]
    assert result["places_left"] == 0
    with pytest.raises(ConflictError, match="full"):
        festival.register(show["id"], "David")


@pytest.mark.parametrize("participants", [["A", "a"], ["A", "B", "C"], [" "]])
def test_invalid_initial_participants(festival, solo, participants):
    with pytest.raises((ConflictError, InvalidValueError)):
        festival.add_performance(workshop(solo, participants=participants))


def test_workshop_limit_and_non_workshop(festival, solo):
    show = festival.add_performance(workshop(solo, max_participants=1))
    assert show["capacity"] == 1
    festival.cancel_performance(show["id"])
    show = festival.add_performance(solo)
    with pytest.raises(InvalidValueError, match="workshop"):
        festival.register(show["id"], "A")
    with pytest.raises(InvalidValueError):
        create_performance(workshop(solo, max_participants=0))


def test_atomic_update_and_new_id(festival, solo):
    original = festival.add_performance(solo)
    festival.add_performance(dict(solo, start="2027-06-11T22:00"))
    before = festival.to_dict()
    with pytest.raises(ConflictError):
        festival.update_performance(
            original["id"], dict(solo, start="2027-06-11T21:15")
        )
    assert festival.to_dict() == before
    moved = festival.update_performance(
        original["id"], dict(solo, start="2027-06-11T18:00")
    )
    assert moved["id"] == "first-hall-2027-06-11-1800"
    with pytest.raises(NotFoundError):
        festival.performance(original["id"])
    festival.cancel_performance(moved["id"])
    assert len(festival.programme()) == 1


def test_public_data_cannot_bypass_rules(festival, solo):
    show = festival.add_performance(workshop(solo, participants=["A"]))
    show["participants"].append("B")
    festival.programme()[0]["title"] = "Changed"
    festival.to_dict()["performances"][0]["participants"].clear()
    festival.artists()[0]["name"] = "Changed"
    assert festival.performance(show["id"])["participants"] == ["A"]
    assert festival.performance(show["id"])["title"] == "First Show"
    assert festival.artists()[0]["name"] == "Alice"


def test_order_filters_and_now(festival, solo):
    first = festival.add_performance(dict(solo, venue="second-hall"))
    second = festival.add_performance(dict(solo, artist="bob"))
    for hour in [22, 23]:
        festival.add_performance(
            dict(solo, start=f"2027-06-12T{hour}:00", duration_minutes=20)
        )
    festival.add_performance(dict(solo, start="2027-06-13T10:00"))
    festival.add_performance(dict(solo, start="2027-06-13T12:00"))
    assert [p["id"] for p in festival.programme()[:2]] == [second["id"], first["id"]]
    assert len(festival.programme(venue="second-hall")) == 1
    assert len(festival.now("2027-06-11T20:00")["now_playing"]) == 2
    result = festival.now("2027-06-11T21:00")
    assert result["now_playing"] == []
    assert len(result["up_next"]) == 3


@pytest.mark.parametrize("field", ["venue", "artist"])
def test_unknown_reference(festival, solo, field):
    solo[field] = "missing"
    with pytest.raises(NotFoundError):
        festival.add_performance(solo)


def test_dates_and_unknown_objects(festival):
    with pytest.raises(InvalidValueError):
        Festival("Festival", "2027-06-13", "2027-06-10")
    for operation in [
        festival.artist,
        festival.performance,
        festival.cancel_performance,
    ]:
        with pytest.raises(NotFoundError):
            operation("missing")
