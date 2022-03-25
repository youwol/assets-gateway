import os
import sys
from dataclasses import dataclass
from typing import Callable, Union, Type, Dict, Coroutine, Any

from youwol_utils import (
    AuthClient, CacheClient, LocalCacheClient, find_platform_path, CdnClient, DocDb, Storage,
    DocDbClient, StorageClient, LocalDocDbClient, LocalStorageClient, get_headers_auth_admin_from_env, TableBody,
    get_headers_auth_admin_from_secrets_file, log_info,
)
from youwol_utils.clients.assets.assets import AssetsClient
from youwol_utils.clients.data_api.data import (
    DataClient, get_remote_storage_client, get_remote_docdb_client,
    get_local_storage_client, get_local_docdb_client
)
from youwol_utils.clients.flux.flux import FluxClient
from youwol_utils.clients.stories.stories import StoriesClient
from youwol_utils.clients.treedb.treedb import TreeDbClient
from youwol_utils.context import ContextLogger, DeployedContextLogger
from youwol_utils.middlewares import Middleware
from youwol_utils.middlewares.authentication_local import AuthLocalMiddleware
from youwol_utils.utils_paths import get_databases_path
from .raw_stores.data import DataStore
from .raw_stores.flux_project import FluxProjectsStore
from .raw_stores.package import PackagesStore
from .raw_stores.story import StoriesStore

AuthMiddleware = Union[Type[Middleware], Type[AuthLocalMiddleware]]


@dataclass(frozen=True)
class Configuration:
    open_api_prefix: str
    http_port: int
    base_path: str

    data_client: DataClient
    flux_client: FluxClient
    cdn_client: CdnClient
    stories_client: StoriesClient
    treedb_client: TreeDbClient
    assets_client: AssetsClient

    auth_middleware: AuthMiddleware
    auth_middleware_args: Dict[str, any]
    admin_headers: Union[Coroutine[Any, Any, Dict[str, str]], None]

    docdb_factory: Callable[[str, str, str], DocDb]
    storage_factory: Callable[[str], Storage]

    cache_prefix: str = "assets-gateway"
    replication_factor: int = 2
    unprotected_paths: Callable[[str], bool] = lambda url: \
        url.path.split("/")[-1] == "healthz" or url.path.split("/")[-1] == "openapi-docs"

    to_package = ["flux-project", "data", "package", "group-showcase"]

    def assets_stores(self):
        return [
            FluxProjectsStore(client=self.flux_client),
            PackagesStore(client=self.cdn_client),
            DataStore(client=self.data_client),
            StoriesStore(client=self.stories_client)
        ]

    ctx_logger: ContextLogger = DeployedContextLogger()


async def get_tricot_config() -> Configuration:
    required_env_vars = ["AUTH_HOST", "AUTH_CLIENT_ID", "AUTH_CLIENT_SECRET", "AUTH_CLIENT_SCOPE"]
    not_founds = [v for v in required_env_vars if not os.getenv(v)]
    if not_founds:
        raise RuntimeError(f"Missing environments variable: {not_founds}")
    openid_host = os.getenv("AUTH_HOST")

    log_info("Use tricot configuration", openid_host=openid_host)

    storage = get_remote_storage_client(
        url_base="http://storage/api"
    )
    docdb = get_remote_docdb_client(
        url_base="http://docdb/api",
        replication_factor=Configuration.replication_factor
    )

    data_client = DataClient(storage=storage, docdb=docdb)
    flux_client = FluxClient("http://flux-backend")
    cdn_client = CdnClient(url_base="http://cdn-backend")
    stories_client = StoriesClient(url_base="http://stories-backend")

    treedb_client = TreeDbClient(url_base="http://treedb-backend")
    assets_client = AssetsClient(url_base="http://assets-backend")

    def docdb_factory(keyspace: str, table: str, primary: str):
        return DocDbClient(url_base="http://docdb/api", keyspace_name=keyspace,
                           table_body=TableBody(name=table, version="0.0", columns=[], partition_key=[primary]),
                           replication_factor=Configuration.replication_factor
                           )

    def storage_factory(bucket_name: str):
        return StorageClient(url_base="http://storage/api", bucket_name=bucket_name)

    return Configuration(
        open_api_prefix='/api/assets-gateway',
        http_port=8080,
        base_path="",
        auth_middleware=Middleware,
        auth_middleware_args={
            "auth_client": AuthClient(url_base=f"https://{openid_host}/auth"),
            "cache_client": CacheClient(host="redis-master.infra.svc.cluster.local",
                                        prefix=Configuration.cache_prefix),
            "unprotected_paths": Configuration.unprotected_paths
        },
        data_client=data_client,
        flux_client=flux_client,
        cdn_client=cdn_client,
        stories_client=stories_client,
        treedb_client=treedb_client,
        assets_client=assets_client,
        docdb_factory=docdb_factory,
        storage_factory=storage_factory,
        admin_headers=get_headers_auth_admin_from_env()
    )


async def get_remote_config(url_cluster) -> Configuration:
    openid_host = "gc.auth.youwol.com"
    storage = get_remote_storage_client(url_base=f"https://{url_cluster}/api/storage")
    docdb = get_remote_docdb_client(url_base=f"https://{url_cluster}/api/docdb",
                                    replication_factor=Configuration.replication_factor)

    data_client = DataClient(storage=storage, docdb=docdb)
    flux_client = FluxClient(url_base="http://localhost:2000/api/flux-backend")
    cdn_client = CdnClient(url_base="http://localhost:2000/api/cdn-backend")
    stories_client = StoriesClient(url_base="http://localhost:2000/api/stories-backend")
    treedb_client = TreeDbClient(url_base="http://localhost:2000/api/treedb-backend")
    assets_client = AssetsClient(url_base="http://localhost:2000/api/assets-backend")

    def docdb_factory(keyspace: str, table: str, primary: str):
        return DocDbClient(url_base=f"https://{url_cluster}/api/docdb", keyspace_name=keyspace,
                           table_body=TableBody(name=table, version="0.0", columns=[], partition_key=[primary]),
                           replication_factor=Configuration.replication_factor)

    def storage_factory(bucket_name: str):
        return StorageClient(url_base=f"https://{url_cluster}/api/storage", bucket_name=bucket_name)

    return Configuration(
        open_api_prefix='/api/assets-gateway',
        http_port=2458,
        base_path="",
        data_client=data_client,
        flux_client=flux_client,
        cdn_client=cdn_client,
        stories_client=stories_client,
        treedb_client=treedb_client,
        assets_client=assets_client,
        auth_middleware=Middleware,
        auth_middleware_args={
            "auth_client": AuthClient(url_base=f"https://{openid_host}/auth"),
            "cache_client": LocalCacheClient(prefix=Configuration.cache_prefix),
            "unprotected_paths": Configuration.unprotected_paths
        },
        docdb_factory=docdb_factory,
        storage_factory=storage_factory,
        admin_headers=get_headers_auth_admin_from_secrets_file(
            file_path=find_platform_path() / "secrets" / "tricot.json",
            url_cluster=url_cluster,
            openid_host=openid_host
        )
    )


async def get_local_config_dev() -> Configuration:
    return await get_remote_config("dev.platform.youwol.com")


async def get_local_config_test() -> Configuration:
    return await get_remote_config("test.platform.youwol.com")


async def get_full_local_config() -> Configuration:
    py_youwol_port = sys.argv[2]
    database_path = await get_databases_path(py_youwol_port)
    storage = get_local_storage_client(database_path=database_path)
    docdb = get_local_docdb_client(database_path=database_path)
    data_client = DataClient(storage=storage, docdb=docdb)
    flux_client = FluxClient(url_base=f"http://localhost:{py_youwol_port}/api/flux-backend")
    cdn_client = CdnClient(url_base=f"http://localhost:{py_youwol_port}/api/cdn-backend")
    stories_client = StoriesClient(url_base=f"http://localhost:{py_youwol_port}/api/stories-backend")

    treedb_client = TreeDbClient(url_base=f"http://localhost:{py_youwol_port}/api/treedb-backend")
    assets_client = AssetsClient(url_base=f"http://localhost:{py_youwol_port}/api/assets-backend")

    def docdb_factory(keyspace: str, table: str, primary: str):
        return LocalDocDbClient(root_path=database_path / 'docdb', keyspace_name=keyspace,
                                table_body=TableBody(name=table, version="0.0", columns=[], partition_key=[primary])
                                )

    def storage_factory(bucket_name: str):
        return LocalStorageClient(root_path=database_path / 'storage',
                                  bucket_name=bucket_name)

    return Configuration(
        open_api_prefix='',
        http_port=2458,
        base_path="",
        data_client=data_client,
        flux_client=flux_client,
        cdn_client=cdn_client,
        stories_client=stories_client,
        treedb_client=treedb_client,
        assets_client=assets_client,
        auth_middleware=AuthLocalMiddleware,
        auth_middleware_args={},
        docdb_factory=docdb_factory,
        storage_factory=storage_factory,
        admin_headers=None
    )


configurations = {
    'tricot': get_tricot_config,
    'local': get_local_config_dev,
    'local-test': get_local_config_test,
    'full-local': get_full_local_config,
}

current_configuration = None


async def get_configuration():
    global current_configuration
    if current_configuration:
        return current_configuration

    current_configuration = await configurations[sys.argv[1]]()
    return current_configuration
