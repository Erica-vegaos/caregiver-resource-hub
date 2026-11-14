"""Synthetic list pages: discovery yields review candidates only, same host, deduplicated."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from build import Text, discover_links, validate_url, DISCOVERY

SRC = {'id': 'D-T', 'name': 't', 'list_url': 'https://www.ntcami.org.tw/events', 'link_pattern': 'civicrm/event/info'}

def page(html):
    p = Text(); p.feed(html); return p

class Discovery(unittest.TestCase):
    def test_pattern_keeps_only_matching_same_host_links(self):
        rows = discover_links(page(
            '<a href="/civicrm/event/info?id=1&reset=1">家屬聚會一</a>'
            '<a href="/civicrm/event/info?id=1&reset=1#x">家屬聚會一</a>'
            '<a href="https://evil.example/civicrm/event/info?id=2">外站活動</a>'
            '<a href="/about">關於我們的團體</a>'), SRC, set())
        self.assertEqual([r['url'] for r in rows], ['https://www.ntcami.org.tw/civicrm/event/info?id=1&reset=1'])
        self.assertEqual(rows[0]['status'], 'discovered_not_parsed')

    def test_known_urls_are_skipped(self):
        known = {'https://www.ntcami.org.tw/civicrm/event/info?id=1&reset=1'}
        self.assertEqual(discover_links(page('<a href="/civicrm/event/info?id=1&reset=1">家屬聚會一</a>'), SRC, known), [])

    def test_label_filter_without_pattern(self):
        src = {'id': 'D-K', 'name': 'k', 'list_url': 'https://www.tpmra.org.tw/'}
        rows = discover_links(page('<a href="/news/1">家屬支持團體開課</a><a href="/news/2">年度財報公告</a><a href="tel:0222">家屬專線電話</a>'), src, set())
        self.assertEqual([r['title'] for r in rows], ['家屬支持團體開課'])

    def test_configured_list_pages_are_fetchable_hosts(self):
        self.assertTrue(DISCOVERY)
        for source in DISCOVERY:
            validate_url(source['list_url'])

if __name__ == '__main__':
    unittest.main()
