"""Tests for scripts/linkcheck.py. Every request goes to a small server started here; nothing leaves the machine."""
import json
import os
import sys
import threading
import unittest
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
# The test servers are on this machine; never send those requests through a proxy.
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'
import linkcheck  # noqa: E402


def make_server(routes):
    """routes: {path: (status, headers, body)}; any other path answers routes['*'] or 404."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, headers, body = routes.get(self.path, routes.get('*', (404, {}, 'gone')))
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            if 'Content-Type' not in headers:
                self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body.encode('utf-8'))

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def page(title):
    return f'<!doctype html><html><head><title>{title}</title></head><body>x</body></html>'


class SortingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.other = make_server({'/': (200, {}, page('Another organization'))})
        other = f'http://localhost:{cls.other.server_port}/'
        cls.normal = make_server({
            '/': (200, {}, page('A real site')),
            '/ok': (200, {}, page('Help for families')),
            '/refused': (403, {}, 'no robots'),
            '/parked': (200, {}, page('example.org is for sale | Buy now')),
            '/gambling': (200, {}, page('Iontogel: Masuk Via Website')),
            '/soft404': (200, {}, page('Page not found | State Department')),
            '/moved': (302, {'Location': other}, ''),
            '/same-site': (302, {'Location': '/ok'}, ''),
        })
        cls.turns_away = make_server({'*': (404, {}, 'not for robots')})
        cls.base = f'http://127.0.0.1:{cls.normal.server_port}'
        cls.away = f'http://127.0.0.1:{cls.turns_away.server_port}'

    @classmethod
    def tearDownClass(cls):
        for s in (cls.other, cls.normal, cls.turns_away):
            s.shutdown()

    def pile(self, url):
        return linkcheck.Checker().check(url)[0]

    def test_a_page_that_loads_is_ok(self):
        self.assertEqual(self.pile(self.base + '/ok'), 'ok')
        self.assertEqual(self.pile(self.base + '/same-site'), 'ok')

    def test_a_missing_page_on_a_working_site_is_broken(self):
        self.assertEqual(self.pile(self.base + '/gone'), 'broken')

    def test_a_site_that_turns_robots_away_everywhere_is_unchecked_not_broken(self):
        """The Ohio state sites answer 404 to a robot for every page, front page included."""
        self.assertEqual(self.pile(self.away + '/child-support/welcome'), 'unchecked')
        self.assertEqual(self.pile(self.away + '/'), 'unchecked')

    def test_a_refusal_is_unchecked(self):
        self.assertEqual(self.pile(self.base + '/refused'), 'unchecked')

    def test_a_parked_or_taken_over_address_is_broken_even_though_it_loads(self):
        self.assertEqual(self.pile(self.base + '/parked'), 'broken')
        self.assertEqual(self.pile(self.base + '/gambling'), 'broken')

    def test_a_page_that_loads_but_says_not_found_is_broken(self):
        self.assertEqual(self.pile(self.base + '/soft404'), 'broken')

    def test_an_address_that_forwards_to_another_website_is_moved(self):
        pile, why, final = linkcheck.Checker().check(self.base + '/moved')
        self.assertEqual(pile, 'moved')
        self.assertIn('localhost', why)

    def test_same_organization_is_judged_by_site_not_by_exact_host(self):
        self.assertEqual(linkcheck.site_of('https://energyhelp.ohio.gov/'), linkcheck.site_of('https://jfs.ohio.gov/x'))
        self.assertNotEqual(linkcheck.site_of('https://www.wvpti.org/'), linkcheck.site_of('https://iontogell.website/'))
        self.assertEqual(linkcheck.site_of('https://health.state.mn.us/'), 'state.mn.us')


class LedgerTests(unittest.TestCase):
    TODAY = date(2026, 11, 15)

    def ledger(self, **entries):
        return {'max_age_days': 180, 'opened_in_browser': entries}

    def test_a_recently_opened_link_is_confirmed(self):
        led = self.ledger(**{'https://a.example/x': {'opened': '2026-11-01'}})
        self.assertTrue(linkcheck.confirmed('https://a.example/x', 'https://a.example/x', led, self.TODAY))

    def test_confirmation_runs_out(self):
        led = self.ledger(**{'https://a.example/x': {'opened': '2026-01-01'}})
        self.assertFalse(linkcheck.confirmed('https://a.example/x', 'https://a.example/x', led, self.TODAY))

    def test_an_unlisted_link_is_not_confirmed(self):
        self.assertFalse(linkcheck.confirmed('https://a.example/x', 'https://a.example/x', self.ledger(), self.TODAY))

    def test_a_forward_to_somewhere_new_cancels_the_confirmation(self):
        led = self.ledger(**{'https://old.example/': {'opened': '2026-11-01', 'lands_on': 'new.example'}})
        self.assertTrue(linkcheck.confirmed('https://old.example/', 'https://www.new.example/home', led, self.TODAY))
        self.assertFalse(linkcheck.confirmed('https://old.example/', 'https://casino.example/', led, self.TODAY))

    def test_report_lists_only_what_needs_a_person(self):
        results = {
            'https://ok.example/': ('ok', '200', 'https://ok.example/'),
            'https://dead.example/x': ('broken', 'HTTP 404', 'https://dead.example/x'),
            'https://quiet.example/': ('unchecked', 'the site refused the robot (HTTP 403)', 'https://quiet.example/'),
            'https://due.example/': ('unchecked', 'the site refused the robot (HTTP 403)', 'https://due.example/'),
        }
        used = {u: {'listing'} for u in results}
        led = self.ledger(**{'https://quiet.example/': {'opened': '2026-11-01'}})
        text, needs = linkcheck.report(results, used, led, self.TODAY)
        self.assertTrue(needs)
        self.assertIn('https://dead.example/x', text)
        self.assertIn('https://due.example/', text)
        self.assertNotIn('https://quiet.example/', text)
        self.assertNotIn('https://ok.example/', text)
        text, needs = linkcheck.report({k: results[k] for k in ('https://ok.example/', 'https://quiet.example/')}, used, led, self.TODAY)
        self.assertFalse(needs)

    def test_the_committed_ledger_is_well_formed_and_only_names_links_in_use(self):
        led = json.loads((ROOT / 'data' / 'link-checks.json').read_text(encoding='utf-8'))
        self.assertIsInstance(led['max_age_days'], int)
        import ymt_lib as lib
        used = set()
        for r in lib.all_records(lib.load()):
            used.update(u for u in [r.get('url')] + list(r.get('sources', [])) if u)
        ohio = json.loads((ROOT / 'data' / 'resources.json').read_text(encoding='utf-8'))
        used.update(r['url'] for r in ohio['resources'] if r.get('url'))
        for url, entry in led['opened_in_browser'].items():
            self.assertTrue(url.startswith('https://'), url)
            self.assertLessEqual(date.fromisoformat(entry['opened']), date.today(), url)
            self.assertIn(url, used, f'{url} is in the ledger but no listing uses it')


if __name__ == '__main__':
    unittest.main()
