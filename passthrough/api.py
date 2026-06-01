from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from passthrough.errors import PassthroughError
from passthrough.pipeline import Pipeline


router = APIRouter()


class RequestBody(BaseModel):
    """Inbound request: which URL to fetch and with what HTTP method."""
    url: str
    method: str = Field(default="GET")


class CookieResponse(BaseModel):
    """Single cookie from the target site's response."""
    name: str
    value: str
    domain: str
    path: str
    expires: float | None
    httpOnly: bool
    secure: bool


class SuccessResponse(BaseModel):
    """Full response from the target site after challenge resolution."""
    status: int
    headers: dict[str, str]
    cookies: list[CookieResponse]
    body: str


class ErrorResponse(BaseModel):
    """Structured error returned when the pipeline fails."""
    error: str
    message: str


def create_router(pipeline: Pipeline) -> APIRouter:
    """Build the router with the pipeline wired in.

    Why a factory: the router needs a pipeline instance, and that
    instance is created in main.py (the composition root). This
    avoids module-level singletons.
    """

    @router.post("/request", response_model=SuccessResponse)
    async def handle_request(body: RequestBody):
        """Run the URL through the pipeline and return the result or a structured error."""
        try:
            result = await pipeline.process(body.url, body.method)
        except PassthroughError as exc:
            return JSONResponse(
                status_code=400 if exc.code == "invalid_request" else 502,
                content={"error": exc.code, "message": exc.message},
            )

        return SuccessResponse(
            status=result.status,
            headers=result.headers,
            cookies=[CookieResponse(**c) for c in result.cookies],
            body=result.body,
        )

    @router.post("/restart")
    async def restart():
        """Panic button: nuke the browser and relaunch a fresh identity.

        Use when the session gets flagged or the tab wedges - rotates the
        browser fingerprint and empties the cookie jar. The egress IP is
        unchanged.
        """
        await pipeline.restart()
        return {"status": "restarted"}

    return router
