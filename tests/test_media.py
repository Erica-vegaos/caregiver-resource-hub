"""v1.0.0 synthetic media extraction and persistent attached-poster acceptance."""
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from media import extract_media_candidates
from build import apply_media_registry,validate_event

URL='https://official.example/events/1'
class MediaDiscovery(unittest.TestCase):
    def media(self,html):
        return extract_media_candidates(html,URL,'陪伴彼此',('cdn.example',))
    def test_lazy_image_and_full_size_anchor_beat_thumbnail(self):
        items=self.media('<article><a href="/poster-full.jpg"><img src="/tiny.jpg" data-src="/poster-medium.jpg" alt="陪伴彼此海報"></a></article>')
        self.assertEqual(items[0]['url'],'https://official.example/poster-full.jpg')
        self.assertTrue(items[0]['title_match']);self.assertTrue(items[0]['in_content'])
        self.assertEqual(len(items),1)
    def test_share_buttons_and_site_badges_are_excluded(self):
        items=self.media('<meta property="og:image" content="/001/Upload/FBsharelogo.jpg"><article>'
            '<img src="/TW/Images/Layout/SocialNetwork/line.png"><img src="/img/fb-icon.png">'
            '<img src="/upload/online-poster.jpg" alt="活動海報"></article>')
        self.assertEqual([i['url'] for i in items],['https://official.example/upload/online-poster.jpg'])
    def test_lazy_srcset_is_discovered_without_guessing_og_image(self):
        items=self.media('<meta property="og:image" content="/preview.jpg"><main><img src="data:image/gif;base64,xyz" data-srcset="/small.jpg 300w, /poster-large.jpg 1200w" alt="活動海報"></main>')
        self.assertEqual(items[0]['url'],'https://official.example/poster-large.jpg')
        self.assertFalse(next(x for x in items if x['kind']=='social_preview')['in_content'])
    def test_navigation_logos_tracking_and_untrusted_hosts_are_excluded(self):
        html='<header><img src="/poster.jpg"></header><article><img src="/logo.jpg"><img src="/pixel.png" width="1"><img src="https://evil.example/poster.jpg"><img src="https://cdn.example/poster.jpg"></article>'
        self.assertEqual([x['url'] for x in self.media(html)],['https://cdn.example/poster.jpg'])
    def test_direct_image_attachment_and_relative_resolution(self):
        self.assertEqual(self.media('<div id="article-content"><a href="../flyer.png" title="陪伴彼此海報">下載</a></div>')[0]['url'],'https://official.example/flyer.png')
    def test_invalid_protocols_and_credential_urls_are_rejected(self):
        self.assertEqual(self.media('<article><img src="javascript:x"><img src="file:///tmp/x.jpg"><img src="https://u:p@official.example/poster.jpg"></article>'),[])
    def test_repeated_image_url_is_deduplicated_and_candidates_are_bounded(self):
        self.assertEqual(len(self.media('<article>'+''.join('<img src="/poster%d.jpg">'%i for i in range(20))+'</article>')),10)
    def test_attached_posters_survive_refresh_and_only_match_the_correct_source(self):
        records=json.loads((ROOT/'data/events.json').read_text())['events']
        event=next(e for e in records if e['id']=='S01:54D200EE367BA9FB')
        refreshed=copy.deepcopy(event)
        for k in ('poster_asset','poster_checked_at','poster_capture_method'):
            refreshed.pop(k,None)
        apply_media_registry([refreshed]);self.assertIn('caregiver-daily',refreshed['poster_asset'])
        self.assertEqual(refreshed['fee_amount'],0)
        altered=copy.deepcopy(refreshed);altered['source_url']='https://official.example/different';altered.pop('poster_asset')
        apply_media_registry([altered]);self.assertNotIn('poster_asset',altered)
    def test_inline_poster_asset_exists_and_fee_has_image_evidence(self):
        data=json.loads((ROOT/'data/events.json').read_text())['events']
        local=[e for e in data if e.get('poster_asset')]
        self.assertEqual(len(local),2)
        for e in local:self.assertTrue((ROOT/'dist'/e['poster_asset']).is_file())
        daily=next(e for e in local if e['id']=='S01:54D200EE367BA9FB')
        self.assertTrue(any(v.get('field')=='fee' and v.get('method')=='provided_poster_review' for v in daily['evidence']))
        invalid=copy.deepcopy(daily);invalid['poster_url']='javascript:alert(1)'
        with self.assertRaises(ValueError):validate_event(invalid)

if __name__=='__main__':unittest.main()
