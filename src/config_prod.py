import os

from config_common import on_before_startup
from youwol.backends.assets_gateway import Configuration
from youwol.utils import CdnClient, RedisCacheClient
from youwol.utils.clients.assets.assets import AssetsClient
from youwol.utils.clients.files import FilesClient
from youwol.utils.clients.flux.flux import FluxClient
from youwol.utils.clients.oidc.oidc_config import OidcInfos, PrivateClient
from youwol.utils.clients.stories.stories import StoriesClient
from youwol.utils.clients.treedb.treedb import TreeDbClient
from youwol.utils.context import DeployedContextReporter
from youwol.utils.middlewares import AuthMiddleware, JwtProviderCookie
from youwol.utils.servers.env import OPENID_CLIENT, REDIS, Env
from youwol.utils.servers.fast_api import (AppConfiguration, FastApiMiddleware,
                                           ServerOptions)


async def get_configuration():
    required_env_vars = OPENID_CLIENT + REDIS

    not_founds = [v for v in required_env_vars if not os.getenv(v)]
    if not_founds:
        raise RuntimeError(f"Missing environments variable: {not_founds}")

    flux_client = FluxClient("http://flux-backend")
    cdn_client = CdnClient(url_base="http://cdn-backend")
    stories_client = StoriesClient(url_base="http://stories-backend")

    treedb_client = TreeDbClient(url_base="http://treedb-backend")
    assets_client = AssetsClient(url_base="http://assets-backend")
    files_client = FilesClient(url_base="http://files-backend")

    openid_base_url = (os.getenv(Env.OPENID_BASE_URL))
    openid_infos = OidcInfos(
        base_uri=openid_base_url,
        client=PrivateClient(
            client_id=(os.getenv(Env.OPENID_CLIENT_ID)),
            client_secret=(os.getenv(Env.OPENID_CLIENT_SECRET)),
        ),
    )

    async def _on_before_startup():
        await on_before_startup(service_config)

    service_config = Configuration(
        flux_client=flux_client,
        cdn_client=cdn_client,
        stories_client=stories_client,
        treedb_client=treedb_client,
        assets_client=assets_client,
        files_client=files_client,
        deployed=True,
    )

    server_options = ServerOptions(
        root_path="/api/assets-gateway",
        http_port=8080,
        base_path="",
        middlewares=[
            FastApiMiddleware(
                AuthMiddleware,
                {
                    "openid_base_uri": openid_base_url,
                    "predicate_public_path": lambda url: url.path.endswith("/healthz"),
                    "jwt_providers": [
                        JwtProviderCookie(
                            auth_cache=RedisCacheClient(
                                host=(os.getenv(Env.REDIS_HOST)), prefix="auth_cache"
                            ),
                            openid_infos=openid_infos,
                        )
                    ],
                },
            )
        ],
        on_before_startup=_on_before_startup,
        ctx_logger=DeployedContextReporter(),
    )
    return AppConfiguration(server=server_options, service=service_config)
