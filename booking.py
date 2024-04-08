import logging
import selenium
import datetime

from main import *
from data_io import load_file
from utils.utils import get_chrome_driver, extract_site_contents
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


logger = logging.getLogger(__name__)


AUTO_BOOK_DETAILS = load_file(
    "auto-book.json", io_type="os", prefix=os.path.join(os.path.dirname(__file__), ".secrets")
)

TEXT_INPUT_MAPPING = {
    "name": "#txt-name",
    "email": "#txt-email",
    "mobile": "#txt-mobile",
    "date-of-birth": "#txt-dob",
}


def _add_to_basket(driver, table_index, court, time, wait=1):
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


def book(date, time, day_start=7, courts=(1, 2), wait=1):
    logger.info(f"Checking for available slots on {date} at {time}")

    time_string = str(time).zfill(2) + ":00"

    url = BOOKING_WIDGET_URL.format(date=date.strftime(BOOKING_WIDGET_URL_DATE_FORMAT))

    # Spin up driver
    driver = get_chrome_driver(
        url=url, driver_path="", sleep=wait
    )

    # Attempt to add a court to the basket
    table_index = 1 + (time - day_start)
    for court in list(courts):
        if _add_to_basket(driver, table_index, court, time=time_string, wait=wait):
            break

    # Navigate to the basket
    driver.get("https://tennistowerhamlets.com/basket")

    # Fill in required details for payment
    for k, v in AUTO_BOOK_DETAILS.items():
        selector = TEXT_INPUT_MAPPING[k]
        form = WebDriverWait(driver, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        form.send_keys(v)
        logger.info(f"Entered value for {k}")

    # Set gender to "prefer not to say"
    selector = " #frm_basket_customer > div:nth-child(8) > fieldset > label:nth-child(4) > input[type=radio]"
    radio_button = WebDriverWait(driver, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    radio_button.click()

    print("")


if __name__ == "__main__":
    book(
        date=datetime.date(2024, 4, 9), time=15
    )
