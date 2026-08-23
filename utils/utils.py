import os
import time
import json
import logging
import requests

import undetected_chromedriver as uc

from bs4 import BeautifulSoup
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager


LOGGER = logging.getLogger(__name__)


def get_chrome_driver(
        url="",
        driver_path="",
        sleep=0,
        headless=True,
    user_data_dir="",
    profile_directory="",
        chrome_version=150,
        init_retries=3,
        init_retry_sleep=2
):
    options = webdriver.ChromeOptions()

    if headless:
        options.add_argument("--headless=new")

    # Reduce automation fingerprints
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Stability
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")
    if profile_directory:
        options.add_argument(f"--profile-directory={profile_directory}")

    # Realistic browser fingerprint
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{chrome_version}.0.0.0 Safari/537.36"
    )

    # derive driver path (download latest if none provided)
    driver_path = driver_path or ChromeDriverManager().install()
    LOGGER.info(f"Chrome Driver path is '{driver_path}'")

    for attempt in range(1, int(init_retries) + 1):
        chrome_driver = None
        try:
            # create the driver instance
            chrome_driver = uc.Chrome(
                executable_path=driver_path,
                options=options,
                version_main=chrome_version,
                use_subprocess=True
            )

            chrome_driver.set_page_load_timeout(25)

            # Warm up the browser and validate at least one live window exists.
            chrome_driver.get("about:blank")
            if not chrome_driver.window_handles:
                raise RuntimeError("Chrome driver initialized without an active window")

            # wait for driver to load content at URL
            _, _ = LOGGER.debug(f"Sleeping: {sleep}"), time.sleep(sleep)

            # make a request through the driver
            if url:
                LOGGER.info(f"Requesting: {url}")
                chrome_driver.get(url)

            return chrome_driver
        except Exception as ex:
            LOGGER.warning(
                f"Chrome driver initialization attempt {attempt}/{init_retries} failed: {ex}",
                exc_info=True
            )
            if chrome_driver is not None:
                try:
                    chrome_driver.quit()
                except Exception:
                    LOGGER.debug("Failed to quit partially-initialized Chrome driver", exc_info=True)
            if attempt >= int(init_retries):
                raise
            time.sleep(init_retry_sleep)


def extract_site_contents(**kwargs):
    """ Return a python-friendly HTML representation of a website. """
    LOGGER.debug(f"Extracting site contents with {kwargs}")

    # multiple extraction methods
    if "chrome_driver" in kwargs:
        html = kwargs["chrome_driver"].page_source
    else:
        html = requests.get(kwargs["url"]).text

    # optionally sleep before extracting HTML content
    sleep_time = kwargs.get("sleep", 0)
    _, _ = LOGGER.debug(f"Sleeping for {sleep_time}"), time.sleep(sleep_time)

    return BeautifulSoup(html, "lxml")


def strcut(string, cut=100, sep="..."):
    if len(string) > cut:
        return string[:int(cut/2)] + sep + string[-int(cut/2):]
    return string


class Cache(dict):

    """ A persisted JSON file-cache. """

    def __init__(self, path, load=True):
        super(Cache, self).__init__()
        self.path = path
        if load:
            self.load()

    def load(self):
        if os.path.exists(self.path):
            persisted = json.load(open(self.path, "r"))
            self.update(persisted)
            LOGGER.info(f"Loaded {len(persisted)} items from {self.path}: {strcut(str(persisted))}")

    def save(self):
        with open(self.path, "w+") as json_file:
            json.dump(self, json_file)
        LOGGER.info(f"Wrote to {self.path}")
