from youwol_assets_gateway import get_router
from youwol_utils.servers.fast_api import serve, FastApiApp, FastApiRouter, AppConfiguration, \
    select_configuration_from_command_line


async def local() -> AppConfiguration:
    from config_local import get_configuration
    return await get_configuration()


async def prod() -> AppConfiguration:
    from config_prod import get_configuration
    return await get_configuration()


app_config = select_configuration_from_command_line(
    {
        "local": local,
        "prod": prod
    }
)

serve(
    FastApiApp(
        title="Assets-gateway",
        description="Assets-gateway server",
        server_options=app_config.server,
        root_router=FastApiRouter(
            router=get_router(app_config.service)
        )
    )
)
