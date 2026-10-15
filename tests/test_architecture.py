"""Executable layer boundaries: allowed directions matter in addition to acyclicity."""
import ast
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from architecture_table import (ADAPTERS, ALLOWED, CORE_EXTERNAL, FORBIDDEN_CORE_NAMES,
                                allowed_edges)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'scripts' / 'novel_ledger'


def imports(tree):
    """Return all internal and external edges, including nested/absolute imports."""
    internal, external = set(), set()

    def absolute(name):
        pieces = name.split('.')
        if pieces[0] == 'novel_ledger':
            internal.add(pieces[1] if len(pieces) > 1 else '__init__')
        else:
            external.add(pieces[0])

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                absolute(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if node.level != 1:
                    internal.add('<outside-package>')
                elif node.module:
                    internal.add(node.module.split('.')[0])
                else:
                    internal.update(alias.name.split('.')[0] for alias in node.names)
            elif node.module == 'novel_ledger':
                internal.update(alias.name.split('.')[0] for alias in node.names)
            else:
                absolute(node.module or '')
    return internal, external


def forbidden_core_accesses(tree):
    """Block builtin aliases too: loading `open` is already an I/O capability leak.

    Name and attribute lookups cover the direct spellings; `getattr`, `__builtins__`
    and `__globals__` are banned outright so the ban cannot be spelled around.
    """
    return {(node.lineno, node.id if isinstance(node, ast.Name) else node.attr)
            for node in ast.walk(tree)
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                and node.id in FORBIDDEN_CORE_NAMES)
            or (isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_CORE_NAMES)}


def diagram():
    source = (ROOT / 'references' / 'architecture.md').read_text(encoding='utf-8')
    return re.search(r'```mermaid\n(.*?)```', source, re.S).group(1).strip()


def diagram_edges():
    """Resolve documented edges whose endpoints name a concrete module.

    The diagram is an intentional summary: aggregate nodes (for example the pure
    rule group) and omitted edges are allowed. What is not allowed is a drawn
    edge that the declared dependency table does not permit.
    """
    source = diagram()
    labels = {}
    for match in re.finditer(r'(\w+)\[([^\]]+)\]', source):
        labels.setdefault(match.group(1), match.group(2))
    names = sorted(ALLOWED, key=len, reverse=True)

    def resolve(node):
        label = labels.get(node, '')
        for name in names:
            if re.search(r'(?<![\w])' + re.escape(name) + r'(?![\w])', label):
                return name
        return None

    resolved = []
    for match in re.finditer(r'(\w+)(?:\[[^\]]+\])?\s*-->\s*(\w+)(?:\[[^\]]+\])?\s*$', source, re.M):
        left, right = resolve(match.group(1)), resolve(match.group(2))
        if left and right:
            resolved.append((left, right))
    return resolved, labels


class ArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {path.stem: path for path in PACKAGE.glob('*.py')}
        cls.sources['novel'] = ROOT / 'scripts' / 'novel.py'
        cls.trees = {name: ast.parse(path.read_text(encoding='utf-8'), feature_version=(3, 9))
                     for name, path in cls.sources.items()}

    def test_every_module_is_classified_as_core_or_adapter(self):
        """A module missing from both sets would silently escape the I/O ban."""
        self.assertEqual(set(self.sources), set(ALLOWED))
        self.assertEqual(set(ALLOWED), set(CORE_EXTERNAL) | ADAPTERS)
        self.assertEqual(set(CORE_EXTERNAL) & ADAPTERS, set())

    def test_every_module_has_an_explicit_dependency_boundary(self):
        self.assertEqual(set(self.sources), set(ALLOWED))
        for name, tree in self.trees.items():
            with self.subTest(module=name):
                internal, _ = imports(tree)
                self.assertFalse(internal - ALLOWED[name],
                                 f'{name} crosses its layer: {sorted(internal - ALLOWED[name])}')

    def test_complete_import_graph_is_acyclic(self):
        graph = {name: imports(tree)[0] for name, tree in self.trees.items()}

        def visit(name, trail):
            self.assertNotIn(name, trail, ' -> '.join(trail + [name]))
            for dependency in graph.get(name, ()):
                visit(dependency, trail + [name])

        for name in graph:
            visit(name, [])

    def test_core_cannot_import_or_access_io_or_dynamic_execution(self):
        for name, allowed in CORE_EXTERNAL.items():
            with self.subTest(module=name):
                tree = self.trees[name]
                _, external = imports(tree)
                self.assertFalse(external - allowed,
                                 f'{name} has unapproved external imports: {sorted(external - allowed)}')
                self.assertEqual(forbidden_core_accesses(tree), set())

    def test_scanner_finds_deferred_absolute_relative_and_from_imports(self):
        tree = ast.parse('''
def hidden():
    import novel_ledger.delivery as files
    from novel_ledger import host
    from novel_ledger.sqlite_store import SQLiteRepository
    from . import workspace
    from .context import build
    from pathlib import Path
    from os import environ
''')
        internal, external = imports(tree)
        self.assertEqual(internal, {'delivery', 'host', 'sqlite_store', 'workspace', 'context'})
        self.assertEqual(external, {'pathlib', 'os'})

    def test_scanner_blocks_builtin_aliases_and_path_access(self):
        tree = ast.parse('''
def hidden():
    reader = open
    __import__('os')
    eval('1')
    exec('x = 1')
    Path('/tmp')
    module.Path('/tmp')
    builtins.open('/tmp')
''')
        self.assertTrue({'open', '__import__', 'eval', 'exec', 'Path'}
                        <= {name for _, name in forbidden_core_accesses(tree)})

    def test_scanner_blocks_builtin_lookup_bypasses(self):
        """The four spellings that used to slip past a name-only ban."""
        tree = ast.parse('''
def hidden():
    getattr(__builtins__, 'open')('/tmp')
    vars(__builtins__)['open']('/tmp')
    __builtins__['open']('/tmp')
    (lambda: 1).__globals__['__builtins__']
''')
        found = {name for _, name in forbidden_core_accesses(tree)}
        self.assertEqual(found, {'getattr', '__builtins__', '__globals__'})

    def test_diagram_edges_are_allowed_by_the_dependency_table(self):
        edges, labels = diagram_edges()
        self.assertTrue(edges, 'At least the concrete diagram edges must resolve.')
        allowed = allowed_edges()
        for caller, dependency in edges:
            with self.subTest(edge=f'{caller}->{dependency}'):
                self.assertIn((caller, dependency), allowed,
                              f'{caller} -> {dependency} is drawn but not allowed.')
        # The aggregate node is a group, not a module: it must stay unresolved
        # rather than silently weakening this check.
        self.assertTrue(any(label.strip() == '纯领域规则' for label in labels.values()),
                        'The pure-rule group node must remain an aggregate.')

    def test_host_uses_public_application_capabilities(self):
        for name in ('host', 'novel'):
            with self.subTest(module=name):
                self.assertFalse(any(isinstance(node, ast.Attribute) and node.attr == 'repo'
                                     for node in ast.walk(self.trees[name])),
                                 'The caller must not reach through Application to persistence.')
                self.assertFalse(any(isinstance(node, ast.Attribute)
                                     and isinstance(node.value, ast.Name) and node.value.id == 'app'
                                     and node.attr.startswith('_')
                                     for node in ast.walk(self.trees[name])),
                                 'Callers must use public application capabilities.')

    def test_sqlite_owns_storage_names_without_delivery_responsibilities(self):
        tree = self.trees['sqlite_store']
        names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertIn('SQLiteRepository', names)
        repository = next(node for node in tree.body
                          if isinstance(node, ast.ClassDef) and node.name == 'SQLiteRepository')
        self.assertNotIn('retire', {node.name for node in repository.body
                                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))})
        self.assertFalse(any(isinstance(node, ast.Name) and node.id == 'FORM_ARTIFACTS'
                             or isinstance(node, ast.Constant) and node.value == 'work'
                             for node in ast.walk(tree)))
        for name in ('application', 'context', 'delivery', 'presentation', 'bookpage', 'host', 'workspace'):
            with self.subTest(module=name):
                self.assertFalse(any(isinstance(node, ast.Constant) and isinstance(node.value, str)
                                     and 'novel.sqlite3' in node.value
                                     for node in ast.walk(self.trees[name])),
                                 'Storage filenames belong only to the concrete storage adapter.')

    def test_publication_and_file_views_have_only_read_capabilities(self):
        readable = {'load', 'read_document', 'headers', 'get'}
        writable = {'transaction', 'after_commit', 'put', 'save', 'document', 'add_task',
                    'seal', 'finish_task', 'cancel_pending', 'add_chapter', 'fork',
                    'promote', 'bind_session', 'record'}
        for name in ('delivery', 'bookpage', 'publication', 'presentation'):
            with self.subTest(module=name):
                for node in ast.walk(self.trees[name]):
                    if not isinstance(node, ast.Attribute):
                        continue
                    self.assertNotIn(node.attr, writable,
                                     f'{name} must not perform persistence writes.')
                    if isinstance(node.value, ast.Name) and node.value.id == 'repo':
                        self.assertIn(node.attr, readable,
                                      f'{name} must depend only on PublicationReader.')

    def test_svg_contains_exactly_the_documented_nodes_and_edges(self):
        nodes, edges = set(), set()
        for line in diagram().splitlines():
            match = re.fullmatch(r'\s*(\w+)(?:\[[^]]+\])? --> (\w+)(?:\[[^]]+\])?\s*', line)
            if match:
                left, right = match.groups()
                nodes.update((left, right))
                edges.add(left + '->' + right)
        self.assertTrue(edges, 'The architecture diagram must contain dependencies.')
        svg = ET.parse(ROOT / 'docs' / 'architecture.svg')
        namespace = {'svg': 'http://www.w3.org/2000/svg'}
        actual_nodes, actual_edges = set(), set()
        for element in svg.findall('.//svg:g', namespace):
            title = element.find('svg:title', namespace)
            if title is not None and element.get('class') == 'node':
                actual_nodes.add(title.text)
            elif title is not None and element.get('class') == 'edge':
                actual_edges.add(title.text)
        self.assertEqual(actual_nodes, nodes)
        self.assertEqual(actual_edges, edges)


if __name__ == '__main__':
    unittest.main()
