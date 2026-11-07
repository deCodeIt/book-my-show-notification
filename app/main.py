import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bms_api import BookMyShowApi
from http_client import CurlCffiHttpClient

from .api import build_router
from .auth import TokenAuthMiddleware
from .bms_service import BmsService
from .config import Settings
from .db import Database
from .notify import PushbulletSender
from .poller import Poller

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(settings: Settings = None, api=None, notifier=None) -> FastAPI:
    settings = settings or Settings.from_env()

    db = Database(settings.database_path)
    db.init()

    api = api or BookMyShowApi(CurlCffiHttpClient())
    bms = BmsService(api)
    notifier = notifier or PushbulletSender(db, settings.env_pushbullet_token)
    poller = Poller(db, api, settings, notifier)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        poller.start()
        try:
            yield
        finally:
            await poller.stop()

    app = FastAPI(title="BookMyShow Watcher", lifespan=lifespan)
    app.state.db = db
    app.state.bms = bms
    app.state.poller = poller
    app.state.notifier = notifier
    app.state.settings = settings

    app.add_middleware(TokenAuthMiddleware, app_token=settings.app_token)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/login")
    def login_page():
        return FileResponse(STATIC_DIR / "login.html")

    app.include_router(build_router(db, bms, poller, notifier, settings))
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    return app
