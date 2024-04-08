import datetime

from bs4 import BeautifulSoup
from utils.utils import get_chrome_driver, extract_site_contents


def book(date, time):
    # content = """
        # <input type="checkbox" class="bookable" name="courts[]" value="255_167_2024-04-09_15:00" data-price="4" data-concession="4">
        # <input type="checkbox" class="bookable" name="courts[]" value="255_168_2024-04-09_16:00" data-price="6" data-concession="6">
        # <input type="checkbox" class="bookable" name="courts[]" value="255_169_2024-04-09_17:00" data-price="8" data-concession="8">
    # """
    # Format time for look-up
    time_string = str(time) + ":00"

    # Spin up driver
    driver = get_chrome_driver(
        url="https://tennistowerhamlets.com/book/courts/st-johns-park/2024-04-09#book",
        driver_path="",
        sleep=1
    )

    # Extract HTML
    content = extract_site_contents(
        chrome_driver=driver, sleep=1
    )

    # Search the HTML for a unique identifier we'd associate with an available slot
    lookup = date.strftime("%Y-%m-%d") + "_" + time_string

    # Use a CSS selector to find elements containing the substring in the value attribute
    selected_elements = content.select('input[value*="{}"]'.format(lookup))

    # Add the slot to the cart
    for element in selected_elements:
        # Get the button (from the parent element) and click it
        button = element.parent.find(name="span", attrs={"class": "button available"})
        button.click()


if __name__ == "__main__":
    book(
        date=datetime.date(2024, 4, 9), time=15
    )
