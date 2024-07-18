import re
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

VIDEOS_DIR = Path(__file__).parent / "videos"

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/videos", StaticFiles(directory="videos"), name="videos")

templates = Jinja2Templates(directory="templates")


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


def _load_videos() -> list[Video]:
    return sorted(
        (Video.from_path(p) for p in VIDEOS_DIR.glob("*.mp4")),
        key=lambda v: v.timestamp,
        reverse=True,
    )


@app.get("/")
async def home(request: Request) -> HTMLResponse:
    model = VideosListViewModel(videos=_load_videos())
    return templates.TemplateResponse(request=request, name="home.html", context=model.dict())


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}
