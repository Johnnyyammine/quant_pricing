"""FastAPI application factory. Serves ``/api`` and, when built, the web SPA."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api import __version__
from api.routes import router
from engine.errors import PricingError

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def create_app(web_dist: Path | None = WEB_DIST) -> FastAPI:
    """Build the app. If ``web_dist`` contains a build, serve it at ``/`` with SPA fallback."""
    app = FastAPI(title="Quant Pricer API", version=__version__)
    app.add_middleware(
        CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["*"], allow_headers=["*"]
    )

    # Engine domain errors (bad market data, unsupported combinations, invalid instruments) are
    # client errors: the request was well-formed but not priceable.
    @app.exception_handler(PricingError)
    @app.exception_handler(ValueError)
    async def _unprocessable(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.include_router(router)

    if web_dist is not None and (web_dist / "index.html").is_file():
        index = web_dist / "index.html"
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = (web_dist / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(web_dist.resolve()):
                return FileResponse(candidate)
            return FileResponse(index)

    return app
