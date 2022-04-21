from pathlib import Path
from config_common import get_py_youwol_env, on_before_startup
from youwol_assets_gateway import Configuration
from youwol_utils import CdnClient
from youwol_utils.clients.assets.assets import AssetsClient
from youwol_utils.clients.data_api.data import get_local_storage_client, get_local_docdb_client, DataClient
from youwol_utils.clients.files import FilesClient
from youwol_utils.clients.flux.flux import FluxClient
from youwol_utils.clients.stories.stories import StoriesClient
from youwol_utils.clients.treedb.treedb import TreeDbClient
from youwol_utils.context import ConsoleContextLogger
from youwol_utils.middlewares.authentication_local import AuthLocalMiddleware
from youwol_utils.servers.fast_api import FastApiMiddleware, AppConfiguration, ServerOptions


async def get_configuration():
    env = await get_py_youwol_env()
    databases_path = Path(env['pathsBook']['databases'])

    storage = get_local_storage_client(database_path=databases_path)
    docdb = get_local_docdb_client(database_path=databases_path)
    data_client = DataClient(storage=storage, docdb=docdb)
    flux_client = FluxClient(url_base=f"http://localhost:{env['httpPort']}/api/flux-backend")
    cdn_client = CdnClient(url_base=f"http://localhost:{env['httpPort']}/api/cdn-backend")
    stories_client = StoriesClient(url_base=f"http://localhost:{env['httpPort']}/api/stories-backend")
    treedb_client = TreeDbClient(url_base=f"http://localhost:{env['httpPort']}/api/treedb-backend")
    assets_client = AssetsClient(url_base=f"http://localhost:{env['httpPort']}/api/assets-backend")
    files_client = FilesClient(url_base=f"http://localhost:{env['httpPort']}/api/files-backend")

    async def _on_before_startup():
        await on_before_startup(service_config)

    service_config = Configuration(
        data_client=data_client,
        flux_client=flux_client,
        cdn_client=cdn_client,
        stories_client=stories_client,
        treedb_client=treedb_client,
        files_client=files_client,
        assets_client=assets_client
    )
    server_options = ServerOptions(
        root_path="",
        http_port=env['portsBook']['assets-gateway'],
        base_path="",
        middlewares=[FastApiMiddleware(AuthLocalMiddleware, {})],
        on_before_startup=_on_before_startup,
        ctx_logger=ConsoleContextLogger()
    )
    return AppConfiguration(
        server=server_options,
        service=service_config
    )
