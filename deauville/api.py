from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from deauville.errors import (
    ConflictError,
    FestivalError,
    InvalidValueError,
    NotFoundError,
    StorageError,
)
from deauville.service import FestivalService
from deauville.storage import DEFAULT_DATA, ROOT, JsonStorage
from deauville.validation import moment


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ArtistInput(InputModel):
    name: str
    bio: str = ""
    photo_url: str = ""


class PerformanceInput(InputModel):
    title: str
    venue: str
    start: str
    duration_minutes: int
    description: str = ""


class SoloInput(PerformanceInput):
    kind: Literal["solo"]
    artist: str
    min_age: int = 0


class LineupInput(PerformanceInput):
    kind: Literal["lineup"]
    host: str
    acts: list[str]


class WorkshopInput(PerformanceInput):
    kind: Literal["workshop"]
    teacher: str
    max_participants: int
    participants: list[str] = Field(default_factory=list)


class ParticipantInput(InputModel):
    name: str


PerformanceBody = Annotated[
    SoloInput | LineupInput | WorkshopInput, Field(discriminator="kind")
]


def valid_moment(value: str) -> str:
    try:
        moment(value)
    except InvalidValueError as error:
        raise ValueError(str(error)) from None
    return value


MomentQuery = Annotated[str, AfterValidator(valid_moment)]


def create_app(data_path: str | Path = DEFAULT_DATA) -> FastAPI:
    app = FastAPI(title="Deauville Festival API")
    service = FestivalService(JsonStorage(data_path))
    app.state.service = service

    @app.exception_handler(FestivalError)
    async def festival_error(request: Request, error: FestivalError):
        status = 422
        if isinstance(error, NotFoundError):
            status = 404
        elif isinstance(error, ConflictError):
            status = 409
        elif isinstance(error, StorageError):
            status = 500
        return JSONResponse(status_code=status, content={"detail": str(error)})

    @app.exception_handler(RequestValidationError)
    async def request_error(request: Request, error: RequestValidationError):
        problems = []
        for problem in error.errors():
            problems.append(
                {
                    "loc": list(problem["loc"]),
                    "msg": problem["msg"],
                    "type": problem["type"],
                }
            )
        return JSONResponse(status_code=422, content={"detail": problems})

    @app.get("/api/festival")
    def festival():
        return service.read("information")

    @app.get("/api/venues")
    def venues():
        return service.read("venues")

    @app.get("/api/artists")
    def artists():
        return service.read("artists")

    @app.get("/api/artists/{slug}")
    def artist(slug: str):
        return service.read("artist", slug)

    @app.get("/api/programme")
    def programme(day: date | None = None, venue: str | None = None):
        selected = day.isoformat() if day is not None else None
        return service.read("programme", selected, venue)

    @app.get("/api/performances/{performance_id}")
    def performance(performance_id: str):
        return service.read("performance", performance_id)

    @app.get("/api/now")
    def now(at: Annotated[MomentQuery | None, Query()] = None):
        return service.read("now", at)

    @app.post("/api/artists", status_code=201)
    def add_artist(body: ArtistInput):
        return service.change("add_artist", body.name, body.bio, body.photo_url)

    @app.post("/api/performances", status_code=201)
    def add_performance(body: PerformanceBody):
        return service.change("add_performance", body.model_dump())

    @app.put("/api/performances/{performance_id}")
    def update_performance(performance_id: str, body: PerformanceBody):
        return service.change("update_performance", performance_id, body.model_dump())

    @app.delete("/api/performances/{performance_id}", status_code=204)
    def cancel_performance(performance_id: str):
        service.change("cancel_performance", performance_id)
        return Response(status_code=204)

    @app.post("/api/performances/{performance_id}/participants", status_code=201)
    def register(performance_id: str, body: ParticipantInput):
        return service.change("register", performance_id, body.name)

    app.mount("/admin", StaticFiles(directory=ROOT / "web" / "admin", html=True))
    app.mount("/", StaticFiles(directory=ROOT / "web" / "public", html=True))
    return app


app = create_app()
