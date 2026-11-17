"""v1.0.0: publication gates, repeated occurrences and build integration regressions."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build
from test_pipeline import event, NOW, WHEN, parser, taipei


class PublicationGateTests(unittest.TestCase):
    def test_invalid_record_is_quarantined_without_dropping_valid(self):
        good = event()
        bad = dict(good, id='bad', start='not-a-date')
        events, quarantine, _ = build.prepare_events([bad, good], NOW)
        self.assertEqual([e['id'] for e in events], [good['id']])
        self.assertEqual(quarantine[0]['id'], 'bad')
        self.assertEqual(quarantine[0]['publication_status'], 'quarantined')

    def test_missing_timezone_rejected(self):
        for field in ('start', 'end', 'checked_at'):
            e = event(); e[field] = e[field][:19]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'timezone_required'):
                build.qualify(e, NOW)

    def test_future_check_does_not_impersonate_verified_source(self):
        e = event(); e['checked_at'] = (NOW + timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, 'check_timestamp_in_future'):
            build.qualify(e, NOW)

    def test_eligibility_boolean_and_evidence_are_required(self):
        for update in ({'caregiver_eligible': 'true'}, {'caregiver_eligible': False}, {'evidence': []}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                build.validate_event(dict(event(), **update))
        e = event(); e['evidence'] = [x for x in e['evidence'] if x['field'] != 'eligibility']
        with self.assertRaisesRegex(ValueError, 'missing_eligibility_evidence'):
            build.validate_event(e)

    def test_professional_and_negative_audience_not_published(self):
        for text in ('僅限專業人員，討論家屬溝通', '不開放家屬參加', '僅限精神科醫師，家屬議題研討'):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'eligibility_not_verified'):
                build.validate_event(dict(event(), eligibility=text))
        p = taipei(); p.parts = [x.replace('臺北市家屬優先。', '限精神科醫師。') for x in p.parts]
        with self.assertRaisesRegex(ValueError, 'eligibility_not_verified'):
            build.parse_taipei(p, build.TAIPEI+'TEST', WHEN, 'hash')

    def test_private_and_credential_urls_rejected_even_in_evidence(self):
        for url in ('https://127.0.0.1/path', 'https://10.0.0.2/path', 'https://localhost/path',
                    'javascript:alert(1)', 'https://user:pass@example.org/a', 'https://example.org/\npath'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                build.validate_event(dict(event(), source_url=url))
        e = event(); e['evidence'][0]['url'] = 'file:///etc/passwd'
        with self.assertRaises(ValueError):
            build.validate_event(e)

    def test_unknown_fee_and_seats_remain_unknown_and_visible(self):
        e = build.qualify(event(), NOW)
        self.assertIsNone(e['fee_amount'])
        self.assertEqual(e['registration_status'], 'unknown')
        self.assertEqual(e['publication_status'], 'listed_with_caveats')

    def test_same_day_date_only_accepted_without_claiming_time(self):
        e = dict(event(), date_precision='date', start='2026-12-01', end='2026-12-01')
        result = build.qualify(e, NOW)
        self.assertEqual(result['date_precision'], 'date')
        self.assertEqual(result['start'], '2026-12-01T00:00:00+08:00')
        self.assertIn('原文僅確認活動日期，時間請洽原單位', result['review_reasons'])

    def test_series_occurrences_stay_separate_duplicate_newest_wins(self):
        e = event()
        newer = dict(e, id='different-id', checked_at=(NOW + timedelta(minutes=1)).isoformat())
        next_week = dict(e, id='next-week', start='2026-11-29T09:30:00+08:00', end='2026-11-29T12:30:00+08:00')
        result, duplicates = build.deduplicate([e, next_week, newer])
        self.assertEqual([x['id'] for x in result], ['different-id', 'next-week'])
        self.assertEqual(duplicates[0]['id'], e['id'])

    def test_unavailable_stays_distinct_after_seventy_two_hours(self):
        e = dict(event(), freshness='unavailable', checked_at=(NOW-timedelta(days=10)).isoformat())
        self.assertEqual(build.qualify(e, NOW)['freshness'], 'unavailable')


class BuildIntegrationTests(unittest.TestCase):
    def fixture(self, root):
        (root/'data').mkdir(); (root/'templates').mkdir(); (root/'src').mkdir()
        (root/'templates/index.html').write_text('<script>__SEARCH_JS__</script><script id="data">__DATA_JSON__</script>')
        (root/'src/search.cjs').write_text('const searchEngine = true;')
        def put(name, value):
            (root/'data'/name).write_text(json.dumps(value))
        e = event()
        put('events.json', {'events': [e], 'sources': []})
        put('manual_records.json', {'events': [], 'sources': [], 'resources': []})
        national = dict(e, id='national:1', city='高雄市', title='高雄家屬團體', source_id='N1',
                        source_url='https://www.example.org/event/1', start='2026-12-01T09:00:00+08:00', end='2026-12-01T11:00:00+08:00')
        put('national_records.json', {'events': [national], 'sources': [{'id':'N1','name':'測試單位','status':'manual'}]})
        put('source_registry.json', {'sources': [{'id':'R1','name':'名錄入口','city':'高雄市','url':'https://www.example.org','status':'directory','note':'測試'}]})
        return e

    def test_offline_overlays_national_and_embeds_search_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); e = self.fixture(root)
            with patch.object(build, 'ROOT', root), patch.object(build, 'fetch', side_effect=AssertionError('network forbidden')):
                result = build.build(now=NOW)
                again = build.build(now=NOW)
            payload = json.loads((root/'data/events.json').read_text())
            self.assertEqual(result['events'], 2)
            self.assertEqual(again['events'], 2)
            self.assertEqual(payload['source_registry'][0]['id'], 'R1')
            self.assertEqual(payload['events'][1]['city'], '高雄市')
            self.assertIn('const searchEngine', (root/'dist/index.html').read_text())
            self.assertNotIn('__SEARCH_JS__', (root/'dist/index.html').read_text())
            self.assertEqual(payload['events'][0]['checked_at'], e['checked_at'])

    def test_refresh_failure_retains_last_good_and_national_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); e = self.fixture(root)
            source = {'id':'S01','name':'測試已設定來源','list_url':None,'seeds':[e['source_url']]}
            with patch.object(build, 'ROOT', root), patch.object(build, 'SOURCES', [source]), patch.object(build, 'fetch', side_effect=OSError('unavailable')):
                result = build.build(refresh=True, now=NOW)
            payload = json.loads((root/'data/events.json').read_text())
            self.assertEqual(result['events'], 2)
            fallback = next(x for x in payload['events'] if x['id'] == e['id'])
            self.assertEqual(fallback['checked_at'], e['checked_at'])
            self.assertEqual(fallback['freshness'], 'unavailable')
            self.assertEqual(fallback['event_status'], 'scheduled')
            self.assertEqual(payload['sources'][0]['status'], 'failed')

    def test_taken_down_page_of_ended_event_is_not_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); e = self.fixture(root)
            ended = dict(e, event_status='ended')
            (root/'data/events.json').write_text(json.dumps({'events': [ended], 'sources': []}))
            source = {'id':'S01','name':'測試已設定來源','list_url':None,'seeds':[e['source_url']]}
            with patch.object(build, 'ROOT', root), patch.object(build, 'SOURCES', [source]), \
                 patch.object(build, 'fetch', side_effect=ValueError('template_or_audience_not_recognized')):
                build.build(refresh=True, now=NOW)
            state = json.loads((root/'data/events.json').read_text())['sources'][0]
            self.assertEqual(state['status'], 'success')
            self.assertEqual(state['errors'], [])
            self.assertEqual(state['retired_seeds'], [e['source_url']])

    def test_invalid_curated_override_cannot_leak_snapshot_old_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); e=self.fixture(root)
            (root/'data/national_records.json').write_text(json.dumps({'events':[dict(e,caregiver_eligible=False)],'sources':[]}))
            with patch.object(build, 'ROOT', root):
                result=build.build(now=NOW)
            self.assertEqual(result['events'],0)
            self.assertEqual(result['quarantined'],1)


if __name__ == '__main__':
    unittest.main()
