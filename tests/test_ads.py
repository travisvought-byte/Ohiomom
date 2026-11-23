"""The Privacy page, and the ad slots that stay empty until an ad is sold. Run: python3 -m unittest discover tests

The owners decided on November 19, 2026 that the site may carry ads. These tests hold the promises that came with
that: no page says there are no ads, every page links to the Privacy page, an empty ad list leaves no ad markup
anywhere, and an ad, once there is one, is labeled, marked sponsored, alone on its page and outside the listings.
"""
import copy
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ads  # noqa: E402
import ymt_build  # noqa: E402
import ymt_lib as lib  # noqa: E402

DATA = lib.load()


def site_pages():
    """Every page a visitor can land on: the built pages, the OhioMom pages and the family guide (not the redirects)."""
    pages = [ROOT / rel for rel in ymt_build.build_all(DATA) if rel.endswith('.html')]
    pages += sorted((ROOT / 'ohio').rglob('*.html')) + [ROOT / 'family-guide.html']
    return [p for p in pages if 'http-equiv="refresh"' not in p.read_text(encoding='utf-8')]


def fixture(today='2026-12-10'):
    """Data with one ad in every kind of slot, a state of its own for Ohio, and two that are not running."""
    data = copy.deepcopy(DATA)
    data['today'] = today

    def ad(slot, sponsor, **more):
        return dict({'slot': slot, 'sponsor': sponsor, 'text': f'{sponsor} helps families & moms.', 'url': f'https://example.org/{slot}'}, **more)
    data['ads'] = [
        ad('home', 'Home Sponsor'), ad('topic', 'Topic Sponsor'), ad('state', 'Any State Sponsor'),
        ad('state-oh', 'Ohio Sponsor'), ad('county', 'County Sponsor'), ad('ohio-home', 'OhioMom Sponsor'),
        ad('ohio-county', 'Ohio County Sponsor'), ad('ohio-topic', 'Ohio Topic Sponsor'),
        ad('ohio-county-morrow', 'Morrow Sponsor', start='2026-12-01', end='2026-12-31'),
        ad('topic-help', 'Not Yet', start='2027-01-01'), ad('topic-connect', 'Already Over', end='2026-11-30'),
    ]
    return data


def built(data):
    files = ymt_build.build_all(data)
    files.update(ymt_build.ohio_ad_files(data))
    return {rel: text for rel, text in files.items() if rel.endswith('.html')}


class PrivacyTests(unittest.TestCase):
    def test_privacy_page_exists_and_says_what_it_must(self):
        text = (ROOT / 'privacy.html').read_text(encoding='utf-8')
        self.assertIn('<h1>Privacy</h1>', text)
        self.assertIn('<time datetime="2026-11-23">November 23, 2026</time>', text)
        for words in ('hosted on GitHub Pages', 'We count visits with GoatCounter', 'does not use cookies', 'never a search or ZIP code', 'Your internet address itself is not stored', 'There is no sign-up',
                      'Every ad is labeled "Advertisement" and kept apart from the resource listings',
                      'We use Google AdSense and ask Google to show only non-personalized ads', 'store nothing of their own on your device', 'can set its own cookies',
                      'Google AdSense', 'https://adssettings.google.com', 'https://policies.google.com/technologies/ads',
                      'https://optout.aboutads.info', 'We do not sell personal information',
                      'not directed to children under 13', 'href="report.html"'):
            self.assertIn(words, text)
        self.assertNotRegex(text, r'(?i)ads are (now )?running|we show ads|we run ads')
        self.assertIn('<loc>https://www.yogamomtalk.com/privacy.html</loc>', (ROOT / 'sitemap.xml').read_text(encoding='utf-8'))

    def test_every_page_links_to_privacy_in_its_footer(self):
        pages = site_pages()
        self.assertGreater(len(pages), 80)
        for path in pages:
            text = path.read_text(encoding='utf-8')
            foot = re.search(r'<footer class="foot">(.*?)</footer>', text, re.S)
            self.assertTrue(foot, f'{path}: no footer')
            links = re.findall(r'<p class="footnav">.*?</p>', foot.group(1), re.S)
            self.assertEqual(len(links), 1, path)
            # A translated page (ohio/<lang>/, scripts/ohio_i18n.py) names the page in its own language.
            href = re.search(r'<a href="([^"]*privacy\.html)">[^<]+</a>', links[0])
            self.assertTrue(href, f'{path}: the footer links to the Privacy page')
            target = ROOT / href.group(1).lstrip('/') if href.group(1).startswith('/') else (path.parent / href.group(1)).resolve()
            self.assertEqual(target, ROOT / 'privacy.html', path)

    def test_no_page_promises_no_ads(self):
        promise = re.compile(r'(?i)\bno ads\b|\bor ads\b|\bad-free\b|\bno advertising\b|\bwithout ads\b|\bthere are no ads\b')
        paths = site_pages() + [ROOT / 'templates' / 'family-guide.html', ROOT / 'templates' / 'share-card.html',
                                ROOT / 'scripts' / 'share_cards.py']
        for path in paths:
            self.assertNotRegex(path.read_text(encoding='utf-8'), promise, path)

    def test_about_pages_explain_ads_and_link_privacy(self):
        about = (ROOT / 'about.html').read_text(encoding='utf-8')
        self.assertIn('<h2 id="advertise">Advertise with us</h2>', about)
        self.assertIn('labeled Advertisement', about)
        self.assertIn('never changes what is listed', about)
        self.assertIn('We review every ad before it runs', about)
        self.assertIn('mailto:' + DATA['site']['corrections_email'], about)
        self.assertNotRegex(about, r'\$\d|per month|a month|pricing', 'no prices on the page')
        self.assertIn('href="privacy.html"', about)
        self.assertIn('We count visits with GoatCounter, which does not use cookies', about)
        ohio = (ROOT / 'ohio' / 'about.html').read_text(encoding='utf-8')
        self.assertIn('href="../about.html#advertise"', ohio)
        self.assertIn('href="../privacy.html"', ohio)

    def test_contact_and_terms_for_ad_review(self):
        # November 22, 2026: the About page names a contact, and a Terms of use page exists, is linked and is in the sitemap.
        about = (ROOT / 'about.html').read_text(encoding='utf-8')
        self.assertIn('<h2 id="contact">Contact us</h2>', about)
        self.assertIn('href="terms.html"', about)
        self.assertIn('href="terms.html"', (ROOT / 'privacy.html').read_text(encoding='utf-8'))
        terms = (ROOT / 'terms.html').read_text(encoding='utf-8')
        for words in ('Terms of use', 'not an emergency service', 'Ads are labeled Advertisement', 'without any warranty', 'href="privacy.html"',
                      'mailto:' + DATA['site']['corrections_email']):
            self.assertIn(words, terms)
        self.assertNotIn('ad-slot', terms)
        self.assertIn('<loc>https://www.yogamomtalk.com/terms.html</loc>', (ROOT / 'sitemap.xml').read_text(encoding='utf-8'))

    def test_the_one_visit_counter_is_the_one_the_privacy_page_describes(self):
        """GoatCounter (added November 19, 2026 at the owner's request) is the only counter. It is loaded by the three shared
        scripts, the same lines in each; it sends only the page's path, with no query string; no page loads a counter or ad
        network of its own (Google's ad code is added only once data/ads.json names a publisher ID; see NetworkTests). If a counter or an ad network changes, the Privacy page changes in the same commit."""
        scripts = ['assets/ymt.js', 'ohio/assets/site.js', 'assets/family-guide.js']
        blocks = []
        for rel in scripts:
            text = (ROOT / rel).read_text(encoding='utf-8')
            m = re.search(r'\n// Visit counter \(GoatCounter.*\n', text, re.S)
            self.assertIsNotNone(m, rel)
            blocks.append(m.group(0))
            self.assertIn("p.replace(/\\?.*$/,'')", m.group(0), rel)
            self.assertIn('return u.origin+u.pathname;', m.group(0), rel)
            self.assertEqual(m.group(0).count('gc.zgo.at'), 1, rel)
            self.assertNotRegex(text, r'(?i)googletagmanager|google-analytics|gtag\(|adsbygoogle', rel)
        self.assertEqual(len(set(blocks)), 1, 'the counter lines must be the same in all three scripts')
        for path in site_pages():
            text = ads.NETWORK.sub('', path.read_text(encoding='utf-8'))  # Google's ad code, once a publisher ID is set, is checked in NetworkTests
            self.assertNotRegex(text, r'(?i)gc\.zgo\.at|googletagmanager|google-analytics|gtag\(|adsbygoogle', path)

    def test_every_page_carries_the_visit_counter(self):
        """Every page a visitor can land on loads one of the three shared scripts that hold the counter, so every visit
        is counted once. The small redirect pages are left out on purpose: they send the visitor straight on, and the
        page they land on counts the visit."""
        for path in site_pages():
            text = path.read_text(encoding='utf-8')
            self.assertRegex(text, r'<script src="(?:/|(?:\.\./)*)(?:assets/ymt\.js|assets/site\.js|assets/family-guide\.js)"', path)


class AdSlotTests(unittest.TestCase):
    def test_the_ad_list_ships_empty_and_leaves_no_markup(self):
        self.assertEqual(ads.load(), [])
        self.assertEqual(ads.check(ads.load()), [])
        for path in site_pages():
            text = path.read_text(encoding='utf-8')
            self.assertNotIn('ad-slot', text, path)
            self.assertNotIn('rel="sponsored', text, path)
        data = copy.deepcopy(DATA)
        data['ads'] = []
        for rel, text in built(data).items():
            self.assertNotIn('<aside', text, rel)
            self.assertNotIn('Advertisement</p>', text, rel)
        for rel, text in ymt_build.ohio_ad_files(data).items():
            self.assertEqual(text, (ROOT / rel).read_text(encoding='utf-8'), f'{rel}: no ad, no change')

    def test_an_ad_is_labeled_sponsored_alone_and_after_the_listings(self):
        pages = built(fixture())
        expect = {'index.html': 'Home Sponsor', 'help.html': 'Topic Sponsor', 'connect.html': 'Topic Sponsor',
                  'states/oh.html': 'Ohio Sponsor', 'states/wy.html': 'Any State Sponsor', 'county.html': 'County Sponsor',
                  'ohio/index.html': 'OhioMom Sponsor', 'ohio/counties/morrow.html': 'Morrow Sponsor',
                  'ohio/counties/knox.html': 'Ohio County Sponsor', 'ohio/help/bills.html': 'Ohio Topic Sponsor',
                  'ohio/help/pregnancy-baby.html': 'Ohio Topic Sponsor', 'ohio/help/single-parent.html': 'Ohio Topic Sponsor',
                  'ohio/connect.html': 'Ohio Topic Sponsor'}
        for rel, sponsor in expect.items():
            text = pages[rel]
            asides = re.findall(r'<aside class="ad-slot".*?</aside>', text, re.S)
            self.assertEqual(len(asides), 1, f'{rel}: one ad at most')
            ad = asides[0]
            self.assertTrue(ad.startswith('<aside class="ad-slot" aria-label="Advertisement"><p class="ad-label">Advertisement</p>'), rel)
            self.assertIn(f'<p class="ad-sponsor">{sponsor}</p>', ad, rel)
            self.assertIn('helps families &amp; moms.', ad, 'the words are escaped')
            links = re.findall(r'<a [^>]*>', ad)
            self.assertEqual(len(links), 1, rel)
            self.assertIn('rel="sponsored noopener"', links[0], rel)
            # Last in <main>: after every listing, row and section of the page's own content.
            self.assertIn(ad + '\n</main>', text, f'{rel}: the ad comes last in <main>')
            before = text[:text.index(ad)]
            self.assertEqual(before.count('<details'), before.count('</details>'), f'{rel}: the ad is not inside a row')
            self.assertEqual(before.count('<section'), before.count('</section>'), f'{rel}: the ad is not inside a section')
            self.assertEqual(before.count('<article'), before.count('</article>'), f'{rel}: the ad is not inside a card')
            self.assertNotIn('class="card', ad, rel)
        self.assertNotIn('Not Yet', pages['help.html'], 'an ad that has not started is not shown')
        self.assertNotIn('Already Over', pages['connect.html'], 'an ad that has ended is not shown')

    def test_crisis_and_other_pages_never_carry_an_ad(self):
        pages = built(fixture())
        for rel in ('about.html', 'privacy.html', 'terms.html', 'report.html', '404.html', 'states.html', 'yoga.html', 'jokes.html', 'affirmations.html'):
            if rel in pages:
                self.assertNotIn('ad-slot', pages[rel], rel)
        for rel in ads.NEVER:
            self.assertNotIn('ad-slot', pages.get(rel, ''), f'{rel} is never given an ad')
            self.assertNotIn(rel, ads.ohio_pages())
        for rel in ('ohio/help/housing.html', 'ohio/wellbeing.html'):
            self.assertNotIn(rel, ads.ohio_pages(), 'crisis and help-now pages have no slot')

    def test_dated_ads_run_only_between_their_days(self):
        early = built(fixture(today='2026-11-25'))
        self.assertIn('Ohio County Sponsor', early['ohio/counties/morrow.html'], 'before Morrow starts, the shared ad runs')
        self.assertIn('Already Over', early['connect.html'])
        self.assertNotIn('Morrow Sponsor', early['ohio/counties/morrow.html'])

    def test_the_checker_turns_down_what_the_pages_cannot_carry(self):
        good = {'slot': 'home', 'sponsor': 'A', 'text': 'Words.', 'url': 'https://example.org/'}
        self.assertEqual(ads.check([good]), [])
        bad = [
            dict(good, url='http://example.org/'),
            dict(good, slot='crisis'),
            dict(good, slot='ohio-county-atlantis'),
            dict(good, image='https://example.org/a.png', alt='A picture'),
            dict(good, image='assets/ads/missing.png'),
            dict(good, sponsor='<b>A</b>'),
            dict(good, start='2026-12-31', end='2026-12-01'),
            dict(good, start='soon'),
            dict(good, price='$10'),
            dict(good, text='x' * 221),
            {k: v for k, v in good.items() if k != 'url'},
        ]
        for ad in bad:
            self.assertTrue(ads.check([ad]), ad)
        self.assertTrue(ads.check([good, dict(good, sponsor='B')]), 'two ads for one slot')


if __name__ == '__main__':
    unittest.main()


class NetworkTests(unittest.TestCase):
    """Google AdSense (owner decision, November 22, 2026): non-personalized only, off the help and crisis pages,
    and nothing at all until data/ads.json names a publisher ID."""
    CLIENT = 'ca-pub-1234567890123456'

    def with_client(self):
        data = copy.deepcopy(DATA)
        data['adsense_client'] = self.CLIENT
        return data

    def test_no_publisher_id_means_no_ad_code(self):
        if DATA['adsense_client']:
            self.skipTest('a publisher ID is set; the tests below cover the code it adds')
        self.assertFalse((ROOT / 'ads.txt').exists())
        self.assertNotIn('ads.txt', ymt_build.build_all(DATA))
        for path in site_pages():
            self.assertNotIn('googlesyndication', path.read_text(encoding='utf-8'), path)

    def test_publisher_id_is_checked(self):
        self.assertEqual(ads.check_client(''), [])
        self.assertEqual(ads.check_client(self.CLIENT), [])
        for bad in ('pub-1234567890123456', 'ca-pub-123', 'ca-pub-1234567890123456"><script>'):
            self.assertTrue(ads.check_client(bad), bad)

    def test_code_only_on_slot_pages_that_are_not_help_pages(self):
        data = self.with_client()
        pages = built(data)
        loader = f'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={self.CLIENT}'
        carry = {'index.html', 'connect.html', 'county.html', 'states/oh.html', 'ohio/index.html', 'ohio/connect.html'}
        carry |= {rel for rel in pages if rel.startswith('ohio/counties/') or rel.startswith('countries/')}
        never = {'help.html', 'christmas.html', 'world.html', 'about.html', 'privacy.html', 'terms.html', 'report.html', '404.html',
                 'states.html', 'yoga.html', 'affirmations.html', 'ohio/help/bills.html', 'ohio/help/pregnancy-baby.html',
                 'ohio/help/single-parent.html'} | set(ads.NEVER)
        for rel in carry:
            if rel not in pages:
                continue
            text = pages[rel]
            head = text.split('</head>')[0]
            self.assertEqual(text.count(loader), 1, rel)
            self.assertIn(loader, head, rel)
            self.assertLess(head.index('requestNonPersonalizedAds=1'), head.index(loader), rel + ': non-personalized is asked first')
            self.assertIn(f'<meta name="google-adsense-account" content="{self.CLIENT}">', head, rel)
        for rel in never:
            if rel in pages:
                self.assertNotIn('googlesyndication', pages[rel], rel)
            elif (ROOT / rel).exists():
                self.assertNotIn('googlesyndication', (ROOT / rel).read_text(encoding='utf-8'), rel)
        self.assertNotIn('googlesyndication', (ROOT / 'family-guide.html').read_text(encoding='utf-8'))

    def test_ads_txt_and_hand_kept_pages_round_trip(self):
        data = self.with_client()
        self.assertEqual(ymt_build.build_all(data)['ads.txt'], 'google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0\n')
        for rel, text in ymt_build.ohio_ad_files(data).items():
            back = ads.place_network(text, '', ads.ohio_pages()[rel])
            self.assertEqual(back, ads.NETWORK.sub('', (ROOT / rel).read_text(encoding='utf-8')), f'{rel}: removing the code restores the page')
            self.assertEqual(ads.place_network(text, self.CLIENT, ads.ohio_pages()[rel]), text, f'{rel}: placing twice adds nothing')
