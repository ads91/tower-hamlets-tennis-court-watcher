import pytz
import datetime


TIMEZONE_MAP = {
    "Europe/London": pytz.timezone("Europe/London"),
    "US/Eastern": pytz.timezone("US/Eastern"),
}


class TimeZoneManager(object):

    def __init__(self, timezone, hour_offset=0):
        self.timezone = timezone
        self.offset = datetime.timedelta(hours=hour_offset)

    def now(self):
        return (datetime.datetime.utcnow() + self.offset).astimezone(pytz.timezone(self.timezone)).replace(tzinfo=None)


if __name__ == "__main__":
    tz_mgr_1 = TimeZoneManager("Europe/London", hour_offset=0)
    tz_mgr_2 = TimeZoneManager("Europe/London", hour_offset=-1)

    print(tz_mgr_1.now())
    print(tz_mgr_2.now())
