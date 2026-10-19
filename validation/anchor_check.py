"""Check local links and exact heading anchors in the active repository guides."""
import argparse
import html
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit


def visible_lines(source):
    """Ignore fenced examples: their headings and links are not document navigation."""
    fence = None
    for number, line in enumerate(source.splitlines(), 1):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield number, line


def slug(title):
    title = html.unescape(re.sub(r'<[^>]+>', '', title)).strip().lower()
    title = ''.join(char for char in title
                    if char in '_- ' or unicodedata.category(char)[0] in 'LNM')
    return title.replace(' ', '-')


def heading_ids(source):
    identifiers, used = set(), set()
    for _, line in visible_lines(source):
        for explicit in re.finditer(r'<(?:a|span)\b[^>]*\b(?:id|name)=["\']([^"\']+)["\']', line):
            identifiers.add(explicit.group(1))
        heading = re.match(r'^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$', line)
        if not heading:
            continue
        base = slug(heading.group(1))
        candidate, suffix = base, 0
        while candidate in used:
            suffix += 1
            candidate = base + '-' + str(suffix)
        used.add(candidate)
        identifiers.add(candidate)
    return identifiers


def active_files(root):
    return sorted(set(root.glob('*.md')) | set((root / 'references').rglob('*.md'))
                  | set((root / 'docs').rglob('*.md')))


def check(root):
    files, bad, headings = active_files(root), [], {}
    for path in files:
        source = path.read_text(encoding='utf-8')
        for number, line in visible_lines(source):
            line = re.sub(r'(`+).*?\1', '', line)
            for match in re.finditer(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)', line):
                raw = match.group(1).strip('<>')
                url = urlsplit(raw)
                if url.scheme or url.netloc:
                    continue
                target = (path.parent / unquote(url.path)).resolve() if url.path else path.resolve()
                if not target.exists():
                    bad.append((str(path.relative_to(root)), number, raw, 'missing file'))
                    continue
                if url.fragment and target.suffix.lower() in ('.md', '.markdown'):
                    if target not in headings:
                        headings[target] = heading_ids(target.read_text(encoding='utf-8'))
                    if unquote(url.fragment) not in headings[target]:
                        bad.append((str(path.relative_to(root)), number, raw, 'anchor not found'))
    return files, bad


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    files, bad = check(args.root.resolve())
    print('checked files:', len(files), 'bad references:', len(bad))
    for row in bad:
        print(row)
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
