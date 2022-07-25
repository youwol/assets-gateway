import os

from config_common import on_before_startup
from youwol_assets_gateway import Configuration
from youwol_utils import CdnClient, RedisCacheClient, get_authorization_header
from youwol_utils.clients.assets.assets import AssetsClient
from youwol_utils.clients.data_api.data import get_remote_storage_client, get_remote_docdb_client, DataClient
from youwol_utils.clients.files import FilesClient
from youwol_utils.clients.flux.flux import FluxClient
from youwol_utils.clients.oidc.oidc_config import PrivateClient, OidcInfos
from youwol_utils.clients.stories.stories import StoriesClient
from youwol_utils.clients.treedb.treedb import TreeDbClient
from youwol_utils.context import DeployedContextReporter
from youwol_utils.middlewares import AuthMiddleware, JwtProviderCookie
from youwol_utils.servers.fast_api import FastApiMiddleware, AppConfiguration, ServerOptions


async def get_configuration():
    required_env_vars = [
        "OPENID_BASE_URL",
        "OPENID_CLIENT_ID",
        "OPENID_CLIENT_SECRET",
        "REDIS_HOST"
    ]

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
    files_client = FilesClient(url_base="http://files-backend")

    openid_infos = OidcInfos(
        base_uri=(os.getenv("OPENID_BASE_URL")),
        client=PrivateClient(
            client_id=(os.getenv("OPENID_CLIENT_ID")),
            client_secret=(os.getenv("OPENID_CLIENT_SECRET"))
        )
    )

    async def _on_before_startup():
        await on_before_startup(service_config)

    service_config = Configuration(
        data_client=data_client,
        flux_client=flux_client,
        cdn_client=cdn_client,
        stories_client=stories_client,
        treedb_client=treedb_client,
        assets_client=assets_client,
        files_client=files_client,
        admin_headers=await get_authorization_header(openid_infos)
    )

    server_options = ServerOptions(
        root_path='/api/assets-gateway',
        http_port=8080,
        base_path="",
        middlewares=[
            FastApiMiddleware(
                AuthMiddleware, {
                    'openid_infos': openid_infos,
                    'predicate_public_path': lambda url:
                    url.path.endswith("/healthz"),
                    'jwt_providers': [
                        JwtProviderCookie(
                            jwt_cache=RedisCacheClient(
                                host=(os.getenv("REDIS_HOST")),
                                prefix='jwt_cache'
                            ),
                            openid_infos=openid_infos
                        )],
                }
            )
        ],
        on_before_startup=_on_before_startup,
        ctx_logger=DeployedContextReporter()
    )
    return AppConfiguration(
        server=server_options,
        service=service_config
    )
