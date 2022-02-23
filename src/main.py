import asyncio

import uvicorn
from fastapi import FastAPI, Depends
from starlette.requests import Request

from youwol_assets_gateway.configurations import get_configuration, Configuration
from youwol_assets_gateway.root_paths import router as base_router
from youwol_assets_gateway.utils import init_resources
from youwol_utils import YouWolException, log_info, youwol_exception_handler
from youwol_utils.middlewares.root_middleware import RootMiddleware
from youwol_utils.utils_paths import matching_files, FileListing, files_check_sum

configuration: Configuration = asyncio.get_event_loop().run_until_complete(get_configuration())
asyncio.get_event_loop().run_until_complete(init_resources(configuration))

app = FastAPI(
    title="assets-gateway",
    description="backend to manage browsing of assets",
    root_path=configuration.open_api_prefix)


@app.exception_handler(YouWolException)
async def exception_handler(request: Request, exc: YouWolException):
    return await youwol_exception_handler(request, exc)


app.add_middleware(configuration.auth_middleware, **configuration.auth_middleware_args)
app.add_middleware(RootMiddleware, ctx_logger=configuration.ctx_logger)

app.include_router(
    base_router,
    prefix=configuration.base_path,
    dependencies=[Depends(get_configuration)],
    tags=[]
)

files_src_check_sum = matching_files(
    folder="./",
    patterns=FileListing(
        include=['*'],
        # when deployed using dockerfile there is additional files in ./src: a couple of .* files and requirements.txt
        ignore=["requirements.txt", ".*", "*.pyc"]
    )
)

log_info(f"./src check sum: {files_check_sum(files_src_check_sum)} ({len(files_src_check_sum)} files)")

if __name__ == "__main__":
    # app: incorrect type. More here: https://github.com/tiangolo/fastapi/issues/3927
    # noinspection PyTypeChecker
    uvicorn.run(app, host="0.0.0.0", port=configuration.http_port)
