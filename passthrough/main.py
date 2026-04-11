from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from playwright.async_api import Page

from passthrough.api import create_router
from passthrough.drivers.base import Driver, PageContent
from passthrough.pipeline import Pipeline


class StubDriver(Driver):
    """Returns canned responses. Exists so the full loop works without a real browser.

    Swap for CamoufoxDriver in slice 2.
    """

    async def start(self) -> None:
        pass

    async def new_page(self) -> Page:
        # Pipeline expects a Page, but we never touch it in the stub.
        # None works here because the stub's goto/capture don't use it.
        return None  # type: ignore

    async def goto(self, page: Page, url: str) -> None:
        pass

    async def capture(self, page: Page) -> PageContent:
        return PageContent(
            status=200,
            headers={"content-type": "text/html"},
            cookies=[],
            body="<html><body>stub response</body></html>",
        )

    async def close_page(self, page: Page) -> None:
        pass

    async def stop(self) -> None:
        pass


def create_app() -> FastAPI:
    driver = StubDriver()
    pipeline = Pipeline(driver=driver, adapters=[])

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await driver.start()
        yield
        await driver.stop()

    app = FastAPI(title="Passthrough", lifespan=lifespan)
    app.include_router(create_router(pipeline))
    return app


app = create_app()


def main():
    uvicorn.run("passthrough.main:app", host="0.0.0.0", port=8191, reload=True)


if __name__ == "__main__":
    main()
