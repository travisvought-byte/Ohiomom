#!/usr/bin/env python3
"""Compare the site files in this repository with the live Wix site, or publish them.

    python3 scripts/publish_wix.py --check      read-only: say what differs, change nothing
    python3 scripts/publish_wix.py --publish    send the files, then read the site back and compare again

Environment:
    WIX_API_KEY      a Wix API key (GitHub secret). It is never printed.
    WIX_ACCOUNT_ID   the Wix account the key belongs to (GitHub secret).
    WIX_TOKEN        instead of the two above: a login token from the Wix command line
                     (`npx @wix/cli@latest token` after `npx @wix/cli@latest login`). It names its own account
                     and is never printed.
    WIX_SITE_ID      optional. Without it the site is found by name among the account's headless sites.

The calls are the ones in Wix's own recipe, "Upload a Website or HTML Files":
https://dev.wix.com/docs/api-reference/account-level/sites/skills/upload-a-website-or-html-files
A raw upload ("drop") replaces the whole file set, so this script always sends the complete set:
every site file in the repository, plus any file that is live but not in the repository, unchanged.
Nothing is deleted from the live site by this script.
"""
import io
import json
import mimetypes
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_NAME = 'OhioMom'
API = os.environ.get('WIX_API_BASE', 'https://www.wixapis.com')
DOWNLOAD = os.environ.get('WIX_DOWNLOAD_BASE', 'https://www.wix.com')
# What is in the repository but is not part of the website.
NOT_SITE = ('README.md', 'LICENSE', 'package.json', 'package-lock.json')
NOT_SITE_DIRS = ('scripts/', 'tests/', 'data/', 'templates/', '.github/', 'node_modules/')
# Wix removes its own script tag from a page when it stores it and adds it back when it serves it.
WIX_TAG = re.compile(rb'<script id="wix-site-script"[^>]*></script>\n?')


def is_site_file(path):
    name = path.rsplit('/', 1)[-1]
    return not (path in NOT_SITE or path.startswith(NOT_SITE_DIRS) or name.startswith('.'))


def stored_form(path, data):
    """The bytes Wix keeps for a file: pages lose the Wix script tag, everything else is kept as sent."""
    return WIX_TAG.sub(b'', data) if path.endswith(('.html', '.htm')) else data


def repo_files(root=ROOT):
    listed = subprocess.check_output(['git', '-C', str(root), 'ls-files'], text=True).split('\n')
    return {p: stored_form(p, (Path(root) / p).read_bytes()) for p in listed if p and is_site_file(p)}


def compare(repo, live):
    """What publishing would change. 'extra' files are live but not in the repository; they are kept."""
    live = {p: stored_form(p, d) for p, d in live.items()}
    return {
        'changed': sorted(p for p in repo if p in live and repo[p] != live[p]),
        'added': sorted(p for p in repo if p not in live),
        'extra': sorted(p for p in live if p not in repo),
        'same': sum(1 for p in repo if p in live and repo[p] == live[p]),
    }


def complete_set(repo, live):
    """Everything a drop must carry: the repository's files, and live files the repository does not have."""
    files = {p: d for p, d in live.items() if p not in repo}
    files.update(repo)
    return files


def multipart(files):
    """multipart/form-data with one part per file, each named "files", its filename the site path."""
    boundary = 'ymt' + uuid.uuid4().hex
    body = io.BytesIO()
    for path in sorted(files):
        kind = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{path}"\r\n'
                   f'Content-Type: {kind}\r\n\r\n'.encode('utf-8'))
        body.write(files[path])
        body.write(b'\r\n')
    body.write(f'--{boundary}--\r\n'.encode('ascii'))
    return body.getvalue(), f'multipart/form-data; boundary={boundary}'


class WixError(Exception):
    pass


def call(method, url, key, account, body=None, content_type=None, site=None):
    """One authenticated call. Returns (status, bytes). The key goes in the Authorization header only."""
    headers = {'Authorization': key, 'User-Agent': 'yogamomtalk-publish'}
    if account:   # an API key needs its account named; a login token carries its own
        headers['wix-account-id'] = account
        if site:  # Wix grants an API key's site permissions (such as OAuth Apps) only when the site is named too
            headers['wix-site-id'] = site
    if isinstance(body, (dict, list)):
        body, content_type = json.dumps(body).encode('utf-8'), 'application/json'
    if content_type:
        headers['Content-Type'] = content_type
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except urllib.error.URLError as error:
        raise WixError(f'{method} {url.split("?")[0]} could not be reached: {error.reason}')


def explain(status, payload, doing):
    text = payload[:300].decode('utf-8', 'replace').replace('\n', ' ')
    hint = ''
    if status in (401, 403):
        hint = (' Wix did not accept the key for this call. Check that the key is current, that it belongs to the account in '
                'WIX_ACCOUNT_ID, and that its permissions and site access cover this site.')
    return WixError(f'{doing} failed with HTTP {status}.{hint} Wix said: {text}')


def find_site(key, account):
    wanted = os.environ.get('WIX_SITE_ID', '').strip()
    if wanted:
        return wanted
    query = {'query': {'filter': {'namespace': 'HEADLESS'}, 'cursorPaging': {'limit': 100}}}
    status, payload = call('POST', f'{API}/site-list/v2/sites/query', key, account, query)
    if status != 200:
        raise explain(status, payload, 'Looking up the site')
    sites = [s for s in json.loads(payload).get('sites', []) if s.get('displayName') == SITE_NAME]
    if len(sites) != 1:
        raise WixError(f'Expected one headless site named {SITE_NAME} in this account and found {len(sites)}. Set WIX_SITE_ID.')
    return sites[0]['id']


def live_is_last_upload(site, key, account):
    """Wix answers 200 here only when what is live is the last static upload. Anything else must not be overwritten."""
    status, payload = call('GET', f'{API}/headless-business-setup/v1/headless-business/{site}/files', key, account, site=site)
    if status != 200:
        raise explain(status, payload, 'Checking what is live')
    return len(json.loads(payload).get('files', []))


def download(site, key, account):
    status, payload = call('GET', f'{DOWNLOAD}/_api/wixstro-deployments/v1/instant-sites/{site}/download.zip', key, account, site=site)
    if status != 200:
        raise explain(status, payload, 'Downloading the live files')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return {n: archive.read(n) for n in archive.namelist() if not n.endswith('/') and n != 'wix.config.json'}


def drop(site, files, key, account):
    body, content_type = multipart(files)
    agent = 'github-actions' if os.environ.get('GITHUB_ACTIONS') else 'shell'
    url = f'{API}/headless-business-setup/v1/headless-business/{site}/drop?campaign=ci&agent={agent}'
    status, payload = call('POST', url, key, account, body, content_type, site=site)
    if status != 200:
        raise explain(status, payload, 'Uploading')
    return json.loads(payload)


def report(diff, lines):
    lines.append(f"- In step: {diff['same']} files")
    for label, key in (('Would change', 'changed'), ('Would be added', 'added'), ('Live but not in the repository (kept as they are)', 'extra')):
        if diff[key]:
            lines.append(f'- {label}: {len(diff[key])}')
            lines.extend(f'  - `{p}`' for p in diff[key][:60])
            if len(diff[key]) > 60:
                lines.append(f'  - and {len(diff[key]) - 60} more')


def finish(lines, code=0):
    text = '\n'.join(lines)
    print(text)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as out:
            out.write(text + '\n')
    return code


def main(argv):
    mode = 'publish' if '--publish' in argv else 'check'
    key, account = os.environ.get('WIX_API_KEY', '').strip(), os.environ.get('WIX_ACCOUNT_ID', '').strip()
    token = os.environ.get('WIX_TOKEN', '').strip()
    if token:
        key, account = token, ''
    lines = [f'## Wix: {mode}']
    if not key or not (account or token):
        lines.append('Not set up yet. Add the repository secrets `WIX_API_KEY` and `WIX_ACCOUNT_ID` '
                     '(README, "Publishing to Wix"). Nothing was read or changed.')
        return finish(lines)
    try:
        site = find_site(key, account)
        live_count = live_is_last_upload(site, key, account)
        repo, live = repo_files(), download(site, key, account)
        diff = compare(repo, live)
        lines.append(f'The live site has {live_count} files. The repository has {len(repo)} site files.')
        report(diff, lines)
        if not diff['changed'] and not diff['added']:
            lines.append('**The live site matches the repository. Nothing to publish.**')
            return finish(lines)
        if mode == 'check':
            lines.append('**Check only: nothing was changed.**')
            return finish(lines)
        files = complete_set(repo, live)
        if 'index.html' not in files:
            raise WixError('Refusing to upload a site with no index.html.')
        result = drop(site, files, key, account)
        after = compare(repo, download(site, key, account))
        if after['changed'] or after['added']:
            lines.append('**Uploaded, but the site read back does not match the repository. Look at this before trusting it:**')
            report(after, lines)
            return finish(lines, 1)
        lines.append(f"**Published {len(diff['changed']) + len(diff['added'])} files and read them back: the live site matches the repository.** "
                     f"{result.get('siteUrl', '')}")
        return finish(lines)
    except WixError as error:
        lines.append(f'**Stopped. Nothing was changed by this step unless an upload is reported above.** {error}')
        return finish(lines, 1)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
