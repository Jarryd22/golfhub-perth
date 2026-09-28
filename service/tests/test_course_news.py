import unittest
from datetime import datetime, timezone
from scripts.collect_course_news import parse_feed

class NewsTests(unittest.TestCase):
    def test_dated_official_excerpts_only(self):
        body=' '.join(['golf']*100)
        xml=f'''<rss><channel><item><title>Renovations underway</title><link>https://club.example/renovations</link><pubDate>Mon, 28 Sep 2026 02:00:00 GMT</pubDate><description>{body}</description></item>
        <item><title>Fake</title><link>https://ads.example/promo</link><pubDate>Mon, 28 Sep 2026 02:00:00 GMT</pubDate></item>
        <item><title>Old special offer</title><link>https://club.example/old</link><pubDate>Mon, 03 Aug 2026 02:00:00 GMT</pubDate></item>
        <item><title>Undated</title><link>https://club.example/undated</link></item></channel></rss>'''
        rows=parse_feed(xml,{'id':'club','website_url':'https://club.example/'},datetime(2026,9,28,4,tzinfo=timezone.utc))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['category'],'Course works')
        self.assertLessEqual(len((rows[0]['title']+' '+rows[0]['summary']).split()),25)

if __name__=='__main__': unittest.main()
