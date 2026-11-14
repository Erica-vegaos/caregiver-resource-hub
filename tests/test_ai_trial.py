"""v0.1.0: budget, evidence and failure regressions; transport is mocked, no API charges."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import ai_trial as ai

NOW = datetime.fromisoformat('2026-11-14T14:00:00+08:00')
TEXT = '家屬交流：115年11月22日09:00–11:00。地點：測試中心。對象：精神疾病家屬。'


def result():
    event = dict.fromkeys(ai.FIELDS)
    event.update(title='家屬交流', date_time='115年11月22日09:00–11:00',
                 venue='測試中心', eligibility='精神疾病家屬', caregiver_eligible=True)
    return {'decision': 'ready', 'events': [event]}


def response(value=None):
    return {'status': 'completed', 'usage': {'input_tokens': 200, 'output_tokens': 150},
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value or result())}]}]}


class MemoryLedger:
    def __init__(self):
        self.data = {'version': ai.VERSION, 'entries': []}
        self.saves = 0

    def persist(self):
        self.saves += 1


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.config = ai.load_config(today=NOW.date())

    def test_verified_fixed_model_and_no_tools(self):
        body = ai.request_body(TEXT, self.config)
        self.assertEqual(body['model'], ai.MODEL)
        self.assertIs(body['store'], False)
        self.assertNotIn('tools', body)
        self.assertEqual(body['max_output_tokens'], 3000)

    def test_stale_pricing_stops_before_charge(self):
        with self.assertRaisesRegex(ValueError, 'pricing_needs_reverification'):
            ai.load_config(today=date(2026, 12, 15))

    def test_increased_budget_not_authorized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            self.config['monthly_budget_ntd'] = '301'
            path.write_text(json.dumps(self.config))
            with self.assertRaisesRegex(ValueError, 'budget_exceeds_authorization'):
                ai.load_config(path, NOW.date())

    def test_large_text_not_silently_cut(self):
        with self.assertRaisesRegex(ValueError, 'source_too_large'):
            ai.request_body('字' * 8001, self.config)

    def test_reservation_accounts_for_output_and_input(self):
        small = ai.reserve_ntd(ai.request_body(TEXT, self.config), self.config)
        large = ai.reserve_ntd(ai.request_body('字' * 8000, self.config), self.config)
        self.assertGreater(large, small)
        self.assertGreater(small, Decimal('.60'))

    def test_budget_stops_before_transport(self):
        ledger = MemoryLedger()
        ledger.data['entries'] = [{'key': 'old', 'month': '2026-11', 'reserved_ntd': '300'}]
        with self.assertRaisesRegex(ValueError, 'monthly_budget_exhausted'):
            ai.run_one('https://example.org', TEXT, ledger, self.config,
                       transport=lambda *_: self.fail('must not call API'), now=NOW)
        self.assertEqual(ledger.saves, 0)

    def test_month_boundaries_use_taipei(self):
        ledger = MemoryLedger()
        ledger.data['entries'] = [{'key': 'oct', 'month': '2026-10', 'reserved_ntd': '300'}]
        ai.reserve(ledger, 'nov', Decimal('1'), self.config,
                   datetime.fromisoformat('2026-10-31T16:01:00+00:00'))
        self.assertEqual(ledger.data['entries'][-1]['month'], '2026-11')

    def test_lifetime_trial_limit_survives_month_reset(self):
        ledger = MemoryLedger()
        ledger.data['entries'] = [{'key': str(i), 'month': '2026-10', 'reserved_ntd': '1'} for i in range(20)]
        with self.assertRaisesRegex(ValueError, 'trial_request_limit'):
            ai.reserve(ledger, 'new', Decimal('1'), self.config, NOW)

    def test_remote_reservation_required_before_transport(self):
        ledger = MemoryLedger()
        def fail_save():
            raise RuntimeError('remote unavailable')
        ledger.persist = fail_save
        with self.assertRaises(RuntimeError):
            ai.run_one('https://example.org', TEXT, ledger, self.config,
                       transport=lambda *_: self.fail('must not call API'), now=NOW)

    def test_success_has_usage_but_does_not_refund_reservation(self):
        ledger = MemoryLedger()
        def transport(*_):
            self.assertEqual(ledger.saves, 1)
            return response()
        report = ai.run_one('https://example.org', TEXT, ledger, self.config, transport, NOW)
        self.assertEqual(report['status'], 'extracted_for_evaluation')
        entry = ledger.data['entries'][0]
        self.assertEqual(entry['status'], 'completed')
        self.assertGreater(Decimal(entry['reserved_ntd']), Decimal(entry['estimated_actual_usd']) * 45)

    def test_unchanged_content_cached_across_runs(self):
        ledger = MemoryLedger()
        ai.run_one('https://example.org', TEXT, ledger, self.config, lambda *_: response(), NOW)
        report = ai.run_one('https://example.org', TEXT, ledger, self.config,
                            lambda *_: self.fail('duplicate charge'), NOW)
        self.assertEqual(report['status'], 'cached_no_charge')

    def test_changed_source_reprocessed(self):
        ledger = MemoryLedger()
        for text in (TEXT, TEXT + '更正公告'):
            ai.run_one('https://example.org', text, ledger, self.config, lambda *_: response(), NOW)
        self.assertEqual(len(ledger.data['entries']), 2)

    def test_timeout_keeps_reservation_and_does_not_retry(self):
        ledger = MemoryLedger()
        def timeout(*_):
            raise TimeoutError('sk-secret-sentinel')
        report = ai.run_one('https://example.org', TEXT, ledger, self.config, timeout, NOW)
        self.assertNotIn('sk-secret', json.dumps(report))
        self.assertEqual(ledger.data['entries'][0]['status'], 'failed_reserved')
        retry = ai.run_one('https://example.org', TEXT, ledger, self.config,
                           lambda *_: self.fail('timeout must not auto-retry'), NOW)
        self.assertEqual(retry['status'], 'cached_no_charge')

    def test_model_must_quote_actual_source(self):
        value = result()
        value['events'][0]['fee'] = '免費'
        with self.assertRaisesRegex(ValueError, 'quote_not_in_source:fee'):
            ai.validate_result(response(value), TEXT)

    def test_null_fee_remains_null(self):
        parsed = ai.validate_result(response(), TEXT)
        self.assertIsNone(parsed['events'][0]['fee'])
        self.assertIsNone(parsed['events'][0]['registration'])

    def test_staff_not_family(self):
        value = result()
        value['events'][0]['eligibility'] = '家屬支持服務工作人員'
        with self.assertRaisesRegex(ValueError, 'eligibility_not_verified'):
            ai.validate_result(response(value), TEXT + '家屬支持服務工作人員')

    def test_incomplete_refusal_and_malformed_json(self):
        for value in ({'status': 'incomplete'}, {'status': 'completed', 'output': []}):
            with self.assertRaises(ValueError):
                ai.validate_result(value, TEXT)

    def test_unexpected_usage_halts_future_requests(self):
        ledger = MemoryLedger()
        value = response()
        value['usage']['output_tokens'] = 1000000
        report = ai.run_one('https://example.org', TEXT, ledger, self.config, lambda *_: value, NOW)
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(ledger.data['halted'])

    def test_missing_ledger_cannot_reset_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['git', 'init', '-b', ai.STATE_BRANCH, tmp], capture_output=True, check=True)
            with self.assertRaises(FileNotFoundError):
                with ai.GitLedger(tmp):
                    self.fail('must not initialize automatically')

    def test_stale_parallel_checkout_cannot_spend_before_successful_push(self):
        def git(*args):
            return subprocess.run(['git', *map(str, args)], capture_output=True, check=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, first, stale = [root / name for name in ('remote.git', 'first', 'stale')]
            git('init', '--bare', remote)
            git('clone', remote, first)
            git('-C', first, 'checkout', '-b', ai.STATE_BRANCH)
            (first / 'state.json').write_text(json.dumps({'version': ai.VERSION, 'entries': []}))
            git('-C', first, 'add', 'state.json')
            git('-C', first, '-c', 'user.name=test', '-c', 'user.email=test@example.org', 'commit', '-m', 'initial ledger')
            git('-C', first, 'push', 'origin', ai.STATE_BRANCH)
            git('clone', '-b', ai.STATE_BRANCH, remote, stale)
            with ai.GitLedger(first) as ledger:
                ai.reserve(ledger, 'first', Decimal('1'), self.config, NOW)
            with ai.GitLedger(stale) as ledger:
                with self.assertRaises(subprocess.CalledProcessError):
                    ai.run_one('https://example.org', TEXT, ledger, self.config,
                               lambda *_: self.fail('must not spend with stale budget'), NOW)


if __name__ == '__main__':
    unittest.main()
