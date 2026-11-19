"""The publish script against a stand-in for Wix. Run: python3 -m unittest tests.test_publish

The stand-in behaves the way Wix's recipe describes: an upload replaces the whole file set, pages are stored
without the Wix script tag, and a call with the wrong key is refused. What this cannot prove is that the real
Wix accepts an API key for these calls; the first real "check" run does that.
"""
import contextlib
import email
import email.policy
import io
import json
import os
import sys
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import publish_wix as pw  # noqa: E402

KEY, ACCOUNT, SITE = 'test-key-not-real', 'account-1', 'site-1'
TOKEN = 'test-login-token-not-real'
TAG = b'<script id="wix-site-script" src="https://example.invalid/s.js" data-client-id="x" async></script>'


class FakeWix(BaseHTTPRequestHandler):
    store, drops, live_ok = {}, [], True

    def log_message(self, *args):
        pass

    def answer(self, status, body, kind='application/json'):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        if self.headers.get('Authorization') == KEY and self.headers.get('wix-account-id') == ACCOUNT:
            # Calls about the site must name it, or Wix leaves out the key's site permissions.
            if SITE in self.path and self.headers.get('wix-site-id') != SITE:
                self.answer(403, {'message': "PERMISSION_DENIED: permission 'OAUTH_APP.APP_CREATE' denied"})
                return False
            return True
        # A login token from the Wix command line names its own account.
        if self.headers.get('Authorization') == TOKEN and 'wix-account-id' not in self.headers:
            return True
        self.answer(403, {'message': 'PERMISSION_DENIED'})
        return False

    def do_GET(self):
        if not self.allowed():
            return
        cls = type(self)
        if self.path == f'/headless-business-setup/v1/headless-business/{SITE}/files':
            if not cls.live_ok:
                return self.answer(409, {'message': 'LIVE_SITE_CHANGED'})
            return self.answer(200, {'revision': '1', 'files': [{'path': p, 'size': len(d)} for p, d in cls.store.items()]})
        if self.path == f'/_api/wixstro-deployments/v1/instant-sites/{SITE}/download.zip':
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w') as z:
                z.writestr('wix.config.json', '{}')
                for p, d in cls.store.items():
                    z.writestr(p, d)
            return self.answer(200, buf.getvalue(), 'application/zip')
        self.answer(404, {'message': 'not found'})

    def do_POST(self):
        if not self.allowed():
            return
        cls = type(self)
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if self.path == '/site-list/v2/sites/query':
            asked = json.loads(body)['query']['filter']
            sites = [{'id': SITE, 'displayName': 'OhioMom'}, {'id': 'other', 'displayName': 'Something else'}] if asked == {'namespace': 'HEADLESS'} else []
            return self.answer(200, {'sites': sites})
        if self.path.startswith(f'/headless-business-setup/v1/headless-business/{SITE}/drop'):
            message = email.message_from_bytes(b'Content-Type: ' + self.headers['Content-Type'].encode() + b'\r\n\r\n' + body, policy=email.policy.HTTP)
            sent = {}
            for part in message.iter_parts():
                assert part.get_param('name', header='content-disposition') == 'files'
                sent[part.get_filename()] = part.get_payload(decode=True)
            cls.drops.append(sorted(sent))
            # A raw drop replaces everything; pages are stored without the Wix tag.
            cls.store = {p: pw.stored_form(p, d) for p, d in sent.items()}
            return self.answer(200, {'uploadId': 'u1', 'siteUrl': 'https://example.wix-site-host.com'})
        self.answer(404, {'message': 'not found'})


class PublishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), FakeWix)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.patches = [mock.patch.object(pw, 'API', base), mock.patch.object(pw, 'DOWNLOAD', base)]
        for p in cls.patches:
            p.start()
        cls.repo = pw.repo_files()

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        cls.server.shutdown()

    def setUp(self):
        FakeWix.store, FakeWix.drops, FakeWix.live_ok = dict(self.repo), [], True

    def run_main(self, mode, key=KEY, account=ACCOUNT, site='', token=''):
        env = {'WIX_API_KEY': key, 'WIX_ACCOUNT_ID': account, 'WIX_TOKEN': token, 'WIX_SITE_ID': site,
               'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}
        out = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=False), contextlib.redirect_stdout(out):
            os.environ.pop('GITHUB_STEP_SUMMARY', None)
            code = pw.main(['--' + mode])
        return code, out.getvalue()

    def test_what_counts_as_a_site_file(self):
        for path in ('index.html', 'ohio/assets/site.css', 'js/wix/client.js', 'states/oh.html', 'robots.txt', 'family-guide.html',
                     'assets/share.jpg', 'ohio/assets/share.jpg', 'assets/icon-180.png', 'assets/icon.svg'):
            self.assertTrue(pw.is_site_file(path), path)
        for path in ('README.md', 'LICENSE', 'scripts/build.py', 'tests/test_ymt.py', 'data/ymt/states.json', 'templates/family-guide.html', 'templates/share-card.html', 'scripts/share_cards.py',
                     '.github/workflows/validate.yml', 'package.json', 'package-lock.json', '.nojekyll', '.gitattributes'):
            self.assertFalse(pw.is_site_file(path), path)
        self.assertIn('index.html', self.repo)
        self.assertGreater(len(self.repo), 100)
        self.assertFalse([p for p in self.repo if p.startswith(('scripts/', 'tests/', 'data/', '.'))])

    def test_pages_are_compared_the_way_wix_stores_them(self):
        page = b'<head>' + TAG + b'</head>'
        self.assertEqual(pw.stored_form('ohio/index.html', page), b'<head></head>')
        self.assertEqual(pw.stored_form('ohio/assets/site.js', page), page, 'only pages lose the tag')
        self.assertFalse(any(b'wix-site-script' in d for p, d in self.repo.items() if p.endswith('.html')))

    def test_multipart_carries_every_byte_and_path(self):
        files = {'index.html': b'<p>caf\xc3\xa9</p>\r\n', 'assets/a.bin': bytes(range(256)), 'ohio/help/bills.html': b''}
        body, kind = pw.multipart(files)
        message = email.message_from_bytes(b'Content-Type: ' + kind.encode() + b'\r\n\r\n' + body, policy=email.policy.HTTP)
        got = {part.get_filename(): part.get_payload(decode=True) for part in message.iter_parts()}
        self.assertEqual(got, files)

    def test_no_secrets_means_nothing_happens(self):
        code, out = self.run_main('publish', key='', account='')
        self.assertEqual(code, 0)
        self.assertIn('Not set up yet', out)
        self.assertEqual(FakeWix.drops, [])

    def test_check_in_step(self):
        code, out = self.run_main('check')
        self.assertEqual(code, 0, out)
        self.assertIn('matches the repository', out)
        self.assertEqual(FakeWix.drops, [])

    def test_check_reports_and_changes_nothing(self):
        FakeWix.store['index.html'] = b'old'
        del FakeWix.store['about.html']
        FakeWix.store['assets/leftover.js'] = b'x'
        before = dict(FakeWix.store)
        code, out = self.run_main('check')
        self.assertEqual(code, 0, out)
        for expected in ('Would change: 1', '`index.html`', 'Would be added: 1', '`about.html`', 'kept as they are', '`assets/leftover.js`', 'nothing was changed'):
            self.assertIn(expected, out)
        self.assertEqual(FakeWix.drops, [])
        self.assertEqual(FakeWix.store, before)

    def test_publish_sends_the_complete_set_and_reads_it_back(self):
        FakeWix.store['index.html'] = b'old'
        del FakeWix.store['about.html']
        FakeWix.store['assets/leftover.js'] = b'x'
        code, out = self.run_main('publish')
        self.assertEqual(code, 0, out)
        self.assertEqual(len(FakeWix.drops), 1, 'one upload')
        self.assertEqual(FakeWix.drops[0], sorted(list(self.repo) + ['assets/leftover.js']), 'every site file, and the live file the repository does not have')
        self.assertEqual(FakeWix.store['index.html'], self.repo['index.html'])
        self.assertEqual(FakeWix.store['assets/leftover.js'], b'x', 'nothing is deleted from the live site')
        self.assertIn('Published 2 files and read them back', out)

    def test_publish_with_nothing_to_do_uploads_nothing(self):
        code, out = self.run_main('publish')
        self.assertEqual(code, 0, out)
        self.assertEqual(FakeWix.drops, [])

    def test_a_refused_key_stops_everything_and_is_not_printed(self):
        FakeWix.store['index.html'] = b'old'
        code, out = self.run_main('publish', key='wrong-key-value')
        self.assertEqual(code, 1)
        self.assertIn('HTTP 403', out)
        self.assertNotIn('wrong-key-value', out)
        self.assertEqual(FakeWix.drops, [])

    def test_never_overwrites_a_site_that_is_not_its_last_upload(self):
        FakeWix.store['index.html'] = b'old'
        FakeWix.live_ok = False
        code, out = self.run_main('publish')
        self.assertEqual(code, 1)
        self.assertIn('Checking what is live failed with HTTP 409', out)
        self.assertEqual(FakeWix.drops, [])

    def test_a_login_token_works_without_a_key_and_is_not_printed(self):
        FakeWix.store['index.html'] = b'old'
        code, out = self.run_main('publish', key='', account='', token=TOKEN, site=SITE)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(FakeWix.drops), 1)
        self.assertEqual(FakeWix.store['index.html'], self.repo['index.html'])
        self.assertNotIn(TOKEN, out)

    def test_site_id_can_be_given_instead_of_looked_up(self):
        code, out = self.run_main('check', site=SITE)
        self.assertEqual(code, 0, out)
        code, out = self.run_main('check', site='not-a-site')
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
