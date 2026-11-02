from datetime import datetime, timedelta

from deauville.errors import ConflictError, InvalidValueError, NotFoundError
from deauville.models import Artist, Venue, Workshop, create_performance
from deauville.validation import day, moment, text


class Festival:
    def __init__(self, name: str, first_day: str, last_day: str):
        self._name = text(name, "Festival name", True)
        self._first_day = day(first_day)
        self._last_day = day(last_day)
        if self._last_day < self._first_day:
            raise InvalidValueError("The last day cannot be before the first day.")
        self._venues = {}
        self._artists = {}
        self._performances = {}

    def information(self) -> dict:
        days = []
        count = (self._last_day - self._first_day).days + 1
        for offset in range(count):
            days.append((self._first_day + timedelta(days=offset)).isoformat())
        return {
            "name": self._name,
            "first_day": self._first_day.isoformat(),
            "last_day": self._last_day.isoformat(),
            "days": days,
        }

    def add_artist(self, name: str, bio: str = "", photo_url: str = "") -> dict:
        artist = Artist(name, bio, photo_url)
        if artist.slug in self._artists:
            raise ConflictError(f"{artist.name} already exists as an artist.")
        self._artists[artist.slug] = artist
        return artist.to_dict()

    def add_venue(self, name: str, capacity: int, address: str) -> dict:
        venue = Venue(name, capacity, address)
        if venue.slug in self._venues:
            raise ConflictError(f"{venue.name} already exists as a venue.")
        self._venues[venue.slug] = venue
        return venue.to_dict()

    def artists(self) -> list[dict]:
        return [self._artists[key].to_dict() for key in sorted(self._artists)]

    def venues(self) -> list[dict]:
        return [venue.to_dict() for venue in self._venues.values()]

    def artist(self, slug: str) -> dict:
        if slug not in self._artists:
            raise NotFoundError(f"Artist '{slug}' was not found.")
        data = self._artists[slug].to_dict()
        data["performances"] = []
        for performance in self._ordered():
            if slug in performance.artist_slugs():
                data["performances"].append(self._view(performance))
        return data

    def _find(self, performance_id: str):
        if performance_id not in self._performances:
            raise NotFoundError(f"Performance '{performance_id}' was not found.")
        return self._performances[performance_id]

    def performance(self, performance_id: str) -> dict:
        return self._view(self._find(performance_id))

    def _ordered(self) -> list:
        return sorted(
            self._performances.values(),
            key=lambda show: (show.start, self._venues[show.venue].name),
        )

    def _view(self, performance) -> dict:
        venue = self._venues[performance.venue]
        data = performance.to_dict()
        data.update(
            id=performance.id,
            venue_name=venue.name,
            end=performance.end.isoformat(timespec="minutes"),
            festival_day=performance.festival_day.isoformat(),
            summary=performance.summary(self._artists),
            capacity=performance.capacity(venue),
            artists=[],
        )
        for slug in performance.artist_slugs():
            data["artists"].append({"slug": slug, "name": self._artists[slug].name})
        if isinstance(performance, Workshop):
            data["places_left"] = data["capacity"] - len(performance.participants)
        return data

    def programme(
        self, on_day: str | None = None, venue: str | None = None
    ) -> list[dict]:
        selected_day = day(on_day) if on_day is not None else None
        if venue is not None and venue not in self._venues:
            raise NotFoundError(f"Venue '{venue}' was not found.")
        result = []
        for performance in self._ordered():
            if selected_day is not None and performance.festival_day != selected_day:
                continue
            if venue is not None and performance.venue != venue:
                continue
            result.append(self._view(performance))
        return result

    def now(self, at: str | None = None) -> dict:
        if at is None:
            at = datetime.now().isoformat(timespec="minutes")
        current = moment(at)
        playing = []
        upcoming = []
        for performance in self._ordered():
            if performance.start <= current < performance.end:
                playing.append(self._view(performance))
            elif performance.start > current and len(upcoming) < 3:
                upcoming.append(self._view(performance))
        return {"at": at, "now_playing": playing, "up_next": upcoming}

    def _validate(self, performance, replaced_id: str | None = None) -> None:
        if performance.venue not in self._venues:
            raise NotFoundError(f"Venue '{performance.venue}' was not found.")
        for slug in performance.artist_slugs():
            if slug not in self._artists:
                raise NotFoundError(f"Artist '{slug}' was not found.")
        if not self._first_day <= performance.festival_day <= self._last_day:
            raise ConflictError("The performance must belong to a festival day.")
        venue = self._venues[performance.venue]
        if isinstance(performance, Workshop) and len(
            performance.participants
        ) > performance.capacity(venue):
            raise ConflictError(
                f"{performance.title} has more participants than places."
            )
        gap = timedelta(minutes=30)
        for existing in self._performances.values():
            if existing.id == replaced_id:
                continue
            if performance.start >= existing.end + gap:
                continue
            if existing.start >= performance.end + gap:
                continue
            busy = None
            if performance.venue == existing.venue:
                busy = venue.name
            else:
                for slug in performance.artist_slugs():
                    if slug in existing.artist_slugs():
                        busy = self._artists[slug].name
                        break
            if busy is not None:
                raise ConflictError(
                    f"{busy} is busy with {existing.title} "
                    f"({existing.start:%Y-%m-%d %H:%M}-{existing.end:%H:%M}). "
                    "Leave 30 minutes between two shows."
                )

    def add_performance(self, data: dict) -> dict:
        performance = create_performance(data)
        self._validate(performance)
        self._performances[performance.id] = performance
        return self._view(performance)

    def update_performance(self, performance_id: str, data: dict) -> dict:
        self._find(performance_id)
        performance = create_performance(data)
        self._validate(performance, performance_id)
        del self._performances[performance_id]
        self._performances[performance.id] = performance
        return self._view(performance)

    def cancel_performance(self, performance_id: str) -> None:
        self._find(performance_id)
        del self._performances[performance_id]

    def register(self, performance_id: str, name: str) -> dict:
        performance = self._find(performance_id)
        if not isinstance(performance, Workshop):
            raise InvalidValueError("Participants can only register for a workshop.")
        name = text(name, "Participant name", True)
        for participant in performance.participants:
            if participant.casefold() == name.casefold():
                raise ConflictError(f"{name} is already registered.")
        venue = self._venues[performance.venue]
        if len(performance.participants) >= performance.capacity(venue):
            raise ConflictError(f"{performance.title} is full.")
        performance.participants.append(name)
        return self._view(performance)

    def to_dict(self) -> dict:
        return {
            "name": self._name,
            "first_day": self._first_day.isoformat(),
            "last_day": self._last_day.isoformat(),
            "venues": [
                {"name": item.name, "capacity": item.capacity, "address": item.address}
                for item in self._venues.values()
            ],
            "artists": [
                {
                    "name": item["name"],
                    "bio": item["bio"],
                    "photo_url": item["photo_url"],
                }
                for item in self.artists()
            ],
            "performances": [item.to_dict() for item in self._ordered()],
        }

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise InvalidValueError("Festival data must be an object.")
        try:
            festival = cls(data["name"], data["first_day"], data["last_day"])
            for field in ("venues", "artists", "performances"):
                if not isinstance(data[field], list):
                    raise InvalidValueError(f"{field.capitalize()} must be a list.")
            for venue in data["venues"]:
                festival.add_venue(**venue)
            for artist in data["artists"]:
                festival.add_artist(**artist)
            for performance in data["performances"]:
                festival.add_performance(performance)
        except (KeyError, TypeError):
            raise InvalidValueError(
                "Festival data has missing fields or an invalid object structure."
            ) from None
        return festival
