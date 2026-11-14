#!/usr/bin/env python3
"""Build the canonical family guide; other pages are maintained as static source."""
import sys
from build_family_guide import ROOT, outputs
for path, content in outputs().items():
    target = ROOT / path
    if '--check' in sys.argv:
        assert target.read_text() == content, f'{path} is stale'
    else:
        target.write_text(content)
print('Family guide is current')
