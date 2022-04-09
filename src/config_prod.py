import os

from config_common import on_before_startup, cache_prefix

from youwol_assets_gateway import Configuration

from youwol_utils import AuthClient, CacheClient, CdnClient, get_headers_auth_admin_from_env
from youwol_utils.clients.assets.assets import AssetsClient
from youwol_utils.clients.data_api.data import get_remote_storage_client, get_remote_docdb_client, DataClient
from youwol_utils.clients.flux.flux import FluxClient
from youwol_utils.clients.stories.stories import StoriesClient
from youwol_utils.clients.treedb.treedb import TreeDbClient
from youwol_utils.context import DeployedContextLogger
from youwol_utils.middlewares import Middleware
from youwol_utils.servers.fast_api import FastApiMiddleware, AppConfiguration, ServerOptions


async def get_configuration():

    required_env_vars = ["AUTH_HOST", "AUTH_CLIENT_ID", "AUTH_CLIENT_SECRET", "AUTH_CLIENT_SCOPE"]

    not_founds = [v for v in required_env_vars if not os.getenv(v)]
    if not_founds:
        raise RuntimeError(f"Missing environments variable: {not_founds}")

    storage = get_remote_storage_client(
        url_base="http://storage/api"
    )
    docdb = get_remote_docdb_client(
        url_base="http://docdb/api",
        replication_factor=2
    )

    data_client = DataClient(storage=storage, docdb=docdb)
    flux_client = FluxClient("http://flux-backend")
    cdn_client = CdnClient(url_base="http://cdn-backend")
    stories_client = StoriesClient(url_base="http://stories-backend")

    treedb_client = TreeDbClient(url_base="http://treedb-backend")
    assets_client = AssetsClient(url_base="http://assets-backend")

    openid_host = os.getenv("AUTH_HOST")
    auth_client = AuthClient(url_base=f"https://{openid_host}/auth")
    cache_client = CacheClient(host="redis-master.infra.svc.cluster.local", prefix=cache_prefix)

    async def _on_before_startup():
        await on_before_startup(service_config)

    service_config = Configuration(
        data_client=data_client,
        flux_client=flux_client,
        cdn_client=cdn_client,
        stories_client=stories_client,
        treedb_client=treedb_client,
        assets_client=assets_client,
        admin_headers=await get_headers_auth_admin_from_env()
    )

    server_options = ServerOptions(
        root_path='/api/assets-gateway',
        http_port=8080,
        base_path="",
        middlewares=[
            FastApiMiddleware(
                Middleware, {
                    "auth_client": auth_client,
                    "cache_client": cache_client,
                    # healthz need to not be protected as it is used for liveness prob
                    "unprotected_paths": lambda url: url.path.split("/")[-1] == "healthz"
                }
            )
        ],
        on_before_startup=_on_before_startup,
        ctx_logger=DeployedContextLogger()
    )
    return AppConfiguration(
        server=server_options,
        service=service_config
    )
