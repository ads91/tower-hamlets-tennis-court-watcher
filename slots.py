import logging
import datetime

import pandas as pd


LOGGER = logging.getLogger(__name__)


class BookingSlot(object):

    """ A state representation of the HTML booking slot in the booking system. """

    def __init__(self, hour, date, schedule, court):
        self._date = date
        self._schedule = schedule
        self._time_hours = hour
        self._court = court

    def __repr__(self):
        return f"{self.date},{self.time}"

    def __str__(self):
        return self.__repr__()

    @property
    def is_bookable(self):
        """ Check if time slot falls into permissible schedule. """
        return self._time_hours in self._schedule  # i.e. the hour of the day

    @property
    def time(self):
        dummy_date = datetime.datetime(year=1, month=1, day=1)
        return (dummy_date + datetime.timedelta(hours=self._time_hours)).strftime("%H:%M")

    @property
    def date(self):
        return self._date.strftime("%a %d %b %Y")


def get_permissible_slots(content, date, schedule, url="", week=""):
    """ Return a list of BookingSlot instances for permissible days. """
    df, slots = pd.read_html(io=str(content.find_all("div", attrs={"class": "availability"})))[0], []

    if df.empty:
        return slots

    # split on the "Court" identifier
    df[2] = df[1].str.split("Court")

    def _expand_list(row):
        return pd.Series(row[2])

    # expand the column of lists into their own distinct fields
    expanded_df = df.apply(_expand_list, axis=1)
    expanded_df.columns = [f'col{i + 1}' for i in range(len(expanded_df.columns))]
    df = pd.concat([df, expanded_df], axis=1)

    # some post-formatting
    df = df.rename(columns={0: "time", "col2": "court_1", "col3": "court_2"})[["time", "court_1", "court_2"]]
    df = df.set_index("time").stack().to_frame().rename(columns={0: "status"})
    df.index.names = ["time", "court"]
    df = df.reset_index()

    # transform time field
    df["time"] = df["time"].apply(lambda t: int(t[:-2]) + {"am": 0, "pm": 12}[t[-2:]])

    # assume those with a £ sign are unbooked
    df = df[df["status"].str.contains("£")]

    # get slot instances
    rows, rows_bookable = df.to_dict(orient="records"), []
    for row in rows:
        slot = BookingSlot(
            hour=row["time"], date=date, schedule=schedule, court=row["court"]
        )
        # check is slot is in the permissible schedule for the given day
        if slot.is_bookable:
            LOGGER.debug(f"Free slot found: {slot}")
            _, _ = slots.append(slot), rows_bookable.append(row)

    return get_email_frame(rows_bookable, date, url), slots


def get_email_frame(rows, date, url):
    """ Make data-frame email-friendly. """
    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.drop("status", axis=1)
        df["date"] = date.strftime("%a %d %b %Y")
        df["url"], df["time"] = url, df["time"].astype(str).str.zfill(2) + ":00"
        df = df[["date", "time", "court", "url"]]
        df.columns = [string[0].upper() + string[1:] for string in df.columns]
    
    return df
