from abc import ABC, abstractmethod
from datetime import timedelta

from deauville.errors import ConflictError, InvalidValueError
from deauville.validation import integer, moment, names, slug, text


class Artist:
    def __init__(self, name: str, bio: str = "", photo_url: str = ""):
        self.name = text(name, "Artist name", True)
        self.slug = slug(self.name)
        self.bio = text(bio, "Biography")
        self.photo_url = text(photo_url, "Photo URL")

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "bio": self.bio,
            "photo_url": self.photo_url,
        }


class Venue:
    def __init__(self, name: str, capacity: int, address: str):
        self.name = text(name, "Venue name", True)
        self.slug = slug(self.name)
        self.capacity = integer(capacity, "Venue capacity", 1)
        self.address = text(address, "Address", True)

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }


class Performance(ABC):
    def __init__(
        self,
        title: str,
        venue: str,
        start: str,
        duration_minutes: int,
        description: str = "",
    ):
        self.title = text(title, "Performance title", True)
        self.venue = text(venue, "Venue slug", True)
        self.start = moment(start)
        self.duration_minutes = integer(duration_minutes, "Duration", 1, 360)
        self.description = text(description, "Description")
        if self.start.year < 2 or self.start.year > 9998:
            raise InvalidValueError("The start year must be between 2 and 9998.")

    @property
    def id(self) -> str:
        return f"{self.venue}-{self.start:%Y-%m-%d-%H%M}"

    @property
    def end(self):
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def festival_day(self):
        return (self.start - timedelta(hours=6)).date()

    @abstractmethod
    def artist_slugs(self) -> list[str]:
        pass

    @abstractmethod
    def summary(self, artists: dict) -> str:
        pass

    def capacity(self, venue: Venue) -> int:
        return venue.capacity

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue,
            "start": self.start.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        }


class Solo(Performance):
    kind = "solo"

    def __init__(self, artist: str, min_age: int = 0, **details):
        super().__init__(**details)
        self.artist = text(artist, "Artist slug", True)
        self.min_age = integer(min_age, "Minimum age", 0, 18)

    def artist_slugs(self) -> list[str]:
        return [self.artist]

    def summary(self, artists: dict) -> str:
        return f"Solo show by {artists[self.artist].name}"

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(artist=self.artist, min_age=self.min_age)
        return data


class Lineup(Performance):
    kind = "lineup"

    def __init__(self, host: str, acts: list[str], **details):
        super().__init__(**details)
        self.host = text(host, "Host slug", True)
        self.acts = names(acts, "Acts")
        if len(self.acts) < 2:
            raise InvalidValueError("A lineup needs at least two acts.")
        if len(set(self.acts)) != len(self.acts):
            raise InvalidValueError("Each act can appear only once in a lineup.")
        if self.host in self.acts:
            raise InvalidValueError("The host cannot also be an act.")
        minimum = len(self.acts) * 10 + (len(self.acts) - 1) * 3
        if self.duration_minutes < minimum:
            raise InvalidValueError(f"This lineup needs at least {minimum} minutes.")

    def artist_slugs(self) -> list[str]:
        return [self.host] + self.acts

    def summary(self, artists: dict) -> str:
        acts = ", ".join(artists[act].name for act in self.acts)
        return f"Hosted by {artists[self.host].name}, with {acts}"

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(host=self.host, acts=list(self.acts))
        return data


class Workshop(Performance):
    kind = "workshop"

    def __init__(
        self,
        teacher: str,
        max_participants: int,
        participants: list[str] | None = None,
        **details,
    ):
        super().__init__(**details)
        self.teacher = text(teacher, "Teacher slug", True)
        self.max_participants = integer(max_participants, "Maximum participants", 1)
        if participants is None:
            participants = []
        self.participants = names(participants, "Participant name")
        registered = set()
        for name in self.participants:
            if name.casefold() in registered:
                raise ConflictError(f"{name} is already registered.")
            registered.add(name.casefold())
        if len(self.participants) > self.max_participants:
            raise ConflictError("This workshop has too many participants.")

    def artist_slugs(self) -> list[str]:
        return [self.teacher]

    def summary(self, artists: dict) -> str:
        return f"Workshop with {artists[self.teacher].name}"

    def capacity(self, venue: Venue) -> int:
        return min(self.max_participants, venue.capacity)

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(
            teacher=self.teacher,
            max_participants=self.max_participants,
            participants=list(self.participants),
        )
        return data


def create_performance(data: dict) -> Performance:
    if not isinstance(data, dict):
        raise InvalidValueError("A performance must be an object.")
    details = dict(data)
    kind = details.pop("kind", None)
    try:
        if kind == "solo":
            return Solo(**details)
        if kind == "lineup":
            return Lineup(**details)
        if kind == "workshop":
            return Workshop(**details)
    except TypeError:
        raise InvalidValueError(
            "The performance has missing or unexpected fields for its kind."
        ) from None
    raise InvalidValueError("Choose solo, lineup or workshop as the performance kind.")
