import selenium
import argparse

from main import *
from data_io import load_file
from utils.utils import get_chrome_driver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.blocking import BlockingScheduler


logger = logging.getLogger(__name__)


# Spin up driver
DRIVER = get_chrome_driver(
    driver_path="", sleep=1  # url=url,
)


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
    "card-number": "#card-element > div > iframe",
    "expiry": None,  # no selector, just hit tab from current selection
    "cvc": None  # no selector, just hit tab from current selection
}


def add_to_basket(driver, table_index, court, time, wait=1):
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


def book(date, time_, day_start=7, courts=(1, 2), wait=5, delay=0, pay=False):
    logger.info(f"Checking for available slots on {date} at {time_}")

    time_string = str(time_).zfill(2) + ":00"

    url = BOOKING_WIDGET_URL.format(date=date.strftime(BOOKING_WIDGET_URL_DATE_FORMAT))

    # Sleep temporarily before performing operations
    _, _ = logger.info(f"Delaying execution by {delay} seconds"), time.sleep(delay)

    # Spin up driver
    DRIVER.get(
        url=url
    )

    # Attempt to add a court to the basket
    added_to_basket, table_index = False, 1 + (time_ - day_start)
    for court in list(courts):
        added_to_basket = add_to_basket(DRIVER, table_index, court, time=time_string, wait=wait)
        if added_to_basket:
            break

    # Don't continue execution if nothing added to basket
    if not added_to_basket:
        logger.warning("No slots were booked")
        return False

    # Navigate to the basket
    DRIVER.get("https://tennistowerhamlets.com/basket")
    # time.sleep(3)

    # Fill in required personal details
    for key, selector in PERSONAL_DETAILS_MAPPING.items():
        form = WebDriverWait(DRIVER, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        form.send_keys(AUTO_BOOK_DETAILS[key])
        logger.info(f"Entered value for {key}")

    # Set gender to "prefer not to say"
    selector = " #frm_basket_customer > div:nth-child(8) > fieldset > label:nth-child(4) > input[type=radio]"
    radio_button = WebDriverWait(DRIVER, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    radio_button.click()

    # Save & go to checkout
    selector = "#frm_basket_customer > div.controls > button"
    button = WebDriverWait(DRIVER, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    button.click()

    # Pay with card
    selector = "#btn-pay-now"
    button = WebDriverWait(DRIVER, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    button.click()

    # Fill in payment details
    time.sleep(wait)  # important to have as we can't inspect as to when Stripe's payment widget has loaded!!
    for key, selector in CARD_DETAILS_MAPPING.items():
        if selector:
            form = WebDriverWait(DRIVER, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))  # visibility_of_element_located?
            form.send_keys(AUTO_BOOK_DETAILS[key])
        else:
            # git tab & then enter details in the next cell
            # selenium.webdriver.ActionChains(DRIVER).send_keys(Keys.TAB).perform()  # only needed for incorrect card details (Stripe auto-tabs for correct details)
            active_element = DRIVER.switch_to.active_element
            active_element.send_keys(AUTO_BOOK_DETAILS[key])
        logger.info(f"Entered value for {key}")

    # Press the pay button
    selector = "#submit"
    button = WebDriverWait(DRIVER, wait).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    if pay:
        button.click()
        _, _ = time.sleep(30), logging.info(f"Booked court {court} at {VENUE} for {time_} on {date}")
        return True
    else:
        logging.warning("Not making payment until explicitly told to")

    return False


def force_book(**kwargs):
    attempt, attempts = 1, kwargs.get("attempts", 3)

    while attempt <= attempts:
        try:
            if book(**kwargs):
                break
        except Exception as _:
            logger.error(f"Failed to book on attempt number {attempt}", exc_info=True)
        attempt += 1

    logger.info("Done attempting to book")


def schedule(cron_schedule, slot_day, slot_time, delay, pay):
    scheduler = BlockingScheduler(job_defaults={"misfire_grace_time": None})
    scheduler.add_job(
        func=force_book,
        trigger=CronTrigger.from_crontab(cron_schedule),
        kwargs=dict(
            date=datetime.datetime.strptime(slot_day, "%Y-%m-%d"),
            time_=int(slot_time),
            delay=int(delay),
            pay={"TRUE": True, "FALSE": False}[pay.upper()]
        )
    )
    scheduler.start()


def run():
    # python3 booking.py --cron_schedule "0 0 * * sat" --slot_day "2024-06-29" --slot_time "14" --delay 1 --pay FALSE
    # python3 booking.py --cron_schedule "0 0 * * sat" --slot_day "2024-06-29" --slot_time "15" --delay 1 --pay FALSE

    parser = argparse.ArgumentParser()

    parser.add_argument("--cron_schedule")  # when to attempt to book e.g. "0 0 * * sat" (midnight Friday/the beginning of Saturday)
    parser.add_argument("--slot_day")  # the day of the slot to book (in format YYYY-MM-DD)
    parser.add_argument("--slot_time")  # the time of the slot to book (i.e. 22 for 10PM)
    parser.add_argument("--delay", default="0")  # seconds delay before performing operations
    parser.add_argument("--pay", default="FALSE")  # TRUE or FALSE, will only click pay button if set to TRUE
    args, _ = parser.parse_known_args()

    logging.info(f"Command line args are: {args.__dict__}")

    schedule(**args.__dict__)


if __name__ == "__main__":
    run()
    # book(
    #     date=datetime.date(2024, 6, 29), time_=8, wait=5, pay=False
    # )
