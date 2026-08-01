import datetime
import unittest

from bs4 import BeautifulSoup

from slots import BookingSlot, get_permissible_slots


class SlotsTests(unittest.TestCase):
    def test_booking_slot_time_and_bookable_flags(self):
        slot = BookingSlot(
            hour=18,
            date=datetime.date(2026, 8, 1),
            schedule=[17, 18, 19],
            court="court_1",
        )

        self.assertTrue(slot.is_bookable)
        self.assertEqual(slot.time, "18:00")
        self.assertEqual(slot.date, "Sat 01 Aug 2026")

    def test_get_permissible_slots_filters_schedule_and_formats_email_frame(self):
        html = """
        <div class='availability'>
          <table>
            <tbody>
              <tr>
                <td>6pm</td>
                <td>Court 1 £7 Court 2 Booked</td>
              </tr>
              <tr>
                <td>7pm</td>
                <td>Court 1 £7 Court 2 £7</td>
              </tr>
            </tbody>
          </table>
        </div>
        """

        content = BeautifulSoup(html, "lxml")
        date = datetime.date(2026, 8, 1)
        email_frame, slots = get_permissible_slots(
            content=content,
            date=date,
            schedule=[19],
            url="https://example.test/booking",
        )

        self.assertEqual(len(slots), 2)
        self.assertTrue(all(str(slot).startswith("Sat 01 Aug 2026,19") for slot in slots))
        self.assertListEqual(list(email_frame.columns), ["Date", "Time", "Url"])
        self.assertEqual(email_frame.iloc[0]["Time"], "19:00")
        self.assertEqual(email_frame.iloc[0]["Url"], "https://example.test/booking")


if __name__ == "__main__":
    unittest.main()