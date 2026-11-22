import json
import unittest
from sync_sheets import convert, validate_row, HEADERS


class SyncValidationTests(unittest.TestCase):
    def setUp(self):
        self.row = [''] * 26
        self.row[:10] = ['F02-03', 'Lampegat', '恩荷芬嘉年華', 'Eindhoven Carnival', 'Eindhoven', 'Noord-Brabant', '2–3月', 'festival', '傳統與民俗,地方特色慶典', 'https://example.org']
        self.row[14] = '已確認'
        self.row[17:26] = ['2027-02-06', '2027-02-09', 'confirmed', '', '', '遊行', 'Parade', '中文備註', 'English note']

    def test_approved_row(self):
        v = validate_row(self.row, 2)
        self.assertEqual(v['start'], '2027-02-06')
        self.assertEqual(v['highlightEn'], 'Parade')

    def test_bad_date_rejected(self):
        self.row[17] = '2027-02-30'
        with self.assertRaises(ValueError): validate_row(self.row, 2)

    def test_missing_english_rejected(self):
        self.row[25] = ''
        with self.assertRaises(ValueError): validate_row(self.row, 2)

    def test_new_approved_id_allowed(self):
        self.row[0] = 'F06-03'
        self.assertEqual(validate_row(self.row, 2)['id'], 'F06-03')

    def test_unapproved_excluded(self):
        self.row[14] = '待審核'
        with self.assertRaises(ValueError): convert([['ID'] + [''] * 13 + ['人工審核狀態'] + [''] * 2 + HEADERS, self.row])

    def test_weekly_rules(self):
        self.row[19] = 'weeklyFri'
        self.row[20] = 'FRI;TUE@07-08'
        self.assertEqual(len(validate_row(self.row, 2)['weeklyRules']), 2)

    def test_seasonal_without_dates(self):
        self.row[0] = 'S03-03'
        self.row[7] = 'seasonal'
        self.row[17:22] = ['', '', 'seasonal', '', '3,4']
        self.assertEqual(validate_row(self.row, 2)['seasonMonths'], [3,4])


if __name__ == '__main__': unittest.main()
