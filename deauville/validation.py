import re
import unicodedata
from datetime import date, datetime

from deauville.errors import InvalidValueError


def text(value: str, label: str, required: bool = False) -> str:
    if not isinstance(value, str):
        raise InvalidValueError(f"{label} must be text.")
    value = value.strip()
    if required and not value:
        raise InvalidValueError(f"{label} cannot be empty.")
    return value


def slug(name: str) -> str:
    name = text(name, "Name", True)
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii").lower()
    result = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    if not result:
        raise InvalidValueError("The name must contain an ASCII letter or digit.")
    return result


def integer(value: int, label: str, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int:
        raise InvalidValueError(f"{label} must be a whole number.")
    if value < minimum or (maximum is not None and value > maximum):
        if maximum is None:
            raise InvalidValueError(f"{label} must be at least {minimum}.")
        raise InvalidValueError(f"{label} must be between {minimum} and {maximum}.")
    return value


def day(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise InvalidValueError("Use YYYY-MM-DD for a festival day.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidValueError("Enter a valid calendar date.") from None


def moment(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value
    ):
        raise InvalidValueError(
            "Use YYYY-MM-DDTHH:MM in local time, without a time zone."
        )
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise InvalidValueError("Enter a valid date and time.") from None


def names(value: list, label: str) -> list[str]:
    if not isinstance(value, list):
        raise InvalidValueError(f"{label} must be a list.")
    result = []
    for name in value:
        result.append(text(name, label, True))
    return result
