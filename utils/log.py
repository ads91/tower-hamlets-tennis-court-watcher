import logging


LOGGER = logging.getLogger(__name__)


def set_logger(format, level=logging.INFO):
    formatter = logging.Formatter(format)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


if __name__ == "__main__":
    args = {
        "format": "%(asctime)s - %(process)d - %(levelname)s - %(name)s,%(funcName)s:%(lineno)s  - %(message)s",
        "level": logging.INFO
    }
    set_logger(**args)
    LOGGER.info("Test logging trace")
