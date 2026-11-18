"""Every page a visitor reads carries the suicide and homelessness help block (owner direction, November 17, 2026)."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import help_now  # noqa: E402


class HelpNowTest(unittest.TestCase):
    def test_block_follows_the_sites_rules(self):
        block = help_now.BLOCK
        for link in ('href="tel:988"', 'href="tel:211"', 'href="tel:+18774243838"', 'href="https://www.hud.gov/findshelter"'):
            self.assertEqual(block.count(link), 1, link)
        for words in ('Thinking about suicide', 'call 988', 'text 988', 'press 1', 'No safe place to sleep tonight',
                      'press 6 for homeless services', '1-877-424-3838', '24 hours a day'):
            self.assertIn(words, block)
        # The site has no text-message links, loads nothing from elsewhere, and names outside links as such.
        self.assertNotIn('sms:', block)
        self.assertNotRegex(block, r'<(script|img|iframe|link|form|input|style)\b')
        self.assertIn('href="https://www.hud.gov/findshelter" rel="noopener"', block)
        self.assertTrue(block.startswith('<aside class="help-now" aria-label="Need help now?"'))
        # A phone link shows the number it dials.
        for href, shown in re.findall(r'href="tel:([^"]+)"[^>]*>([^<]+)<', block):
            self.assertTrue(href.endswith(re.sub(r'\D', '', shown)), f'{href} vs {shown}')

    def test_every_page_carries_it_once_above_the_footer(self):
        self.assertGreaterEqual(help_now.check_pages(), 80)

    def test_builders_and_static_pages_cover_every_page(self):
        built = help_now.built_names()
        static = set(help_now.static_pages())
        self.assertFalse(built & static)
        for name in help_now.tracked_pages():
            text = (ROOT / name).read_text(encoding='utf-8')
            if help_now.wants_help(name, text):
                self.assertTrue(name in built or name in static, name)
        # The OhioMom pages are static source, so the script is what keeps the block on them.
        self.assertIn('ohio/index.html', static)
        self.assertIn('ohio/help/housing.html', static)
        self.assertIn('family-guide.html', built)
        self.assertIn('index.html', built)

    def test_adding_twice_changes_nothing_and_forwarding_pages_are_left_alone(self):
        page = '<html><head></head><body><main></main>\n<footer class="foot"></footer></body></html>'
        once = help_now.add_help(page, 'page')
        self.assertEqual(help_now.add_help(once, 'page'), once)
        self.assertEqual(help_now.strip_help(once), page)
        self.assertEqual(once, '<html><head></head><body><main></main>\n' + help_now.LINE + '<footer class="foot"></footer></body></html>')
        self.assertFalse(help_now.wants_help('yoga.html', '<meta http-equiv="refresh" content="0; url=ohio/yoga.html"><footer></footer>'))
        self.assertFalse(help_now.wants_help('templates/family-guide.html', page))


if __name__ == '__main__':
    unittest.main()
