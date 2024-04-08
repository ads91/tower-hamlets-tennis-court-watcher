import logging
import selenium
import datetime

from bs4 import BeautifulSoup
from main import *
from utils.utils import get_chrome_driver, extract_site_contents
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


logger = logging.getLogger(__name__)


def _add_to_basket(driver, table_index, court, time, wait=5):
    logger.info(f"Attempting to add court {court} at {time} to the basket")

    selector = f"#book > div.availability > form > table > tbody > tr:nth-child({table_index}) > td > label:nth-child({court}) > span.button.available"
    try:
        button = WebDriverWait(driver, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        button.click()
        logger.info(f"Added court {court} at {time} to the basket")
        return True
    except selenium.common.exceptions.TimeoutException as _:
        logger.debug("Slot not available")
    except Exception as _:
        logger.critical("Unknown exception occurred", exc_info=True)

    return False


def book(date, time, day_start=7, courts=(1, 2)):
    logger.info(f"Checking for available slots on {date} at {time}")

    time_string = str(time).zfill(2) + ":00"

    # Spin up driver
    driver = get_chrome_driver(
        url=BOOKING_WIDGET_URL.format(date=date.strftime(BOOKING_WIDGET_URL_DATE_FORMAT)),
        driver_path="",
        sleep=1
    )

    # Attempt to add a court to the basket
    table_index = 1 + (time - day_start)
    for court in list(courts):
        if _add_to_basket(driver, table_index, court, time=time_string, wait=5):
            break

    # Navigate to the basket
    selector_basket = "# menu-basket > img"
    button = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector_basket)))
    button.click()

    print("")


if __name__ == "__main__":
    book(
        date=datetime.date(2024, 4, 9), time=15
    )
