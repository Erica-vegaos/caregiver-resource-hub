"""v1.0.0: independent acceptance cases for family audience and shipped records."""
import json
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from build import Text, TAIPEI, parse_taipei


def page(audience):
    parser = Text()
    parser.feed(
        '<h3>115年11月22日-家屬溝通技巧講座</h3>'
        '<p>活動時間：115年11月22日（日）9:30-12:30</p>'
        '<p>活動地點：測試會議室</p><p>🌟 活動內容：家屬溝通。</p>'
        '<p>報名時間：即日起至額滿為止</p><p>報名方式：請洽主辦。</p>'
        '<p>參加對象：' + audience + ' 主辦單位：測試單位</p>'
    )
    return parser


class FamilyAudienceAcceptance(unittest.TestCase):
    def assert_not_accepted(self, audience):
        with self.assertRaises(ValueError):
            parse_taipei(page(audience), TAIPEI + 'QA', '2026-11-14T10:00:00+08:00', 'qa')

    def test_professional_course_about_family_is_not_family_event(self):
        self.assert_not_accepted('限精神科醫師及護理師。')

    def test_explicit_family_exclusion_is_not_family_event(self):
        self.assert_not_accepted('僅限專業人員，不開放家屬參加。')

    def test_negative_family_phrase_is_not_positive_eligibility(self):
        self.assert_not_accepted('精神康復者本人，不含家屬。')

    def test_family_before_negative_instruction_is_not_eligible(self):
        self.assert_not_accepted('限醫師，家屬請勿報名。')

    def test_family_not_applicable_is_not_eligible(self):
        self.assert_not_accepted('精神康復者本人，家屬不適用。')

    def test_family_service_staff_is_not_family_audience(self):
        self.assert_not_accepted('僅限家屬支持服務工作人員。')

    def test_family_priority_does_not_become_a_residence_prohibition(self):
        event = parse_taipei(page('臺北市精障者家屬優先。'), TAIPEI + 'QA',
                             '2026-11-14T10:00:00+08:00', 'qa')[0]
        self.assertTrue(event['caregiver_eligible'])
        self.assertIn('優先', event['eligibility'])
        self.assertNotIn('限臺北市', event['eligibility'])


class ShippedSnapshotAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / 'data/events.json').read_text())

    def test_each_displayed_event_has_family_evidence(self):
        for event in self.payload['events']:
            with self.subTest(event=event['id']):
                self.assertIs(event.get('caregiver_eligible'), True)
                eligibility = [e['quote'] for e in event.get('evidence', [])
                               if e.get('field') == 'eligibility']
                self.assertTrue(eligibility, 'Missing eligibility evidence')
                self.assertRegex(' '.join(eligibility), r'家屬|照顧者|家人|家庭')

    def test_dates_have_explicit_timezones_and_positive_duration(self):
        for event in self.payload['events']:
            with self.subTest(event=event['id']):
                start, end = (datetime.fromisoformat(event[k]) for k in ('start', 'end'))
                self.assertIsNotNone(start.utcoffset())
                self.assertIsNotNone(end.utcoffset())
                self.assertGreater(end, start)

    def test_same_source_occurrence_not_duplicated(self):
        occurrences = set()
        for event in self.payload['events']:
            key = (event['source_url'], event['start'], event['title'])
            self.assertNotIn(key, occurrences, event['id'])
            occurrences.add(key)


if __name__ == '__main__':
    unittest.main()
