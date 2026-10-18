"""One-off: verify every intra-repo markdown anchor reference resolves."""
import io
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = list(root.glob('*.md')) + list(root.glob('references/*.md')) + [root / 'docs' / 'README.md']
heads = {}
for fp in files:
    text = io.open(fp, encoding='utf-8').read()
    heads[fp.resolve()] = {m.group(1) for m in re.finditer(r'^#+\s+(.+)$', text, re.M)}

def slug(t):
    t = re.sub(r'[（）()：:、，,。.·—\[\]`*/？?"“”\'；;！]', '', t.strip())
    return t.replace(' ', '-')

bad = []
for fp in files:
    text = io.open(fp, encoding='utf-8').read()
    for m in re.finditer(r'\]\(([^)#]+\.md)#([^)]+)\)', text):
        target, anchor = m.group(1), m.group(2)
        tfp = (fp.parent / target).resolve()
        titles = heads.get(tfp)
        if titles is None:
            bad.append((fp.name, target, anchor, 'missing file'))
            continue
        if not any(slug(t) == anchor or t.replace(' ', '-') == anchor or anchor in t for t in titles):
            bad.append((fp.name, target, anchor, 'anchor not found'))
print('checked files:', len(files), 'bad anchors:', len(bad))
for row in bad:
    print(row)
