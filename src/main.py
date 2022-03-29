import asyncio

from youwol_assets_gateway import Dependencies
from configurations import get_configuration, Configuration
from youwol_assets_gateway import router, init_resources
from youwol_utils.servers.fast_api import serve, FastApiApp, FastApiRouter, FastApiMiddleware

configuration: Configuration = asyncio.get_event_loop().run_until_complete(get_configuration())
asyncio.get_event_loop().run_until_complete(init_resources(configuration))

Dependencies.get_configuration = get_configuration

serve(
    FastApiApp(
        title="assets-gateway",
        description="Assets gateway service of YouWol",
        root_path=configuration.root_path,
        base_path=configuration.base_path,
        root_router=FastApiRouter(
            router=router
        ),
        middlewares=[FastApiMiddleware(
            configuration.auth_middleware,
            configuration.auth_middleware_args
        )],
        ctx_logger=configuration.ctx_logger,
        http_port=configuration.http_port
    )
)
