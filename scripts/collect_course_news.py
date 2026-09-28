"""Collect short, dated announcements from official course RSS/Atom feeds.

No social logins, invented news, full articles, or booking-site challenges.
One daily shared fetch keeps this free and avoids every phone polling clubs.
"""
import argparse
import hashlib
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
UA = 'GolfHubPerth-CourseNews/1.0 (+https://golfhub-perth.web.app)'


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.feeds = []; self.images = []; self.words = []; self.hidden = 0
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'style'): self.hidden += 1
        if tag == 'link' and a.get('type', '') in ('application/rss+xml', 'application/atom+xml'):
            self.feeds.append(a.get('href', ''))
        if tag == 'img' and a.get('src') and a.get('width') != '1' and a.get('height') != '1':
            self.images.append(a['src'])
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden: self.words.extend(data.split())


def safe_url(value):
    try:
        u = urlparse(value)
        return value if u.scheme == 'https' and u.hostname and not u.username else None
    except ValueError: return None


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/rss+xml, application/atom+xml, text/html;q=0.8'})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000: raise ValueError('Feed too large')
        return raw.decode('utf-8', errors='replace')


def parse_feed(text, course, clock):
    root = ET.fromstring(text)
    result = []
    for entry in root.iter():
        if entry.tag.split('}')[-1] not in ('item', 'entry'): continue
        values = {}
        for child in entry:
            key = child.tag.split('}')[-1]
            values.setdefault(key, child.text or '')
        title = ' '.join(Page(values.get('title', '')).words)[:180]
        url = safe_url(values.get('link', ''))
        if not url:
            url = next((safe_url(n.get('href', '')) for n in entry if n.tag.split('}')[-1] == 'link' and n.get('rel', 'alternate') == 'alternate'), None)
        # Only the official site's articles; feeds may contain external ads.
        if not title or not url or urlparse(url).hostname.removeprefix('www.') != urlparse(course['website_url']).hostname.removeprefix('www.'): continue
        date_text = values.get('pubDate') or values.get('published') or values.get('updated')
        try:
            try: stamp = parsedate_to_datetime(date_text)
            except (ValueError, TypeError): stamp = datetime.fromisoformat(date_text.replace('Z', '+00:00'))
            if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError, AttributeError): continue
        if not clock - timedelta(days=90) <= stamp <= clock + timedelta(hours=1): continue
        body = values.get('description') or values.get('summary') or values.get('encoded') or values.get('content') or ''
        page = Page(body)
        # Short excerpts only: at most 25 combined title + excerpt words.
        summary = ' '.join(page.words[:max(0, min(14, 25 - len(title.split())))])
        photo = next((safe_url(urljoin(url, p)) for p in page.images if safe_url(urljoin(url, p))), None)
        for n in entry:
            if n.tag.split('}')[-1] in ('thumbnail', 'content', 'enclosure') and n.get('url') and ('image' in n.get('type', 'image') or n.get('medium') == 'image'):
                photo = safe_url(n.get('url')) or photo
        topic = title.lower()
        category = ('Course works' if re.search(r'\b(renovat|maintenance|coring|closure|closed|upgrade|redevelop)', topic) else
                    'Offers' if re.search(r'\b(offer|deal|special|discount|twilight)', topic) else
                    'Events' if re.search(r'\b(event|open day|tournament|competition|championship|christmas)', topic) else 'Course news')
        if category == 'Offers' and stamp < clock - timedelta(days=30): continue
        result.append({'id': hashlib.sha256(url.encode()).hexdigest()[:20], 'course_id': course['id'],
                       'title': html.unescape(title), 'summary': html.unescape(summary), 'url': url,
                       'image': photo, 'published_at': stamp.astimezone(timezone.utc).isoformat(), 'category': category})
    return sorted(result, key=lambda v: v['published_at'], reverse=True)[:4]


def collect(course, clock):
    url = course['website_url']
    try:
        text = fetch(url)
        feeds = [urljoin(url, u) for u in Page(text).feeds]
        if not feeds and ('wp-content/' in text or 'WordPress' in text): feeds = [urljoin(url.rstrip('/') + '/', 'feed/')]
        for feed in dict.fromkeys(feeds[:3]):
            if not safe_url(feed): continue
            try:
                items = parse_feed(fetch(feed), course, clock)
                return course['id'], items, 'checked'
            except Exception: continue
        return course['id'], [], 'unavailable' if feeds else 'no_feed'
    except Exception: return course['id'], [], 'unavailable'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--sources', type=Path, default=ROOT / 'data/course_news_sources.json')
    args = parser.parse_args()
    courses = json.loads(args.sources.read_text(encoding='utf8'))['courses']
    clock = datetime.now(timezone.utc)
    old = {}
    if args.previous and args.previous.exists():
        try: old = json.loads(args.previous.read_text(encoding='utf8'))
        except (ValueError, OSError): pass
    items, sources = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for cid, rows, status in pool.map(lambda c: collect(c, clock), courses):
            if status == 'unavailable':
                rows = [r for r in old.get('items', []) if r['course_id'] == cid and
                        datetime.fromisoformat(r['published_at']) >= clock - timedelta(days=30)]
            items.extend(rows)
            sources.append({'course_id': cid, 'status': status})
    items = list({row['id']: row for row in items}.values())
    items.sort(key=lambda r: r['published_at'], reverse=True)
    payload = {'schema': 1, 'generated_at': clock.isoformat(), 'items': items, 'sources': sources}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf8')
    print(f'Collected {len(items)} announcements; {sum(s["status"] == "checked" for s in sources)} course feeds checked.')


if __name__ == '__main__': main()
