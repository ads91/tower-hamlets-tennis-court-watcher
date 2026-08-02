import os
import tempfile
import unittest

from data_io import load_file, save_file


class DataIoTests(unittest.TestCase):
    def test_save_and_load_json_roundtrip(self):
        payload = {
            "venue": "st-johns-park",
            "schedule": {"Sat": [10, 11]},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            save_file("cache.json", payload, io_type="os", prefix=temp_dir)
            loaded = load_file("cache.json", io_type="os", prefix=temp_dir)

            self.assertEqual(loaded, payload)

    def test_save_text_file_with_wildcard_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            save_file("debug.txt", "hello", io_type="os", prefix=temp_dir, file_type="*")
            target = os.path.join(temp_dir, "debug.txt")

            self.assertTrue(os.path.exists(target))
            with open(target, "r", encoding="utf-8") as text_file:
                self.assertEqual(text_file.read(), "hello")


if __name__ == "__main__":
    unittest.main()