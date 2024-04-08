# /usr/local/bin/python3.8 ~/Documents/dev/other/tennis_booking.py
import os
import time
import logging
import yagmail
import datetime
import traceback

import pandas as pd

from twilio.rest import Client
from apscheduler.schedulers.background import BackgroundScheduler

from cfg import cfg
from slots import get_permissible_slots, BookingSlot
from data_io import load_file, save_file
from utils.utils import get_chrome_driver, extract_site_contents


logger = logging.getLogger(__name__)


logging.getLogger("WDM").setLevel("WARNING")


WINDOW = cfg.CONFIG["window"]  # slots in which to notify recipients
SCHEDULE = cfg.CONFIG["schedule"]  # number of days to look ahead (current date inclusive)
# SCHEDULE = {k: [i+1 for i in range(24)] for k, _ in SCHEDULE.items()}  # for testing purposes

PRUNE_CACHE_FREQUENCY = cfg.CONFIG["prune_cache_frequency"]  # minutes
SLOT_NOTIFICATION_COOL_DOWN = cfg.CONFIG["slot_notification_cool_down"]  # hours

COURT_NAME = "st-johns-park"

BOOKING_FOUND_MESSAGE = f"{{n}} tennis court slots available at {COURT_NAME}"
BOOKING_FOUND_BODY = "{slots_html}" + ("\n" * 10) + "{timestamp}"

BOOKING_SYSTEM_DOWN_MESSAGE = "Tennis booking court system down"

BOOKING_SYSTEM_UP_MESSAGE = "Tennis booking court system back up and running"

BOOKING_WIDGET_URL = f"https://tennistowerhamlets.com/book/courts/{COURT_NAME}/{{date}}#book"
BOOKING_WIDGET_URL_DATE_FORMAT = "%Y-%m-%d"

CHROME_DRIVER = None
USE_CHROME_DRIVER = True
# CHROME_DRIVER_PATH = ""  #'/Users/andrewsanderson/Documents/dev/chromedriver'


TEXT_MESSAGE_FROM = ''
TEXT_MESSAGE_TO = ''
TEXT_MESSAGE_ACCOUNT_ID = ''
TEXT_MESSAGE_ACCOUNT_AUTH_TOKEN = ''
# TEXT_MESSAGE_CLIENT = Client(TEXT_MESSAGE_ACCOUNT_ID, TEXT_MESSAGE_ACCOUNT_AUTH_TOKEN)

AUTH = load_file("auth.json", io_type="os", prefix=os.path.join(os.path.dirname(__file__), ".secrets"))
EMAILS = load_file("emails.json", io_type="os", prefix=os.path.join(os.path.dirname(__file__), ".secrets"))


EMAIL_SENDER = AUTH["emails"]["address"]
EMAIL_SENDER_PASSWORD = AUTH["emails"]["password"]
EMAIL_SLOT_AVAILABLE_RECIPIENTS = EMAILS["slot_available"]
EMAIL_SYS_ERROR_RECIPIENTS = EMAILS["sys_errors"]


def send_email(booking_msg, body, recipients):
    """ Send an email about an available slot to book. """
    try:
        yag = yagmail.SMTP(EMAIL_SENDER, EMAIL_SENDER_PASSWORD)
        # yag.send(recipients, booking_msg, [body])
        yag.send(bcc=recipients, subject=booking_msg, contents=body)
        logger.info("Email sent successfully")
    except Exception as _:
        logger.error("Email send error", exc_info=True)


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
        send_email(msg, body, recipients)


def reload_content(driver, url, date, sleep=0, reload_interval=10):
    """ Wait indefinitely until the page refreshes, checking the page's implied date against
    a target date. """
    # refresh the driver's URL
    _, _, query_count = driver.get(url), logger.debug(f"Querying {url}"), 1

    while True:
        time.sleep(sleep)
        current = extract_site_contents(chrome_driver=driver)

        # check to see if courts are even available to book for this date
        closed_for_booking_check = current.find("p", attrs={"class": "closed"})
        if closed_for_booking_check:
            logger.warning(closed_for_booking_check.string)
            return None

        # extract expected date location from HTML
        arr = current.find_all("input", attrs={"name": "selected_date"})  # arr = current.find_all("div", attrs={"class": "date"})

        # format dates and check they're equal
        if not isinstance(arr, list) or len(arr) > 1:
            logger.error(f"Expected an array of one element when targeting the page's time but instead received: {arr}")
        else:
            if arr[0].get("value") == str(date):
                logger.debug("Queried date equals HTML's date")
                break
        logger.warning(f"Driver's web page yet to load, waiting {sleep} second(s): '{url}'")

        # after a certain number of attempts, re-load the URL
        if query_count % reload_interval == 0:
            logger.warning(f"Queried HTML {query_count} times, re-loading URL: '{url}'")
            driver.get(url)

        # increment query count
        query_count += 1

    return current


def check_booking_system(cache, start, window, schedule, week="", message_box=False, text_message=False, email=False,
                         auto_book=False):
    """ Query the booking system for permissible slots. Notify/book them, if requested. """
    timestamp = cfg.TIME_ZONE_MANAGER.now().strftime("%Y-%m-%d %H:%M:%S")
    default_notification_args = dict(
        message_box=message_box, text_message=text_message, email=email
    )

    # loop the days in the schedule
    df, dates, notify = pd.DataFrame(), [start + datetime.timedelta(days=i) for i in range(window)], False

    logger.info(f"Searching from {dates[0]} for {window} days")
    for date in dates:
        day, url = date.strftime("%a"), BOOKING_WIDGET_URL.format(date=date.strftime(BOOKING_WIDGET_URL_DATE_FORMAT))
        logger.debug(f"Directing chrome driver instance to {url}")
        content = reload_content(CHROME_DRIVER, url, date, sleep=3)
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
        msg = BOOKING_FOUND_MESSAGE.format(n=len(df))
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
        if close_existing:
            CHROME_DRIVER.quit()
        CHROME_DRIVER = get_chrome_driver(
            url="", driver_path=cfg.CONFIG["chrome"]["driver"], sleep=0
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
        try:
            # reload driver
            if cycle_count % cfg.CONFIG["chrome"]["reload_frequency"] == 0:
                reload_chrome_driver(close_existing=True)
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
            if not sys_down:
                logger.exception(ex)
                # send message
                dispatch_alerts(
                    BOOKING_SYSTEM_DOWN_MESSAGE, recipients=EMAIL_SYS_ERROR_RECIPIENTS, message_box=message_box,
                    text_message=text_message, email=email, body="\n".join(
                        traceback.format_exception(type(ex), ex, ex.__traceback__)
                    )
                )
            else:
                logger.warning("Booking system is down", exc_info=True)
            # system not running normally
            sys_down = True

        logger.info(f"Sleeping for {wait_time} second(s) before next search")
        time.sleep(wait_time)

        # if system down, reload Chrome Driver
        if sys_down:
            reload_chrome_driver(
                log_text="System is down, re-loading Chrome Driver", close_existing=True
            )


def _test():
    global CHROME_DRIVER

    CHROME_DRIVER = get_chrome_driver(
        url=BOOKING_WIDGET_URL.format(date="2022-10-10"),  # url
        driver_path="",
        sleep=1
    )

    content = extract_site_contents(chrome_driver=CHROME_DRIVER, sleep=1)
    slots_content = content.find_all("span", attrs={"class": "available-booking-slot"})

    slot = BookingSlot(slots_content[0], datetime.date(2022, 10, 10), [], week="")
    print(slot)
    assert slot.is_bookable


if __name__ == "__main__":
    # _test()
    # cache = Cache("/Users/andrewsanderson/Desktop/logs/tennis_booking.json", load=True)
    # prune_cache(cache, notification_cool_down=12, save=False)
    main(**cfg.CONFIG["runtime_args"])
