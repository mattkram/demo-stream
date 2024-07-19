import functools
import re
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any

import jinja_partials
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

templates = Jinja2Templates("tests/test_templates")

VIDEOS_DIR = Path(__file__).parent / "videos"
REQUEST_CTX_KEY = "request_id"

_request_ctx_var: ContextVar[Request] = ContextVar(REQUEST_CTX_KEY, default=None)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/videos", StaticFiles(directory="videos"), name="videos")

templates = Jinja2Templates(directory="templates")
jinja_partials.register_starlette_extensions(templates)


def get_request() -> Request:
    return _request_ctx_var.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _request_ctx_var.set(request)

        response = await call_next(request)

        _request_ctx_var.reset(request_id)

        return response


app.add_middleware(RequestContextMiddleware)


class Video(BaseModel):
    timestamp: datetime
    title: str
    uri: str

    @classmethod
    def from_path(cls, path: Path) -> "Video":
        filename = path.name
        if m := re.match(
            r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})",
            filename,
        ):
            year = int(m.group("year"))
            month = int(m.group("month"))
            day = int(m.group("day"))
            timestamp = datetime(year, month, day)
        else:
            raise ValueError(f"Could not match string {filename}")

        return Video(
            uri=f"/videos/{path.name}",
            timestamp=timestamp,
            title=(str(path.name)[11:].replace(".mp4", "").replace("-", " ").title()),
        )


class VideosListViewModel(BaseModel):
    videos: list[Video]


def _load_videos(order: str) -> list[Video]:
    return sorted(
        (Video.from_path(p) for p in VIDEOS_DIR.glob("*.mp4")),
        key=lambda v: v.timestamp,
        reverse=(order == "desc"),
    )


def render_template(name, model):
    return templates.TemplateResponse(request=get_request(), name=name, context=model.dict())


def template(name: str) -> Any:
    """A decorator to convert a view model object into an HTML response, via Jinja2 template."""

    def decorator(f):
        @functools.wraps(f)
        async def inner(*args: Any, **kwargs: Any):
            model = await f(*args, **kwargs)
            return render_template(name, model)

        return inner

    return decorator


@app.get("/")
async def home(order: str = "desc") -> HTMLResponse:
    model = VideosListViewModel(videos=_load_videos(order=order))
    return render_template("home.html", model=model)


@app.get("/home")
@template("home.html")
async def home2(order: str = "desc") -> VideosListViewModel:
    return VideosListViewModel(videos=_load_videos(order=order))


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}
