import time
from bs4 import BeautifulSoup

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


URL = "https://tennistowerhamlets.com/book/courts/poplar-rec-ground/2026-05-14#book"


def build_driver():
    options = uc.ChromeOptions()

    # IMPORTANT
    options.add_argument("--headless=new")

    # Reduce automation fingerprints
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Stability
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Realistic browser fingerprint
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    )

    driver = uc.Chrome(
        options=options,
        use_subprocess=True,
    )

    return driver


driver = build_driver()

try:
    # Warm-up navigation
    driver.get("about:blank")
    time.sleep(2)

    driver.get(URL)

    # Give anti-bot scripts time
    time.sleep(5)

    print("Current URL:", driver.current_url)
    print("Title:", driver.title)

    # Save debug artifacts
    driver.save_screenshot("debug.png")

    with open("page.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)

    # Wait for booking table or venue text
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//*[contains(text(), 'Poplar Rec Ground')]"
            )
        )
    )

    # Parse rendered HTML
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Print some useful content
    text = soup.get_text("\n", strip=True)

    print("\n====================")
    print(text[:5000])
    print("====================\n")

finally:
    driver.quit()
