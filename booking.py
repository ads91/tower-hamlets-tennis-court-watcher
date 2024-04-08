import selenium

from main import *
from data_io import load_file
from utils.utils import get_chrome_driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


logger = logging.getLogger(__name__)


AUTO_BOOK_DETAILS = load_file(
    "auto-book.json", io_type="os", prefix=os.path.join(os.path.dirname(__file__), ".secrets")
)

PERSONAL_DETAILS_MAPPING = {
    "name": "#txt-name",
    "email": "#txt-email",
    "mobile": "#txt-mobile",
    "date-of-birth": "#txt-dob",
}


CARD_DETAILS_MAPPING = {
    "card-number": "#root > form > div > div.CardField-input-wrapper > span.CardField-number.CardField-child > span:nth-child(2) > div > div.CardNumberField-input-wrapper > span > input",
    "expiry": "#root > form > div > div.CardField-input-wrapper > span.CardField-restWrapper > span.CardField-expiry.CardField-child > span > span > input",
    "cvc": "#root > form > div > div.CardField-input-wrapper > span.CardField-restWrapper > span.CardField-cvc.CardField-child > span > span > input"
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


def book(date, time_, day_start=7, courts=(1, 2), wait=1, pay=False):
    logger.info(f"Checking for available slots on {date} at {time_}")

    time_string = str(time_).zfill(2) + ":00"

    url = BOOKING_WIDGET_URL.format(date=date.strftime(BOOKING_WIDGET_URL_DATE_FORMAT))

    # Spin up driver
    driver = get_chrome_driver(
        url=url, driver_path="", sleep=3
    )

    # Attempt to add a court to the basket
    added_to_basket, table_index = True, 1 + (time_ - day_start)
    for court in list(courts):
        if _add_to_basket(driver, table_index, court, time=time_string, wait=wait):
            added_to_basket = True
            break

    # Don't continue execution if nothing added to basket
    if not added_to_basket:
        logger.warning("No slots were booked")
        return

    # Navigate to the basket
    driver.get("https://tennistowerhamlets.com/basket")
    time.sleep(3)

    # Fill in required personal details
    for key, selector in PERSONAL_DETAILS_MAPPING.items():
        form = WebDriverWait(driver, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        form.send_keys(AUTO_BOOK_DETAILS[key])
        logger.info(f"Entered value for {key}")

    # Set gender to "prefer not to say"
    selector = " #frm_basket_customer > div:nth-child(8) > fieldset > label:nth-child(4) > input[type=radio]"
    radio_button = WebDriverWait(driver, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    radio_button.click()

    # Save & got to checkout
    selector = "#frm_basket_customer > div.controls > button"
    radio_button = WebDriverWait(driver, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    radio_button.click()

    # Pay with card
    selector = "#btn-pay-now"
    radio_button = WebDriverWait(driver, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    radio_button.click()

    # Fill in payment details
    for key, selector in CARD_DETAILS_MAPPING.items():
        form = WebDriverWait(driver, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        form.send_keys(AUTO_BOOK_DETAILS[key])
        logger.info(f"Entered value for {key}")

    # Press the pay button
    if pay:
        pass
    else:
        logging.warning("Not making payment until explicitly told to")

    print("")


if __name__ == "__main__":
    book(
        date=datetime.date(2024, 4, 9), time_=15, wait=1, pay=False
    )
