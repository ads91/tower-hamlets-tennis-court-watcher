import datetime
import importlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup


def import_main_for_tests():
    os.environ["APP_ENVIRONMENT"] = "LOC"
    os.environ["CONFIG_EXTRAS"] = ".st_johns_park"

    import cfg.cfg as cfg_module
    importlib.reload(cfg_module)

    import data_io

    original_load_file = data_io.load_file

    def stub_load_file(item, *args, **kwargs):
        if item == "auth.json":
            return {"emails": {"address": "sender@example.com", "password": "password"}}
        if item.startswith("emails"):
            return {
                "slot_available": ["slot@example.com"],
                "sys_errors": ["ops@example.com"],
            }
        return original_load_file(item, *args, **kwargs)

    with patch("data_io.load_file", side_effect=stub_load_file):
        if "main" in sys.modules:
            del sys.modules["main"]
        return importlib.import_module("main")


class FakeDriver:
    def __init__(self, page_source="", current_url="https://example.test"):
        self.page_source = page_source
        self.current_url = current_url
        self.requested_urls = []

    def get(self, url):
        self.requested_urls.append(url)

    def save_screenshot(self, path):
        with open(path, "wb") as screenshot_file:
            screenshot_file.write(b"fake-image")
        return True


class MainMonitoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = import_main_for_tests()

    def test_classify_booking_page_reports_expected_states(self):
        date_value = datetime.date(2026, 8, 8)

        matched = BeautifulSoup(
            "<input name='selected_date' value='2026-08-08'/>",
            "lxml",
        )
        classification, details = self.main.classify_booking_page(matched, date_value)
        self.assertEqual(classification, self.main.PageClassification.DATE_MATCHED)
        self.assertEqual(details["observed_date"], "2026-08-08")

        mismatched = BeautifulSoup(
            "<input name='selected_date' value='2026-08-09'/>",
            "lxml",
        )
        classification, details = self.main.classify_booking_page(mismatched, date_value)
        self.assertEqual(classification, self.main.PageClassification.DATE_MISMATCH)
        self.assertEqual(details["expected_date"], "2026-08-08")

        closed = BeautifulSoup(
            "<p class='closed'>No booking available</p>",
            "lxml",
        )
        classification, _ = self.main.classify_booking_page(closed, date_value)
        self.assertEqual(classification, self.main.PageClassification.CLOSED_FOR_BOOKING)

        missing = BeautifulSoup("<html><body></body></html>", "lxml")
        classification, _ = self.main.classify_booking_page(missing, date_value)
        self.assertEqual(classification, self.main.PageClassification.MISSING_SELECTED_DATE)

    def test_get_wait_interval_supports_randomized_jitter(self):
        with patch.object(self.main, "get_wait_time", return_value=60):
            self.main.POLLING_RANDOMIZE = True
            self.main.POLLING_JITTER_RATIO = 0.25
            self.main.POLLING_MIN_WAIT_SECONDS = None
            self.main.POLLING_MAX_WAIT_SECONDS = None
            self.main.POLLING_RANDOM.seed(11)
            wait_interval = self.main.get_wait_interval(60)

        self.assertGreaterEqual(wait_interval, 45)
        self.assertLessEqual(wait_interval, 75)

    def test_capture_failure_diagnostics_writes_expected_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.main.DIAGNOSTICS_ENABLED = True
            self.main.DIAGNOSTICS_DIR = temp_dir

            driver = FakeDriver(page_source="<html><body>hello</body></html>")
            error = RuntimeError("boom")
            diagnostics = self.main.capture_failure_diagnostics(
                driver=driver,
                context="test_capture",
                exception=error,
                extra={"cycle_count": 5},
            )

            self.assertIn("screenshot", diagnostics)
            self.assertIn("html", diagnostics)
            self.assertIn("metadata", diagnostics)
            for path in diagnostics.values():
                self.assertTrue(os.path.exists(path), msg=f"Missing artifact at {path}")

            with open(diagnostics["metadata"], "r", encoding="utf-8") as metadata_file:
                metadata = json.load(metadata_file)
            self.assertEqual(metadata["exception"]["type"], "RuntimeError")
            self.assertEqual(metadata["extra"]["cycle_count"], 5)

    def test_prune_cache_removes_expired_and_old_items(self):
        fixed_now = datetime.datetime(2026, 8, 1, 12, 0)
        stale_slot = (fixed_now - datetime.timedelta(hours=2)).strftime("%a %d %b %Y,%H:%M")
        old_notification_slot = (fixed_now + datetime.timedelta(hours=3)).strftime("%a %d %b %Y,%H:%M")
        fresh_slot = (fixed_now + datetime.timedelta(hours=4)).strftime("%a %d %b %Y,%H:%M")

        cache = {
            stale_slot: (fixed_now - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            old_notification_slot: (fixed_now - datetime.timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S"),
            fresh_slot: (fixed_now - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        }

        with patch.object(self.main.cfg.TIME_ZONE_MANAGER, "now", return_value=fixed_now):
            self.main.prune_cache(cache, notification_cool_down=12, save=False)

        self.assertEqual(len(cache), 1)
        remaining_key = list(cache.keys())[0]
        self.assertEqual(remaining_key, fresh_slot)

    def test_reload_content_returns_content_when_date_matches(self):
        expected_date = datetime.date(2026, 8, 9)
        mismatched = BeautifulSoup(
            "<input name='selected_date' value='2026-08-08'/>",
            "lxml",
        )
        matched = BeautifulSoup(
            "<input name='selected_date' value='2026-08-09'/>",
            "lxml",
        )

        driver = FakeDriver()

        with patch.object(self.main, "CHROME_MAX_QUERY_ATTEMPTS", 3), patch.object(
            self.main,
            "extract_site_contents",
            side_effect=[mismatched, matched],
        ):
            content = self.main.reload_content(
                driver=driver,
                url="https://example.test",
                date=expected_date,
                sleep=0,
                reload_interval=2,
            )

        self.assertIsNotNone(content)
        self.assertEqual(driver.requested_urls[0], "https://example.test")

    def test_reload_content_returns_none_when_booking_closed(self):
        expected_date = datetime.date(2026, 8, 9)
        closed = BeautifulSoup("<p class='closed'>No booking available</p>", "lxml")
        driver = FakeDriver()

        with patch.object(self.main, "extract_site_contents", return_value=closed):
            content = self.main.reload_content(
                driver=driver,
                url="https://example.test",
                date=expected_date,
                sleep=0,
                reload_interval=2,
            )

        self.assertIsNone(content)


if __name__ == "__main__":
    unittest.main()