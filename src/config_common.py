import sys
from youwol_assets_gateway import Configuration as ServiceConfiguration
from youwol_utils.utils_paths import get_running_py_youwol_env

cache_prefix = "assets_gateway_"


async def get_py_youwol_env():
    py_youwol_port = sys.argv[2]
    if not py_youwol_port:
        raise RuntimeError("The configuration requires py-youwol to run on port provided as command line option")
    return await get_running_py_youwol_env(py_youwol_port)


async def on_before_startup(_selected_config: ServiceConfiguration):
    """
    Usually used to init minio's bucket or scylla's tables if they do not exist yet.
    The service assets-gateway does not own any data => there is nothing to do here
    """
    pass
