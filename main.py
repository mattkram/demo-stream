import functools
import hashlib
import json
import re
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import jinja_partials
from fastapi import FastAPI, Form, Header, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, computed_field
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


def render_template(name, model: BaseModel | None = None):
    context = {"model": model.dict(), **model.dict()} if model is not None else {}
    return templates.TemplateResponse(request=get_request(), name=name, context=context)


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
async def home() -> HTMLResponse:
    with open("templates/index.html", "rb") as fp:
        return HTMLResponse(content=fp.read(), media_type="text/html", status_code=200)


@app.get("/videos")
async def videos(
    from_htmx: Annotated[str, Header(alias="hx-request")] = "",
    order: Annotated[str, Query()] = "desc",
) -> HTMLResponse:
    model = VideosListViewModel(videos=_load_videos(order=order))
    if from_htmx:
        return render_template("partials/videos_list.html", model=model)
    return render_template("home.html", model=model)


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


try:
    with open("repodata.json") as fp:
        data = json.load(fp)
except FileNotFoundError:
    data = {}

packages = data.get("packages", [])
package_names = sorted(set(p["name"] for filename, p in packages.items()))

PAGE_SIZE = 10


class ChannelListModel(BaseModel):
    packages: list[str] = []
    page: int = 1


@app.get("/app/main")
async def main_channel(
    from_htmx: Annotated[str, Header(alias="hx-request")] = "",
    page: int = 1,
) -> ChannelListModel:
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    model = ChannelListModel(packages=package_names[start:end], page=page)
    if from_htmx:
        return render_template("partials/package_table.html", model=model)
    return render_template("channel_list.html", model=model)


@app.get("/app")
async def app_home():
    return render_template("app.html")


class AccountProfileViewModel(BaseModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""

    @computed_field
    @property
    def gravitar_url(self) -> str:
        email_hash = hashlib.md5(self.email.strip().lower().encode("utf-8")).hexdigest()
        gravitar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
        return gravitar_url


ACCOUNT_DATABASE = {}
USER_ID = "mrk"


@app.get("/app/profile/account-settings")
async def account_settings(from_htmx: Annotated[str, Header(alias="hx-request")] = ""):
    model = AccountProfileViewModel(**ACCOUNT_DATABASE.get(USER_ID, {}))
    if from_htmx:
        return render_template("partials/account-settings-form.html", model=model)
    return render_template(
        "account-settings.html",
        model=model,
    )


@app.put("/app/profile/account-settings")
async def update_account_settings(
    first_name: Annotated[str, Form()] = "",
    last_name: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
):
    ACCOUNT_DATABASE[USER_ID] = {"first_name": first_name, "last_name": last_name, "email": email}
    model = AccountProfileViewModel(**ACCOUNT_DATABASE.get(USER_ID, {}))
    return render_template("partials/account-settings-form.html", model=model)
