# /usr/local/bin/python3.8 ~/Documents/dev/other/main.py
import os
import socket
import getpass
import platform
import uuid
import time
import logging
import random
import json
import yagmail
import datetime
import traceback
from enum import Enum

import pandas as pd

from twilio.rest import Client
from apscheduler.schedulers.background import BackgroundScheduler

from cfg import cfg
from slots import get_permissible_slots, BookingSlot
from data_io import load_file, save_file
from utils.utils import get_chrome_driver, extract_site_contents


logger = logging.getLogger(__name__)


logging.getLogger("WDM").setLevel("WARNING")
logging.getLogger("apscheduler").setLevel("WARNING")


WINDOW = cfg.CONFIG["window"]  # slots in which to notify recipients
SCHEDULE = cfg.CONFIG["schedule"]  # number of days to look ahead (current date inclusive)
# SCHEDULE = {k: [i+1 for i in range(24)] for k, _ in SCHEDULE.items()}  # for testing purposes

CHROME_PAGE_POLL_SLEEP = float(cfg.CONFIG.get("chrome", {}).get("page_poll_sleep", 0.5))
CHROME_MAX_QUERY_ATTEMPTS = int(cfg.CONFIG.get("chrome", {}).get("max_query_attempts", 8))
CHROME_HEADLESS = bool(cfg.CONFIG.get("chrome", {}).get("headless", True))
CHROME_USER_DATA_DIR = str(cfg.CONFIG.get("chrome", {}).get("user_data_dir", "")).strip()
CHROME_PROFILE_DIRECTORY = str(cfg.CONFIG.get("chrome", {}).get("profile_directory", "")).strip()

CHALLENGE_CONFIG = cfg.CONFIG.get("challenge", {})
CHALLENGE_MANUAL_VERIFY_ENABLED = bool(CHALLENGE_CONFIG.get("manual_verify_enabled", True))
CHALLENGE_VERIFY_TIMEOUT_SECONDS = int(CHALLENGE_CONFIG.get("verify_timeout_seconds", 180))
CHALLENGE_VERIFY_POLL_SLEEP_SECONDS = float(CHALLENGE_CONFIG.get("verify_poll_sleep_seconds", 2))
CHALLENGE_PAGE_MARKERS = [
    str(marker).lower() for marker in CHALLENGE_CONFIG.get(
        "page_markers",
        [
            "verify you are a human",
            "captcha",
            "cloudflare",
            "are you human",
            "security check",
        ],
    )
]

POLLING_CONFIG = cfg.CONFIG.get("polling", {})
POLLING_RANDOMIZE = bool(POLLING_CONFIG.get("randomize", False))
POLLING_JITTER_RATIO = float(POLLING_CONFIG.get("jitter_ratio", 0.2))
POLLING_MIN_WAIT_SECONDS = POLLING_CONFIG.get("min_wait_seconds")
POLLING_MAX_WAIT_SECONDS = POLLING_CONFIG.get("max_wait_seconds")
POLLING_RANDOM_SEED = POLLING_CONFIG.get("seed")
POLLING_RANDOM = random.Random(POLLING_RANDOM_SEED)

DIAGNOSTICS_CONFIG = cfg.CONFIG.get("diagnostics", {})
DIAGNOSTICS_ENABLED = bool(DIAGNOSTICS_CONFIG.get("enabled", True))
DIAGNOSTICS_DIR = DIAGNOSTICS_CONFIG.get("dir", ".diagnostics")

PRUNE_CACHE_FREQUENCY = cfg.CONFIG["prune_cache_frequency"]  # minutes
SLOT_NOTIFICATION_COOL_DOWN = cfg.CONFIG["slot_notification_cool_down"]  # hours

VENUE = cfg.CONFIG["venue"]

BOOKING_FOUND_MESSAGE = f"{{n}} tennis court slots available at {VENUE} ({{timestamp}})"
BOOKING_FOUND_BODY = "{slots_html}" + ("\n" * 10) + "{timestamp}"

BOOKING_SYSTEM_DOWN_MESSAGE = "Tennis booking court system down"

BOOKING_SYSTEM_UP_MESSAGE = "Tennis booking court system back up and running"

BOOKING_WIDGET_URL = f"https://tennistowerhamlets.com/book/courts/{VENUE}/{{date}}#book"
BOOKING_WIDGET_URL_DATE_FORMAT = "%Y-%m-%d"

CHROME_DRIVER = None
USE_CHROME_DRIVER = True
# CHROME_DRIVER_PATH = ""  #'/Users/andrewsanderson/Documents/dev/chromedriver'

TEXT_MESSAGE_FROM = ''
TEXT_MESSAGE_TO = ''
TEXT_MESSAGE_ACCOUNT_ID = ''
TEXT_MESSAGE_ACCOUNT_AUTH_TOKEN = ''
# TEXT_MESSAGE_CLIENT = Client(TEXT_MESSAGE_ACCOUNT_ID, TEXT_MESSAGE_ACCOUNT_AUTH_TOKEN)

AUTH = load_file(
    cfg.CONFIG["auth_config_path"], io_type="os", prefix=os.path.join(os.path.dirname(__file__), ".secrets")
)
EMAILS = load_file(
    cfg.CONFIG["emails_config_path"], io_type="os", prefix=os.path.join(os.path.dirname(__file__), ".secrets")
)

logger.info(f"Auth is {AUTH}")
logger.info(f"Emails is {EMAILS}")

EMAIL_SENDER = AUTH["emails"]["address"]
EMAIL_SENDER_PASSWORD = AUTH["emails"]["password"]
EMAIL_SLOT_AVAILABLE_RECIPIENTS = EMAILS["slot_available"]
EMAIL_SYS_ERROR_RECIPIENTS = EMAILS["sys_errors"]


class PageClassification(Enum):
    DATE_MATCHED = "date_matched"
    CLOSED_FOR_BOOKING = "closed_for_booking"
    CHALLENGE_PAGE = "challenge_page"
    DATE_MISMATCH = "date_mismatch"
    MISSING_SELECTED_DATE = "missing_selected_date"
    INVALID_SELECTED_DATE_COUNT = "invalid_selected_date_count"


class MonitorState(Enum):
    NAVIGATE = "navigate"
    WAIT_FOR_SETTLE = "wait_for_settle"
    FETCH_HTML = "fetch_html"
    CLASSIFY_PAGE = "classify_page"
    RELOAD_PAGE = "reload_page"
    COMPLETED = "completed"
    STOPPED_CLOSED = "stopped_closed"
    STOPPED_TIMEOUT = "stopped_timeout"


def log_structured(event, level=logging.INFO, **payload):
    message = {
        "event": event,
        "timestamp": cfg.TIME_ZONE_MANAGER.now().isoformat(),
        **payload,
    }
    logger.log(level, json.dumps(message, default=str, sort_keys=True))


def classify_booking_page(content, expected_date):
    page_text = content.get_text(" ", strip=True).lower()
    for marker in CHALLENGE_PAGE_MARKERS:
        if marker and marker in page_text:
            return PageClassification.CHALLENGE_PAGE, {"marker": marker}

    closed_for_booking_check = content.find("p", attrs={"class": "closed"})
    if closed_for_booking_check:
        return PageClassification.CLOSED_FOR_BOOKING, {
            "reason": closed_for_booking_check.get_text(strip=True)
        }

    selected_date_fields = content.find_all("input", attrs={"name": "selected_date"})
    if isinstance(selected_date_fields, list) and len(selected_date_fields) == 1:
        observed_date = selected_date_fields[0].get("value")
        if observed_date == str(expected_date):
            return PageClassification.DATE_MATCHED, {"observed_date": observed_date}
        return PageClassification.DATE_MISMATCH, {
            "observed_date": observed_date,
            "expected_date": str(expected_date),
        }

    if isinstance(selected_date_fields, list) and len(selected_date_fields) == 0:
        return PageClassification.MISSING_SELECTED_DATE, {}

    return PageClassification.INVALID_SELECTED_DATE_COUNT, {
        "selected_date_count": len(selected_date_fields) if isinstance(selected_date_fields, list) else "non-list"
    }


def capture_failure_diagnostics(driver, context, exception=None, extra=None):
    if not DIAGNOSTICS_ENABLED:
        return {}

    timestamp = cfg.TIME_ZONE_MANAGER.now().strftime("%Y%m%d-%H%M%S")
    destination = os.path.join(DIAGNOSTICS_DIR, f"{timestamp}-{context}")
    os.makedirs(destination, exist_ok=True)

    output = {}
    if driver is not None:
        screenshot_path = os.path.join(destination, "screenshot.png")
        html_path = os.path.join(destination, "page.html")

        try:
            if driver.save_screenshot(screenshot_path):
                output["screenshot"] = screenshot_path
        except Exception:
            logger.warning("Failed to capture diagnostics screenshot", exc_info=True)

        try:
            with open(html_path, "w", encoding="utf-8") as page_file:
                page_file.write(driver.page_source)
            output["html"] = html_path
        except Exception:
            logger.warning("Failed to capture diagnostics HTML", exc_info=True)

    metadata_path = os.path.join(destination, "metadata.json")
    metadata = {
        "context": context,
        "timestamp": cfg.TIME_ZONE_MANAGER.now().isoformat(),
        "current_url": getattr(driver, "current_url", ""),
        "extra": extra or {},
    }
    if exception is not None:
        metadata["exception"] = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)),
        }

    try:
        with open(metadata_path, "w", encoding="utf-8") as metadata_file:
            json.dump(metadata, metadata_file, indent=2, sort_keys=True)
        output["metadata"] = metadata_path
    except Exception:
        logger.warning("Failed to capture diagnostics metadata", exc_info=True)

    return output


def send_email(booking_msg, body, recipients):
    """ Send an email about an available slot to book. """
    try:
        yag = yagmail.SMTP(EMAIL_SENDER, EMAIL_SENDER_PASSWORD)
        # yag.send(recipients, booking_msg, [body])
        yag.send(bcc=recipients, subject=booking_msg, contents=body)
        logger.info("Email sent successfully")
    except Exception as _:
        logger.error("Email send error", exc_info=True)


def get_email_source_footer():
    host_name = socket.gethostname()
    # fqdn = socket.getfqdn()
    user_name = getpass.getuser()
    machine = platform.machine()
    system = platform.system()
    release = platform.release()
    # python_version = platform.python_version()
    # machine_id = f"{uuid.getnode():012x}"
    # app_environment = getattr(cfg, "ENV", os.environ.get("APP_ENVIRONMENT", "unknown"))
    config_extras = os.environ.get("CONFIG_EXTRAS", "")
    return (
        "\n\n---\n"
        "Source:\n"
        f"host={host_name}\n"
        # f"fqdn={fqdn}\n"
        f"user={user_name}\n"
        f"os={system} {release}\n"
        f"arch={machine}\n"
        # f"python={python_version}\n"
        # f"machine_id={machine_id}\n"
        # f"env={app_environment}\n"
        f"config_extras={config_extras or 'NONE'}"
    )


def dispatch_alerts(msg, recipients, body="", message_box=False, text_message=False, email=False):
    # log the message
    logger.info(f"Email message is '{msg}'")
    logger.info(f"Email recipients are {recipients}")
    logger.debug(f"Email body is {body}")
    # message box
    if message_box:
        # tkinter.messagebox.showinfo(title="Tennis Court Booking", message=msg)
        logger.error("Message box alert not currently supported.")
    # email available (and permissible) slot
    if text_message:
        TEXT_MESSAGE_CLIENT.messages.create(to=TEXT_MESSAGE_TO, from_=TEXT_MESSAGE_FROM, body=msg)
    # email available (and permissible) slot
    if email:
        source_footer = get_email_source_footer()
        send_email(msg, f"{body}{source_footer}" if body else source_footer.strip(), recipients)


def wait_for_manual_verification(driver, url, date):
    """Allow a human to complete challenge verification in a visible browser window."""
    deadline = time.time() + CHALLENGE_VERIFY_TIMEOUT_SECONDS
    logger.warning(
        f"Challenge page detected at {url}. Please complete verification in the browser within "
        f"{CHALLENGE_VERIFY_TIMEOUT_SECONDS} second(s)."
    )

    while time.time() < deadline:
        time.sleep(CHALLENGE_VERIFY_POLL_SLEEP_SECONDS)
        current = extract_site_contents(chrome_driver=driver)
        classification, details = classify_booking_page(current, date)
        if classification != PageClassification.CHALLENGE_PAGE:
            log_structured(
                "challenge_page_cleared",
                url=url,
                page_classification=classification.value,
                **details,
            )
            return current

    logger.warning("Manual verification timed out")
    return None


def reload_content(driver, url, date, sleep=0, reload_interval=10):
    """ Wait indefinitely until the page refreshes, checking the page's implied date against
    a target date. """
    monitor_state = MonitorState.NAVIGATE
    _, _, query_count = driver.get(url), logger.debug(f"Querying {url}"), 1

    while query_count <= CHROME_MAX_QUERY_ATTEMPTS:
        monitor_state = MonitorState.WAIT_FOR_SETTLE
        time.sleep(sleep)

        monitor_state = MonitorState.FETCH_HTML
        current = extract_site_contents(chrome_driver=driver)

        monitor_state = MonitorState.CLASSIFY_PAGE
        page_classification, details = classify_booking_page(current, date)
        log_structured(
            "booking_page_classified",
            monitor_state=monitor_state.value,
            page_classification=page_classification.value,
            query_count=query_count,
            url=url,
            **details,
        )

        if page_classification == PageClassification.DATE_MATCHED:
            monitor_state = MonitorState.COMPLETED
            logger.debug("Queried date equals HTML's date")
            return current

        if page_classification == PageClassification.CHALLENGE_PAGE:
            logger.warning(
                "Challenge page encountered. "
                "If using headless mode, set chrome.headless to false for manual verification."
            )
            capture_failure_diagnostics(
                driver,
                context="challenge_page_detected",
                extra={"url": url, "marker": details.get("marker", "")},
            )

            if CHALLENGE_MANUAL_VERIFY_ENABLED and not CHROME_HEADLESS:
                manually_verified_content = wait_for_manual_verification(driver, url, date)
                if manually_verified_content is not None:
                    current = manually_verified_content
                    page_classification, details = classify_booking_page(current, date)
                    if page_classification == PageClassification.DATE_MATCHED:
                        monitor_state = MonitorState.COMPLETED
                        return current
                    if page_classification == PageClassification.CLOSED_FOR_BOOKING:
                        monitor_state = MonitorState.STOPPED_CLOSED
                        return None
                else:
                    return None

        if page_classification == PageClassification.CLOSED_FOR_BOOKING:
            monitor_state = MonitorState.STOPPED_CLOSED
            logger.debug(details.get("reason", "Date is closed for booking"))
            return None

        if page_classification == PageClassification.DATE_MISMATCH:
            logger.debug(
                f"Expected date '{details.get('expected_date')}' but observed '{details.get('observed_date')}'"
            )
        elif page_classification == PageClassification.MISSING_SELECTED_DATE:
            logger.warning("selected_date field missing from page; waiting for page to settle")
        elif page_classification == PageClassification.INVALID_SELECTED_DATE_COUNT:
            logger.warning(
                "Expected one selected_date field but received "
                f"{details.get('selected_date_count', 'non-list')}"
            )

        logger.warning(f"Driver's web page yet to load, waiting {sleep} second(s): '{url}'")

        # after a certain number of attempts, re-load the URL
        if query_count % reload_interval == 0:
            monitor_state = MonitorState.RELOAD_PAGE
            logger.warning(f"Queried HTML {query_count} times, re-loading URL: '{url}'")
            driver.get(url)

        # increment query count
        query_count += 1

    if query_count > CHROME_MAX_QUERY_ATTEMPTS:
        monitor_state = MonitorState.STOPPED_TIMEOUT
        logger.warning(f"Timed out waiting for content date match at '{url}'")
        diagnostics = capture_failure_diagnostics(
            driver,
            context="reload_content_timeout",
            extra={
                "state": monitor_state.value,
                "url": url,
                "expected_date": str(date),
                "max_attempts": CHROME_MAX_QUERY_ATTEMPTS,
            },
        )
        if diagnostics:
            log_structured(
                "reload_content_diagnostics_captured",
                level=logging.WARNING,
                diagnostics=diagnostics,
                url=url,
                expected_date=str(date),
            )
        return None


def get_wait_time(default_wait_time):
    """Use a faster polling interval during the midnight release window."""
    boost = cfg.CONFIG.get("midnight_boost", {})
    if not boost.get("enabled", True):
        return default_wait_time

    now = cfg.TIME_ZONE_MANAGER.now()
    boost_hour = int(boost.get("hour", 0))
    boost_minutes = int(boost.get("minutes", 20))
    boosted_wait_time = int(boost.get("wait_time", 15))

    if now.hour == boost_hour and 0 <= now.minute < boost_minutes:
        return max(5, boosted_wait_time)

    return default_wait_time


def get_wait_interval(default_wait_time):
    """Select the next polling wait interval using optional randomization settings."""
    base_wait = float(get_wait_time(default_wait_time))

    if not POLLING_RANDOMIZE:
        return base_wait

    min_wait_seconds = POLLING_MIN_WAIT_SECONDS
    max_wait_seconds = POLLING_MAX_WAIT_SECONDS

    if min_wait_seconds is None or max_wait_seconds is None:
        min_wait_seconds = max(1.0, base_wait * (1 - POLLING_JITTER_RATIO))
        max_wait_seconds = max(min_wait_seconds, base_wait * (1 + POLLING_JITTER_RATIO))
    else:
        min_wait_seconds = float(min_wait_seconds)
        max_wait_seconds = max(min_wait_seconds, float(max_wait_seconds))

    wait_seconds = POLLING_RANDOM.uniform(min_wait_seconds, max_wait_seconds)
    log_structured(
        "polling_interval_selected",
        randomized=True,
        base_wait=base_wait,
        wait_seconds=round(wait_seconds, 3),
        min_wait_seconds=round(min_wait_seconds, 3),
        max_wait_seconds=round(max_wait_seconds, 3),
    )
    return wait_seconds


def check_booking_system(cache, start, window, schedule, week="", message_box=False, text_message=False, email=False,
                         auto_book=False):
    """ Query the booking system for permissible slots. Notify/book them, if requested. """
    timestamp = cfg.TIME_ZONE_MANAGER.now().strftime("%Y-%m-%d %H:%M:%S")
    default_notification_args = dict(
        message_box=message_box, text_message=text_message, email=email
    )

    # loop the days in the schedule
    df, dates, notify = pd.DataFrame(), [start + datetime.timedelta(days=i) for i in range(window)], False

    logger.debug(f"Searching from {dates[0]} for {window} days")
    for date in dates:
        day, url = date.strftime("%a"), BOOKING_WIDGET_URL.format(date=date.strftime(BOOKING_WIDGET_URL_DATE_FORMAT))
        logger.debug(f"Directing chrome driver instance to {url}")
        content = reload_content(CHROME_DRIVER, url, date, sleep=CHROME_PAGE_POLL_SLEEP)
        if not content:
            continue
        # get date permissible slots
        df_temp, day_slots = get_permissible_slots(content, date, schedule[day], week=week, url=url)  # TODO: remove week from all funcs!
        for day_slot in day_slots:
            key = str(day_slot)
            # notify, email etc for a new slot (i.e. one that's not already cached)
            if key not in cache:
                notify = True
                # book available (and permissible) slot
                if auto_book:
                    raise Exception("Auto-booking functionality not yet supported")
                # add to cache so we don't notify/attempt to book again etc.
                _, cache[key] = logger.info(f"Adding '{key}' to the cache as to not alert recipients again."), timestamp
                save_file(cfg.CONFIG["cache_file"], cache, **cfg.FILE_IO_KWARGS)
        df = pd.concat([df, df_temp])

    # send email (include multiple slots in one email)
    if notify:
        msg = BOOKING_FOUND_MESSAGE.format(n=len(df), timestamp=timestamp)
        dispatch_alerts(
            msg=msg,
            recipients=EMAIL_SLOT_AVAILABLE_RECIPIENTS,
            # body=BOOKING_FOUND_BODY.format(
            #     slots_html=df.to_html(index=False).replace("\n", ""),
            #     timestamp=timestamp
            # ),
            body=df.to_html(index=False).replace("\n", ""),
            **default_notification_args
        )


def prune_cache(cache, notification_cool_down=12, save=False):
    """ Cycle through cache; clean out redundant slots & clear those that have been cached for a certain period of
    time in case the slot has become available again.

    NOTE: can be done more efficiently by inspecting the schedule of permissible slots rather than implicitly assuming
    a slot would've been booked in an arbitrary time frame. """
    dt, queue = cfg.TIME_ZONE_MANAGER.now(), list()  # .strftime("%Y-%m-%d %H:%M:%S")

    for k, v in cache.items():
        dt_slot = datetime.datetime.strptime(k, "%a %d %b %Y,%H:%M")
        dt_slot_notification = datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
        if dt_slot + datetime.timedelta(hours=1) < dt:  # extra hour to avoid >1 emails for free current hour slot
            # check if cached slot is less than current date and time
            logger.info(f"Removing slot '{k}' from cache as it's no longer in scope")
            queue.append(k)
        elif (dt - dt_slot_notification) >= datetime.timedelta(hours=notification_cool_down):
            # check if cached slot has been cached for longer than the cool-down period. This allows for notifications 
            # of a slot again i.e. to account for booked then cancelled slots
            logger.info(
                f"Removing slot '{k}' from cache as it's been cached for at least {notification_cool_down} hours"
            )
            queue.append(k)

    # delete keys
    for k in queue:
        cache.pop(k)

    # save cache
    if save:
        save_file(cfg.CONFIG["cache_file"], cache, **cfg.FILE_IO_KWARGS)


def reload_chrome_driver(log_text="", close_existing=False):
    global CHROME_DRIVER

    if USE_CHROME_DRIVER:
        logger.info(log_text or "Loading Chrome Driver")
        if close_existing and CHROME_DRIVER is not None:
            try:
                CHROME_DRIVER.quit()
            except Exception:
                logger.warning("Existing Chrome Driver could not be closed cleanly", exc_info=True)
        CHROME_DRIVER = get_chrome_driver(
            url="",
            driver_path=cfg.CONFIG["chrome"]["driver"],
            sleep=0,
            headless=CHROME_HEADLESS,
            user_data_dir=CHROME_USER_DATA_DIR,
            profile_directory=CHROME_PROFILE_DIRECTORY,
        )


def main(wait_time=60, message_box=False, email=False, text_message=False):
    """ Monitor the booking system indefinitely. """
    sys_down = False

    # set global Chrome Driver instance
    reload_chrome_driver(close_existing=False)

    # load in persisted (/cached) results
    cache = load_file(cfg.CONFIG["cache_file"], **cfg.FILE_IO_KWARGS)

    # set up scheduler
    scheduler = BackgroundScheduler(job_defaults={"misfire_grace_time": None})
    scheduler.add_job(
        prune_cache, "interval", minutes=PRUNE_CACHE_FREQUENCY, args=[cache, SLOT_NOTIFICATION_COOL_DOWN, True]
    )
    scheduler.start()

    _, cycle_count = logger.info("Running tennis booking system continuously."), 0
    while True:
        log_structured("monitor_cycle_started", cycle_count=cycle_count)
        try:
            # reload driver
            if cycle_count % cfg.CONFIG["chrome"]["reload_frequency"] == 0:
                # reload_chrome_driver(close_existing=True)
                logger.info(f"Cycle count: {cycle_count}")
            # ensure start date rolls
            start = cfg.TIME_ZONE_MANAGER.now().date()
            # check the booking system: loops schedule and checks "bookability" of slots; notifies if slots found
            check_booking_system(
                cache, start, WINDOW, dict(SCHEDULE), message_box=message_box, email=email, text_message=text_message
            )
            # check if system was down last cycle (if we got to this point the system is back-up & running)
            if sys_down:
                # send message
                dispatch_alerts(
                    BOOKING_SYSTEM_UP_MESSAGE, recipients=EMAIL_SYS_ERROR_RECIPIENTS, message_box=message_box,
                    text_message=text_message, email=email
                )
            # system running normally
            sys_down, cycle_count = False, cycle_count+1
        except Exception as ex:
            diagnostics = capture_failure_diagnostics(
                CHROME_DRIVER,
                context="monitor_cycle_failure",
                exception=ex,
                extra={"cycle_count": cycle_count},
            )
            diagnostics_text = ""
            if diagnostics:
                diagnostics_lines = [f"- {k}: {v}" for k, v in diagnostics.items()]
                diagnostics_text = "\n\nDiagnostics:\n" + "\n".join(diagnostics_lines)

            if not sys_down:
                logger.exception(ex)
                log_structured(
                    "monitor_cycle_failed",
                    level=logging.ERROR,
                    cycle_count=cycle_count,
                    diagnostics=diagnostics,
                    error=str(ex),
                )
                # send message
                dispatch_alerts(
                    BOOKING_SYSTEM_DOWN_MESSAGE, recipients=EMAIL_SYS_ERROR_RECIPIENTS, message_box=message_box,
                    text_message=text_message, email=email, body="\n".join(
                        traceback.format_exception(type(ex), ex, ex.__traceback__)
                    ) + diagnostics_text
                )
            else:
                logger.warning("Booking system is down", exc_info=True)
            # system not running normally
            sys_down = True

        wait_interval = get_wait_interval(wait_time)
        logger.debug(f"Sleeping for {wait_interval} second(s) before next search")
        time.sleep(wait_interval)

        # if system down, reload Chrome Driver
        if sys_down:
            reload_chrome_driver(
                log_text="System is down, re-loading Chrome Driver", close_existing=True
            )


def _test():
    global CHROME_DRIVER

    CHROME_DRIVER = get_chrome_driver(
        url=BOOKING_WIDGET_URL.format(date="2026-5-12"),  # url
        driver_path="",
        sleep=5
    )

    CHROME_DRIVER.save_screenshot("debug.png")

    with open("page.html", "w", encoding="utf-8") as f:
        f.write(CHROME_DRIVER.page_source)


if __name__ == "__main__":
    # _test()
    # cache = Cache("/Users/andrewsanderson/Desktop/logs/tennis_booking.json", load=True)
    # prune_cache(cache, notification_cool_down=12, save=False)
    main(**cfg.CONFIG["runtime_args"])
