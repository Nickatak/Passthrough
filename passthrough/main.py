from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from passthrough.api import create_router
from passthrough.drivers.camoufox import CamoufoxDriver
from passthrough.pipeline import Pipeline


def create_app() -> FastAPI:
    driver = CamoufoxDriver(headless=True)
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
