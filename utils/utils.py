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


def get_chrome_driver(url="", driver_path="", sleep=0, chrome_version=128):
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized")
    options.add_argument("--headless")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--incognito")
    # options.add_argument("--disable-gpu")
    # options.add_argument("--window-size=%s" % window_size)  # window_size="1920,1080"

    # derive driver path (download latest if none provided)
    driver_path = driver_path or ChromeDriverManager().install()
    LOGGER.info(f"Chrome Driver path is '{driver_path}'")

    # create the driver instance
    chrome_driver = uc.Chrome(
        executable_path=driver_path, options=options, version_main=chrome_version
    )

    # wait for driver to load content at URL
    _, _ = LOGGER.debug(f"Sleeping: {sleep}"), time.sleep(sleep)

    # make a request through the driver
    if url:
        LOGGER.info(f"Requesting: {url}")
        chrome_driver.get(url)

    return chrome_driver


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
