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


class ExtractResponse(BaseModel):
    """Response from the /request/{extractor} route.

    On success: status/headers/cookies plus `extracted` structured data; the
    raw body is omitted (the point of an extractor is to not ship the blob).
    On extraction failure: `extract_error` plus the raw `body` as a fallback.
    """
    status: int
    headers: dict[str, str]
    cookies: list[CookieResponse]
    extracted: dict | None = None
    extract_error: str | None = None
    body: str | None = None


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

    def _error(exc: PassthroughError) -> JSONResponse:
        """Translate a pipeline error into an HTTP response.

        Client mistakes (bad URL, unknown extractor) are 400; everything else
        is an upstream/processing failure -> 502.
        """
        client_errors = {"invalid_request", "unknown_extractor"}
        return JSONResponse(
            status_code=400 if exc.code in client_errors else 502,
            content={"error": exc.code, "message": exc.message},
        )

    @router.post("/request", response_model=SuccessResponse)
    async def handle_request(body: RequestBody):
        """Run the URL through the pipeline and return the raw result or an error."""
        try:
            result = await pipeline.process(body.url, body.method)
        except PassthroughError as exc:
            return _error(exc)

        content = result.content
        return SuccessResponse(
            status=content.status,
            headers=content.headers,
            cookies=[CookieResponse(**c) for c in content.cookies],
            body=content.body,
        )

    @router.post("/request/{extractor}", response_model=ExtractResponse)
    async def handle_request_extracted(extractor: str, body: RequestBody):
        """Run the URL through the pipeline, then through the named extractor.

        Returns the structured `extracted` data; the raw body is omitted unless
        extraction failed, in which case it's included as a fallback.
        """
        try:
            result = await pipeline.process(body.url, body.method, extractor=extractor)
        except PassthroughError as exc:
            return _error(exc)

        content = result.content
        return ExtractResponse(
            status=content.status,
            headers=content.headers,
            cookies=[CookieResponse(**c) for c in content.cookies],
            extracted=result.extracted,
            extract_error=result.extract_error,
            # Only ship the raw body when extraction failed (fallback).
            body=content.body if result.extract_error else None,
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
