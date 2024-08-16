import os
import logging

from data_io import load_file
from utils.log import set_logger
from utils.date_time import TimeZoneManager


LOGGER = logging.getLogger(__name__)

ENV = os.environ.get("APP_ENVIRONMENT", "LOC")  # default to local config
CONFIG_EXTRAS = os.environ.get("CONFIG_EXTRAS", "")  # default to local config

DEFAULT_LOGGER_ARGS = {
    "format": "%(asctime)s - %(levelname)s - %(name)s:%(lineno)s  - %(message)s",
    "level": logging.INFO
}
GOOGLE_CLOUD_CREDENTIALS = {}
JSON_FILE = f"{ENV}.cfg{CONFIG_EXTRAS}.json"
FILE_IO_KWARGS = {
    "io_type": "os",
    "prefix": os.path.dirname(__file__),
    "bucket_name": "tennis_booking",
    "credentials": GOOGLE_CLOUD_CREDENTIALS
}


def load(force=False):
    global CONFIG
    global TIME_ZONE_MANAGER
    global DEFAULT_LOGGER_ARGS

    # only ever set logger once
    if not hasattr(load, "is_loaded"):
        set_logger(**DEFAULT_LOGGER_ARGS)

    LOGGER.info(f"Application environment is: {ENV}")

    if not hasattr(load, "is_loaded") or force:
        # load application config
        CONFIG = load_file(JSON_FILE, **FILE_IO_KWARGS)
        LOGGER.info(f"Loaded config: {CONFIG}")

        # create time zone manager instance
        TIME_ZONE_MANAGER = TimeZoneManager(CONFIG["timezone"], hour_offset=int(CONFIG.get("timezone_hour_offset", 0)))

    # prevent any downstream loading (unless forced...)
    load.is_loaded = True


# attempt load on any import of this module
load(force=False)
