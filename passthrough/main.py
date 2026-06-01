from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from passthrough.adapters.cloudflare import CloudflareAdapter
from passthrough.api import create_router
from passthrough.drivers.camoufox import CamoufoxDriver
from passthrough.extractors.facebook import FacebookMarketplaceExtractor
from passthrough.pipeline import Pipeline


def create_app() -> FastAPI:
    """Composition root: wire up driver, adapters, extractors, pipeline, and routes."""
    driver = CamoufoxDriver(headless=True)
    pipeline = Pipeline(
        driver=driver,
        adapters=[CloudflareAdapter()],
        extractors=[FacebookMarketplaceExtractor()],
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Start the browser on boot, shut it down on exit."""
        await driver.start()
        yield
        await driver.stop()

    app = FastAPI(title="Passthrough", lifespan=lifespan)
    app.include_router(create_router(pipeline))
    return app


app = create_app()


def main():
    """Entry point for `python -m passthrough` or the pyproject script."""
    uvicorn.run("passthrough.main:app", host="0.0.0.0", port=8191, reload=True)


if __name__ == "__main__":
    main()
