"""v1.0.0: bounded, source-scoped media discovery. No network or OCR calls."""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, unquote

RASTER = re.compile(r'\.(?:jpe?g|png|webp|gif)(?:$|[?#])', re.I)
POSTER = re.compile(r'海報|簡章|招生|活動圖|宣傳|poster|flyer', re.I)
CHROME = re.compile(r'(?:^|[\s_./-])(?:nav|footer|header|sidebar|logo|banner|share|icon|tracking)(?:$|[\s_./-])|網站標誌|分享按鈕', re.I)
CONTENT = re.compile(r'content|article|editor|detail|正文|活動內容', re.I)
VOID = {'img','meta','br','hr','input','link','source','area','embed','wbr','param','track','col','base'}


def image_url(raw, base, hosts):
    if not raw or raw.strip().lower().startswith(('data:', 'blob:', 'javascript:')):
        return None
    value = urljoin(base, raw.strip())
    try:
        p = urlsplit(value)
        if p.scheme != 'https' or p.hostname not in hosts or p.username or p.password or p.port not in (None,443):
            return None
    except ValueError:
        return None
    return value if RASTER.search(value) else None


def largest_srcset(value):
    choices=[]
    for part in value.split(','):
        bits=part.strip().split()
        if not bits or bits[0].startswith('data:'):
            continue
        weight=1.0
        if len(bits)>1:
            try: weight=float(bits[1].rstrip('wx'))
            except ValueError: continue
        choices.append((weight,bits[0]))
    return max(choices,default=(0,''))[1]


class Media(HTMLParser):
    def __init__(self, base, title, hosts):
        super().__init__(convert_charrefs=True)
        self.base,self.title,self.hosts=base,title,hosts
        self.stack=[];self.items=[]

    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        contexts=self.stack+[(tag,a)]
        labels=' '.join(str(b.get(k,'')) for _,b in contexts for k in ('id','class','role'))
        if CHROME.search(labels) or any(t in ('nav','header','footer','script','style') for t,_ in contexts):
            excluded=True
        else: excluded=False
        in_content=any(t in ('article','main') for t,_ in contexts) or bool(CONTENT.search(labels))
        alt=a.get('alt','')
        raw='';kind='body_image'
        if tag=='img':
            if a.get('width') in ('0','1') or a.get('height') in ('0','1'):
                excluded=True
            # Full-size linked images outrank lazy thumbnails and placeholder src.
            anchor=next((b.get('href','') for t,b in reversed(self.stack) if t=='a'), '')
            possibilities=[anchor,a.get('data-original',''),a.get('data-src',''),largest_srcset(a.get('data-srcset','')),largest_srcset(a.get('srcset','')),a.get('src','')]
            raw=next((x for x in possibilities if image_url(x,self.base,self.hosts)), '')
        elif tag=='a' and image_url(a.get('href',''),self.base,self.hosts):
            raw=a['href'];alt=a.get('title','');kind='image_attachment'
        elif tag=='meta' and a.get('property','').lower()=='og:image':
            raw=a.get('content','');kind='social_preview';in_content=False
        url=image_url(raw,self.base,self.hosts)
        if url and not excluded and not CHROME.search(unquote(url)+' '+alt):
            normalized=lambda s:re.sub(r'[\W_]+','',s)
            title=normalized(self.title)
            matching=bool(title and len(title)>=4 and title in normalized(alt))
            hint=bool(POSTER.search(unquote(url)+' '+alt))
            score=(3 if in_content else 0)+(4 if hint else 0)+(6 if matching else 0)
            self.items.append({'url':url,'alt':alt[:200],'kind':kind,'score':score,'in_content':in_content,'title_match':matching,'source_url':self.base})
        if tag not in VOID:
            self.stack.append((tag,a))

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:];break


def extract_media_candidates(html, source_url, title, media_hosts=()):
    """Return deduplicated candidates; do not treat og:image as a verified poster."""
    hosts={urlsplit(source_url).hostname,*media_hosts}
    parser=Media(source_url,title,hosts);parser.feed(html)
    best={}
    for item in parser.items:
        if item['url'] not in best or item['score']>best[item['url']]['score']:
            best[item['url']]=item
    return sorted(best.values(),key=lambda x:(-x['score'],x['url']))[:10]
