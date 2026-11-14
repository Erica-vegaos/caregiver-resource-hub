"""v1.0.0: nationwide curated records, validation quarantine and standalone build. No scheduler.

Changes: optional national records/registry; fail-closed validation; occurrence dedup;
source failures retain timestamps; offline builds do not refresh source checks.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import ipaddress
import unicodedata
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qs
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('Asia/Taipei')
VERSION = '1.1.0'
HOSTS = {'mental-health.gov.taipei', 'www.heartlife.org.tw'}
TAIPEI = 'https://mental-health.gov.taipei/Active_Content.aspx?n=6CCBECECB36BFE4E&ss='
HEART = 'https://www.heartlife.org.tw/TW/NewsGallery/ugC_NewsGallery_Detail.asp?hidNewsGalleryCatID=3&hidNewsGalleryID=308'
SOURCES = [
    {'id': 'S01', 'name': '臺北市社區心理衛生中心', 'mode': 'http', 'list_url': 'https://mental-health.gov.taipei/ActiveList.aspx?n=6CCBECECB36BFE4E&sms=F62510C10F2670B1', 'seeds': [TAIPEI+'54D200EE367BA9FB', TAIPEI+'C6AD3B6D5810F476']},
    {'id': 'S05', 'name': '台北市心生活協會', 'mode': 'http', 'list_url': None, 'seeds': [HEART]},
]

class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.headers = [], [], []
        self.skip = 0
        self.link, self.header = None, None
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript'): self.skip += 1
        if tag == 'a': self.link = [dict(attrs).get('href',''), []]
        if tag in ('h2','h3'): self.header = [tag, []]
    def handle_endtag(self, tag):
        if tag in ('script','style','noscript'): self.skip = max(0,self.skip-1)
        if tag == 'a' and self.link:
            self.links.append((self.link[0], ''.join(self.link[1]).strip())); self.link = None
        if tag in ('h2','h3') and self.header:
            self.headers.append(''.join(self.header[1]).strip()); self.header = None
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)
            if self.link: self.link[1].append(data)
            if self.header: self.header[1].append(data)
    @property
    def text(self): return re.sub(r'\s+', ' ', ' '.join(self.parts)).strip()

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        if '/.within.website/' in newurl: raise ValueError('anti_bot_redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def validate_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname not in HOSTS or p.port not in (None,443) or p.username or p.password:
        raise ValueError('url_not_allowed')

def fetch(url):
    validate_url(url)
    req = urllib.request.Request(url, headers={'User-Agent': 'CaregiverResourceHub-Research/0.1 (manual read-only prototype)'})
    with urllib.request.build_opener(SafeRedirect()).open(req, timeout=20) as response:
        if 'text/html' not in response.headers.get('Content-Type',''): raise ValueError('unexpected_content_type')
        raw = response.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('body_too_large')
        doc = raw.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
    parser = Text(); parser.feed(doc)
    lowered = parser.text.lower()
    if any(term in lowered for term in ['making sure you\'re not a bot','anubis','captcha','access denied']): raise ValueError('challenge_or_access_denied')
    if len(parser.text)<120: raise ValueError('missing_body')
    return parser, hashlib.sha256(raw).hexdigest()

def year(value):
    n=int(value)
    return n+1911 if n<1911 else n

def stamp(y,m,d,h,minute):
    return datetime(year(y),int(m),int(d),int(h),int(minute),tzinfo=TZ).isoformat()

def evidence(field, raw, url, checked, digest, locator='正文'):
    return {'field':field,'quote':raw.strip(),'url':url,'checked_at':checked,'content_hash':digest,'locator':locator}

def base(source, sid, title, url, checked, digest):
    return {'id':sid,'source_id':source['id'],'source_event_id':sid.split(':')[-1], 'title':title,'organizer':source['name'],
        'source_url':url,'source_published_at':None,'source_modified_at':None,'last_successful_fetch_at':checked,
        'last_content_checked_at':checked,'checked_at':checked,'check_method':'http_rules','content_hash':digest,
        'parser_version':VERSION,'city':'台北市','mode':'實體','audience':'家屬／照顧者','caregiver_eligible':True,
        'fee_amount':None,'fee_text':'原文未註明','registration_status':'unknown','event_status':'scheduled',
        'publication_status':'pending','registration_deadline':None,'evidence':[], 'notes':[], 'review_reasons':[], 'freshness':'fresh'}

def parse_taipei(parser, url, checked, digest):
    text=parser.text
    title=next((h for h in parser.headers if re.match(r'\d+年\d+月\d+日',h)), None)
    if not title or not re.search('家屬|照顧者', text): raise ValueError('template_or_audience_not_recognized')
    fields={}
    patterns={
        'time':r'活動時間\s*[：:]\s*(.+?)\s*活動地點',
        'venue':r'活動地點\s*[：:]\s*(.+?)(?=🌟|活動內容)',
        'eligibility':r'參加對象\s*[：:]\s*(.+?)\s*主辦單位',
        'registration':r'報名時間\s*[：:]\s*(.+?)\s*報名方式',
    }
    for key,pattern in patterns.items():
        match=re.search(pattern,text)
        if not match: raise ValueError('missing_required_block:'+key)
        fields[key]=match.group(1).strip()
    validate_eligibility(fields['eligibility'])
    times=re.search(r'(\d+)年(\d+)月(\d+)日.*?(\d+)\s*:\s*(\d+)\s*[-~～]\s*(\d+)\s*:\s*(\d+)',fields['time'])
    if not times: raise ValueError('unrecognized_event_time')
    y,m,d,h,mi,eh,emi=times.groups()
    source=SOURCES[0];sid=parse_qs(urlsplit(url).query)['ss'][0]
    event=base(source,'S01:'+sid,re.sub(r'^\d+年\d+月\d+日\s*[-－]?','',title),url,checked,digest)
    event.update({'start':stamp(y,m,d,h,mi),'end':stamp(y,m,d,eh,emi),'category':'講座與交流','venue':fields['venue'],
        'eligibility':fields['eligibility'],'registration_text':fields['registration'], 'contact':'請見原單位公告',
        'summary':'與有相似照顧經驗的家屬交流，認識支持資源，也為自己留一段被理解的時間。',
        'notes':['臺北市居住家屬優先，優先資格不等於其他地區一定不能參加。','名額及費用請向原單位確認。']})
    # Date windows and an application button are not evidence of remaining seats.
    event['evidence']=[evidence(k,v,url,checked,digest) for k,v in fields.items()]
    if '額滿' in fields['registration']: event['notes'].append('原文寫至額滿為止，本入口沒有剩餘名額資料。')
    return [event]

def parse_heart(parser,url,checked,digest):
    text=parser.text
    if '115年心朋友學苑' not in text: raise ValueError('template_not_recognized')
    match=re.search(r'「心家庭暖房」(.+?)(?=★|家連家精神)',text)
    if not match: raise ValueError('missing_series_block')
    block=match.group(1)
    if not re.search(r'限家屬.*照顧者',block): raise ValueError('eligibility_not_verified')
    dates=re.findall(r'(\d+)\s*月\s*(\d+)\s*日',block)
    time=re.search(r'晚上\s*(\d+)\s*:\s*(\d+)\s*[~～-]\s*(\d+)\s*:\s*(\d+)',block)
    venue=re.search(r'學苑地點\s*[：:]\s*(.+?)(?=心生活協會115年|檔案下載)',text)
    eligibility=re.search(r'服務對象\s*[：:]\s*(.+?)\s*服務時間',text)
    if not dates or not time or not venue or not eligibility: raise ValueError('missing_series_fields')
    h,mi,eh,emi=time.groups()
    # The explicit year and evening qualifier are required; no current-year fallback.
    y=2026;start_h=int(h)+12 if int(h)<12 else int(h);end_h=int(eh)+12 if int(eh)<12 else int(eh)
    results=[]
    for m,d in dates:
        event=base(SOURCES[1],'S05:308:'+f'{y}-{int(m):02}-{int(d):02}','心家庭暖房・家屬每月聚會',url,checked,digest)
        event.update({'series_id':'S05:308:warmroom','source_event_id':'308','start':stamp(y,m,d,start_h,mi),'end':stamp(y,m,d,end_h,emi),
            'category':'支持團體','venue':venue.group(1).strip(),'eligibility':eligibility.group(1).strip()+'；心家庭暖房限家屬／照顧者。',
            'registration_text':'請先向心家庭專線確認本場次的參加方式。','contact':'02-2739-8516','contact_verified':False,
            'summary':'為精神疾病家屬留下的每月交流空間，與有相似經驗的人分享日常。',
            'notes':['系列活動是否接受單場或中途加入，請先向單位確認。','時間依原文晚上 6:30–8:30 換算；未確認報名名額。']})
        event['evidence']=[evidence('date',f'115年度；{m}月{d}日',url,checked,digest),evidence('time',time.group(0),url,checked,digest),
            evidence('eligibility',eligibility.group(1).strip()+'；限家屬.照顧者參加',url,checked,digest),evidence('venue',venue.group(1),url,checked,digest)]
        results.append(event)
    return results

def aware_datetime(value, field):
    if not isinstance(value, str):
        raise ValueError('invalid_datetime:' + field)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid_datetime:' + field) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('timezone_required:' + field)
    return parsed


def public_https_url(url):
    """Validate display/evidence URLs only; fetching still uses the strict HOSTS allowlist."""
    if not isinstance(url, str):
        raise ValueError('invalid_source_url')
    try:
        p = urlsplit(url)
        host = (p.hostname or '').lower().rstrip('.')
        port = p.port
    except ValueError as exc:
        raise ValueError('invalid_source_url') from exc
    if url.strip() != url or any(ord(c) < 32 for c in url):
        raise ValueError('invalid_source_url')
    if p.scheme != 'https' or not host or p.username or p.password or port not in (None, 443):
        raise ValueError('invalid_source_url')
    if '.' not in host or host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid')):
        raise ValueError('nonpublic_source_url')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError('nonpublic_source_url')
    return url


def validate_eligibility(text):
    # '家屬支持服務工作人員' describes staff, not a family participant.
    audience_text = re.sub(r'(?:家屬|照顧者|親友|陪伴者)[^，,。；;、與及和]{0,12}(?:工作人員|專業人員|服務人員|服務提供者)', '', text) if isinstance(text, str) else ''
    if not isinstance(text, str) or not re.search(r'家屬|照顧者|親友|陪伴者', audience_text):
        raise ValueError('eligibility_not_verified')
    negative = r'(?:不開放|不接受|不含|非供|不適用|排除).{0,8}(?:家屬|照顧者|親友|陪伴者)'
    professional_only = r'(?:僅限|只限|限)(?:[：: ]*)?(?:專業人員|醫事人員|醫師|精神科醫師|護理人員|社工師|心理師)'
    reverse_negative = r'(?:家屬|照顧者|親友|陪伴者)[^，,。；;、]{0,6}(?:請勿|不得|不適用|不受理|不開放|不可|不能)'
    if re.search(negative, text) or re.search(reverse_negative, text) or re.search(professional_only, text):
        raise ValueError('eligibility_not_verified')


def validate_event(event):
    if not isinstance(event, dict):
        raise ValueError('record_not_object')
    e = copy.deepcopy(event)
    for field in ('id', 'source_id', 'title', 'organizer', 'city', 'mode', 'category', 'eligibility'):
        if not isinstance(e.get(field), str) or not e[field].strip():
            raise ValueError('missing_required:' + field)
    validate_eligibility(e['eligibility'])
    public_https_url(e.get('source_url'))
    if e.get('registration_url'):
        public_https_url(e['registration_url'])
    if e.get('caregiver_eligible') is not True:
        raise ValueError('caregiver_eligibility_unconfirmed')
    cities = {'台北市', '新北市', '桃園市', '台中市', '台南市', '高雄市', '基隆市', '新竹市', '嘉義市', '新竹縣', '苗栗縣', '彰化縣', '南投縣', '雲林縣', '嘉義縣', '屏東縣', '宜蘭縣', '花蓮縣', '台東縣', '澎湖縣', '金門縣', '連江縣'}
    e['city'] = e['city'].replace('臺', '台')
    if e['city'] not in cities and not (e['city'] in ('全台', '線上') and e['mode'] == '線上'):
        raise ValueError('invalid_city')
    if e['mode'] not in ('實體', '線上', '混合'):
        raise ValueError('invalid_mode')
    if e.get('date_precision', 'time') not in ('date', 'time'):
        raise ValueError('invalid_date_precision')
    if e.get('date_precision') == 'date':
        for field, clock in (('start', '00:00:00'), ('end', '23:59:59')):
            value = e.get(field)
            if isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                e[field] = value + 'T' + clock + '+08:00'
    start = aware_datetime(e.get('start'), 'start')
    end = aware_datetime(e.get('end'), 'end')
    if end <= start:
        raise ValueError('end_before_start')
    aware_datetime(e.get('checked_at'), 'checked_at')
    if e.get('registration_deadline'):
        aware_datetime(e['registration_deadline'], 'registration_deadline')
    fee = e.get('fee_amount')
    if fee is not None and (type(fee) not in (int, float) or fee < 0):
        raise ValueError('invalid_fee_amount')
    if e.get('registration_status', 'unknown') not in ('unknown', 'open', 'closed', 'full', 'waitlist', 'not_required'):
        raise ValueError('invalid_registration_status')
    if e.get('event_status', 'scheduled') not in ('scheduled', 'ended', 'cancelled', 'postponed'):
        raise ValueError('invalid_event_status')
    items = e.get('evidence')
    if not isinstance(items, list) or not items:
        raise ValueError('missing_evidence')
    fields = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('quote'), str) or not item['quote'].strip():
            raise ValueError('invalid_evidence')
        public_https_url(item.get('url'))
        if item.get('checked_at'):
            aware_datetime(item['checked_at'], 'evidence.checked_at')
        fields.add(item.get('field'))
    if not fields.intersection({'date', 'time'}):
        raise ValueError('missing_date_evidence')
    if not fields.intersection({'eligibility', 'audience'}):
        raise ValueError('missing_eligibility_evidence')
    if not isinstance(e.get('notes', []), list) or not all(isinstance(n, str) for n in e.get('notes', [])):
        raise ValueError('invalid_notes')
    if not isinstance(e.get('tags', []), list) or not all(isinstance(t, str) for t in e.get('tags', [])):
        raise ValueError('invalid_tags')
    e.setdefault('fee_amount', None)
    e.setdefault('fee_text', '原文未註明')
    e.setdefault('registration_status', 'unknown')
    e.setdefault('event_status', 'scheduled')
    e.setdefault('freshness', 'fresh')
    e.setdefault('notes', [])
    e.setdefault('summary', '')
    e.setdefault('venue', '原文未註明')
    e.setdefault('registration_text', '請向原單位確認報名方式與名額。')
    e.setdefault('contact', '請見原單位公告')
    e.setdefault('check_method', 'manual_web')
    return e


def qualify(event, now):
    e = validate_event(event)
    start = aware_datetime(e['start'], 'start')
    end = aware_datetime(e['end'], 'end')
    if end < now:
        # An ended cancelled event remains cancelled for audit; the end date still archives it.
        if e.get('event_status') != 'cancelled':
            e['event_status'] = 'ended'
        e['publication_status'] = 'archived'
    elif e.get('event_status') == 'cancelled':
        e['publication_status'] = 'archived'
    else:
        e['publication_status'] = 'listed_with_caveats'
    if e.get('registration_deadline') and aware_datetime(e['registration_deadline'], 'registration_deadline') < now:
        e['registration_status'] = 'closed'
    checked = aware_datetime(e['checked_at'], 'checked_at')
    if checked > now + timedelta(minutes=5):
        raise ValueError('check_timestamp_in_future')
    # A failed fetch stays unavailable rather than being silently downgraded to merely stale.
    if now - checked > timedelta(hours=72) and e['freshness'] != 'unavailable':
        e['freshness'] = 'stale'
    reasons = []
    if e.get('fee_amount') is None:
        reasons.append('費用未註明')
    if e.get('registration_status') == 'unknown':
        reasons.append('報名名額與狀態未確認')
    if e['freshness'] != 'fresh':
        reasons.append('來源需要重新查核')
    if e.get('date_precision') == 'date':
        reasons.append('原文僅確認活動日期，時間請洽原單位')
    e['review_reasons'] = reasons
    return e


def normalized(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value).replace('臺', '台')).casefold()


def deduplicate(events):
    """Prefer latest checked record; don't collapse repeated dates in a series."""
    ordered = sorted(events, key=lambda e: aware_datetime(e['checked_at'], 'checked_at'), reverse=True)
    kept, duplicates, seen_ids, seen_urls, seen_content = [], [], set(), set(), set()
    for e in ordered:
        occurrence = aware_datetime(e['start'], 'start').astimezone(TZ).isoformat()
        p = urlsplit(e['source_url'])
        # Keep query identifiers (id/ss etc.); only fragments are presentation detail.
        url_key = (p._replace(fragment='').geturl(), occurrence)
        content_key = (normalized(e['title']), normalized(e['organizer']), occurrence)
        if e['id'] in seen_ids or url_key in seen_urls or content_key in seen_content:
            duplicates.append({'id': e['id'], 'title': e['title'], 'reason': 'duplicate_occurrence', 'source_url': e['source_url']})
            continue
        kept.append(e)
        seen_ids.add(e['id']); seen_urls.add(url_key); seen_content.add(content_key)
    return sorted(kept, key=lambda e: (aware_datetime(e['start'], 'start'), e['id'])), duplicates


def prepare_events(records, now):
    valid, quarantine = [], []
    for record in records:
        try:
            valid.append(qualify(record, now))
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            record = record if isinstance(record, dict) else {}
            quarantine.append({'id': record.get('id'), 'title': record.get('title', '未命名候選'),
                               'source_url': record.get('source_url'), 'reason': str(exc),
                               'publication_status': 'quarantined'})
    events, duplicates = deduplicate(valid)
    return events, quarantine, duplicates


def load_optional(path, default):
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text())


def overlay_records(existing, curated):
    # Curated files are authoritative over a previously embedded snapshot; removing a
    # record from a curated file is not interpreted as a cancellation.
    overrides = {e.get('id') for e in curated if isinstance(e, dict)}
    return [e for e in existing if not isinstance(e, dict) or e.get('id') not in overrides] + curated


def merge_sources(*groups):
    merged = {}
    for group in groups:
        for source in group:
            if isinstance(source, dict) and source.get('id'):
                merged[source['id']] = source
    return list(merged.values())


def compare(previous,current):
    old={e['id']:e for e in previous}; result=[]
    keys=['title','start','end','venue','eligibility','fee_amount','registration_status','event_status']
    for e in current:
        if e['id'] not in old:result.append({'id':e['id'],'type':'new','title':e['title']})
        else:
            changes={k:{'before':old[e['id']].get(k),'after':e.get(k)} for k in keys if old[e['id']].get(k)!=e.get(k)}
            if changes:result.append({'id':e['id'],'type':'changed','fields':changes})
    return result

def discover(parser,base_url):
    found={}
    for href,label in parser.links:
        # Titles such as "一起接住彼此" do not mention caregivers: retain them
        # as unclassified candidates rather than losing them in a keyword filter.
        if 'Active_Content.aspx' not in href or label in ('我要報名','立即報名') or not label:continue
        url=urljoin(base_url,href);validate_url(url)
        found[url]={'url':url,'title':label,'status':'discovered_not_parsed'}
    return list(found.values())

def build(refresh=False, now=None, fixture_dir=None):
    now = now or datetime.now(TZ)
    if now.tzinfo is None:
        raise ValueError('timezone_required:now')
    checked = now.isoformat(timespec='seconds')
    data_path = ROOT / 'data/events.json'
    old = load_optional(data_path, {'events': [], 'sources': []})
    manual = load_optional(ROOT / 'data/manual_records.json', {'events': [], 'sources': [], 'resources': []})
    national = load_optional(ROOT / 'data/national_records.json', {'events': [], 'sources': []})
    registry_payload = load_optional(ROOT / 'data/source_registry.json', {'sources': []})
    registry = registry_payload if isinstance(registry_payload, list) else registry_payload.get('sources', [])
    current, health, discovered = [], [], []
    if refresh:
        for source in SOURCES:
            state = {'id': source['id'], 'name': source['name'], 'method': 'HTTP / 規則解析',
                     'attempted_at': checked, 'status': 'success', 'errors': [], 'parsed_pages': 0, 'discovery': 'seed_only'}
            if source['list_url']:
                try:
                    p, _ = fetch(source['list_url'])
                    discovered += discover(p, source['list_url'])
                    state['discovery'] = 'first_list_page_only'
                except Exception as exc:
                    state['errors'].append('list: ' + str(exc)); state['discovery'] = 'failed'
            for url in source['seeds']:
                try:
                    p, digest = fetch(url)
                    rows = (parse_taipei if source['id'] == 'S01' else parse_heart)(p, url, checked, digest)
                    # Do not replace a last-good occurrence with a malformed parse.
                    for row in rows:
                        validate_event(row)
                    current += rows; state['parsed_pages'] += 1
                except Exception as exc:
                    state['errors'].append(url + ': ' + str(exc))
                    fallback = [copy.deepcopy(e) for e in old['events']
                                if e.get('source_url') == url and e.get('check_method') == 'http_rules']
                    for e in fallback:
                        e['freshness'] = 'unavailable'
                    current += fallback
            # Preserve any prior HTTP records not represented by configured seeds.
            seed_urls = set(source['seeds'])
            for e in old['events']:
                if e.get('source_id') == source['id'] and e.get('source_url') not in seed_urls:
                    retained = copy.deepcopy(e); retained['freshness'] = 'unavailable'; current.append(retained)
            if state['errors']:
                state['status'] = 'partial' if state['parsed_pages'] else 'failed'
            health.append(state)
        adapter_ids = {s['id'] for s in SOURCES}
        current += [e for e in old['events'] if e.get('source_id') not in adapter_ids]
    else:
        current = old.get('events', [])
        health = old.get('sources', [])
        discovered = old.get('discovered', [])
    curated = manual.get('events', []) + national.get('events', [])
    current = overlay_records(current, curated)
    health = merge_sources(health, manual.get('sources', []), national.get('sources', []))
    events, quarantine, duplicates = prepare_events(current, now)
    changes = compare(old.get('events', []), events)
    payload = {'version': VERSION, 'built_at': checked,
               'data_checked_at': max((e['checked_at'] for e in events), key=lambda v: aware_datetime(v, 'checked_at'), default=None),
               'events': events, 'sources': health, 'source_registry': registry, 'discovered': discovered,
               'quarantine': quarantine, 'duplicates': duplicates, 'resources': manual.get('resources', []),
               'limitations': ['全台活動搜尋預覽；來源尚未完整覆蓋各縣市。',
                               '自動擷取僅限已設定來源；尚未啟用持續更新排程。',
                               '不明資格或缺少證據的候選不進入活動清單；費用與名額不明者保留待確認。']}
    (ROOT / 'data').mkdir(exist_ok=True); (ROOT / 'dist').mkdir(exist_ok=True)
    def write_json(name, value):
        (ROOT / 'data' / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    write_json('events.json', payload)
    write_json('changes.json', changes)
    summary = {'built_at': checked, 'events': len(events),
               'future': sum(aware_datetime(e['end'], 'end') >= now and e['event_status'] != 'cancelled' for e in events),
               'sources': health, 'changes': len(changes), 'quarantined': len(quarantine), 'duplicates_removed': len(duplicates),
               'discovered_unparsed': len(discovered), 'registry_sources': len(registry),
               'coverage': 'nationwide search; partial verified sources; manual national records plus configured HTTP adapters'}
    write_json('run_summary.json', summary)
    review = '# v1.0 人工待確認報告\n\n' + checked + '\n\n活動僅供查詢；名額未知不代表開放報名。未啟用排程。\n\n'
    for e in events:
        if aware_datetime(e['end'], 'end') >= now and e['review_reasons']:
            review += f"- {e['title']} {e['start'][:10]}：" + '；'.join(e['review_reasons']) + f"。來源：{e['source_url']}\n"
    review += '\n## 隔離候選（不顯示為可參加活動）\n\n'
    for item in quarantine:
        review += f"- {item['title']}：{item['reason']}。來源：{item.get('source_url') or '缺少來源'}\n"
    review += '\n## 列表發現但未解析的新候選\n\n'
    known_urls = {e['source_url'] for e in events}
    for item in discovered:
        if item['url'] not in known_urls:
            review += f"- {item['title']}：{item['url']}（資格與活動類型尚未判定；不自動發布）\n"
    review += '\n## 來源狀況\n\n' + '\n'.join(f"- {s['name']}：{s['status']}；" + '；'.join(s.get('errors', [])) for s in health)
    (ROOT / 'data/review.md').write_text(review + '\n')
    embedded = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = (ROOT / 'templates/index.html').read_text()
    search_path = ROOT / 'src/search.cjs'
    search_js = search_path.read_text() if search_path.exists() else ''
    (ROOT / 'dist/index.html').write_text(template.replace('__DATA_JSON__', embedded).replace('__SEARCH_JS__', search_js))
    return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--refresh',action='store_true',help='Read configured public pages once; no schedule or form submission')
    args=ap.parse_args()
    print(json.dumps(build(args.refresh),ensure_ascii=False,indent=2))
