"""v0.1.0: synthetic safety regressions, not a claim of real-source accuracy."""
import sys
import unittest
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from build import Text, parse_taipei, parse_heart, qualify, compare, validate_url, discover, TZ, TAIPEI, HEART

WHEN='2026-11-12T20:00:00+08:00'
NOW=datetime.fromisoformat(WHEN)

def parser(raw):
    p=Text();p.feed(raw);return p

def taipei(time='115年11月22日（日）9 :30-12:30'):
    # Deliberately synthetic minimal text, not a copy of the source document.
    return parser('<h3>115年11月22日-測試家屬交流</h3><p>報名日期：115/10/20~115/11/22</p><p>活動時間：'+time+'</p><p>活動地點：測試中心四樓</p><p>🌟 活動內容 家屬交流</p><p>報名時間：即日起至額滿為止</p><p>報名方式：https://example.test</p><p>參加對象：臺北市家屬優先。 主辦單位：測試單位</p>')

def event():return parse_taipei(taipei(),TAIPEI+'TEST',WHEN,'testhash')[0]

class PipelineTests(unittest.TestCase):
    def test_roc_and_split_time(self):
        e=event();self.assertEqual(e['start'],'2026-11-22T09:30:00+08:00')
    def test_missing_fee_and_seats_stay_unknown(self):
        e=qualify(event(),NOW);self.assertIsNone(e['fee_amount']);self.assertEqual(e['registration_status'],'unknown');self.assertIn('費用未註明',e['review_reasons'])
    def test_past_not_current_year(self):
        e=parse_taipei(taipei('114年11月22日（日）9:30-12:30'),TAIPEI+'TEST',WHEN,'hash')[0]
        self.assertEqual(qualify(e,NOW)['event_status'],'ended')
    def test_missing_year_rejected(self):
        with self.assertRaises(ValueError):parse_taipei(taipei('11月22日9:30-12:30'),TAIPEI+'TEST',WHEN,'hash')
    def test_failed_source_not_cancelled(self):
        e=event();e['freshness']='unavailable';result=qualify(e,NOW);self.assertEqual(result['event_status'],'scheduled');self.assertEqual(result['freshness'],'unavailable')
    def test_stale(self):
        e=event();e['checked_at']='2026-11-01T10:00:00+08:00';self.assertEqual(qualify(e,NOW)['freshness'],'stale')
    def test_content_diff_ignores_check_timestamp(self):
        e=event();new=dict(e,checked_at='2026-11-13T10:00:00+08:00');self.assertEqual(compare([e],[new]),[])
    def test_important_change_detected(self):
        e=event();new=dict(e,venue='更正場地');self.assertIn('venue',compare([e],[new])[0]['fields'])
    def test_url_blocks_local_and_unknown_hosts(self):
        for url in ['file:///etc/passwd','http://127.0.0.1','https://example.test','https://mental-health.gov.taipei.evil.test','https://user:pw@mental-health.gov.taipei']:
            with self.assertRaises(ValueError):validate_url(url)
    def test_heart_series_explicit_evening(self):
        p=parser('<h2>115年心朋友學苑</h2><p>服務對象：臺北市家屬 服務時間：週一到週五</p><p>「心家庭暖房」限家屬.照顧者參加，每月一場，晚上6:30~8:30。11月3日、12月1日。★ 家連家精神教育</p><p>學苑地點：測試地址 心生活協會115年 簡章</p>')
        rows=parse_heart(p,HEART,WHEN,'hash');self.assertEqual(len(rows),2);self.assertEqual(rows[1]['start'],'2026-12-01T18:30:00+08:00');self.assertEqual(qualify(rows[0],NOW)['event_status'],'ended')
    def test_end_before_start_rejected(self):
        e=event();e['end']=e['start']
        with self.assertRaises(ValueError):qualify(e,NOW)
    def test_discovery_keeps_titles_without_caregiver_keywords(self):
        p=parser('<a href="Active_Content.aspx?ss=A">一起接住彼此</a><a href="Active_Content.aspx?ss=A">我要報名</a>')
        rows=discover(p,TAIPEI+'TEST');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title'],'一起接住彼此')

if __name__=='__main__':unittest.main()
