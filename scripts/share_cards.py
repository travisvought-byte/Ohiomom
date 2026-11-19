#!/usr/bin/env python3
"""Draw the pictures a phone or Facebook shows when someone shares a link, and the site icon.

    python3 scripts/share_cards.py

Writes three 1200 by 630 cards (assets/share.jpg, ohio/assets/share.jpg, assets/share-family-guide.jpg) and two
icon sizes made from assets/icon.svg (assets/icon-48.png, assets/icon-180.png).

This is not part of the build or the tests. It needs Playwright and Pillow
(pip install playwright pillow; playwright install chromium). Run it only when the wording or the look
of a card changes, look at the pictures, and commit them. The words on a card must stay true of the site.
"""
import asyncio
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEART = '<i>♥</i>'
CARDS = {
    'assets/share.jpg': {
        'logo': 'Yoga Mom <span>Talk</span>' + HEART,
        'headline': 'Help for moms<br>in all 50 states',
        'line': 'Find help, meet other moms, and see what your state offers. Plain words, real phone numbers.',
        'first': 'www.yogamomtalk.com',
        'second': 'Free. No sign-up.',
    },
    'ohio/assets/share.jpg': {
        'logo': 'Ohio<span>Mom</span>' + HEART,
        'headline': 'Find your people,<br>close to home',
        'line': 'Meet other moms, find family events near you, and get help with the hard stuff.',
        'first': 'For moms all over Ohio',
        'second': 'Free. No sign-up.',
    },
    'assets/share-family-guide.jpg': {
        'logo': 'Ohio<span>Mom</span>' + HEART,
        'headline': 'Family guide:<br>autism, ADHD and more',
        'line': "Free programs and clear next steps for Ohio families, sorted by your child's age. No diagnosis needed.",
        'first': 'For Ohio families',
        'second': 'Free. No sign-up.',
    },
}
FILL = '''(card) => { for (const [id, html] of Object.entries(card)) document.getElementById(id).innerHTML = html;
  const box = document.querySelector('.pad').getBoundingClientRect();
  return [...document.querySelectorAll('.pad *')].every(e => e.getBoundingClientRect().right <= box.right + 1); }'''
# 180 is the size an iPhone uses on the home screen: it rounds the corners itself, so that one is a full square.
ICONS = {'assets/icon-48.png': (48, False), 'assets/icon-180.png': (180, True)}


def small_png(shot, colors=48):
    """The same picture with a short list of colors, so the file is a few kilobytes."""
    from PIL import Image
    image = Image.open(io.BytesIO(shot)).convert('RGBA')
    out = io.BytesIO()
    image.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(out, 'PNG', optimize=True)
    return out.getvalue()


async def main():
    from playwright.async_api import async_playwright
    template = (ROOT / 'templates/share-card.html').as_uri()
    icon = (ROOT / 'assets/icon.svg').read_text()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1200, 'height': 630}, device_scale_factor=1)
        for path, card in CARDS.items():
            await page.goto(template)
            fits = await page.evaluate(FILL, card)
            assert fits, f'{path}: the words run off the card. Shorten them.'
            await page.evaluate('document.fonts.ready')
            (ROOT / path).write_bytes(await page.screenshot(type='jpeg', quality=86))
            print('wrote', path)
        for path, (size, square) in ICONS.items():
            svg = icon.replace(' rx="14"', '') if square else icon
            assert not square or svg != icon
            await page.set_viewport_size({'width': size, 'height': size})
            await page.set_content(f'<body style="margin:0">{svg}</body>'.replace('<svg ', f'<svg width="{size}" height="{size}" style="display:block" '))
            (ROOT / path).write_bytes(small_png(await page.screenshot(omit_background=not square)))
            print('wrote', path)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
