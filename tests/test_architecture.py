"""Executable layer boundaries: allowed directions matter in addition to acyclicity."""
import ast
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'scripts' / 'novel_ledger'

# A new module or dependency requires an explicit architectural decision here.
# In particular, two modules can remain acyclic while still crossing a layer.
ALLOWED = {
    '__init__': set(),
    'contracts': set(),
    'ports': {'contracts'},
    'book_state': {'contracts'},
    'craft': {'contracts'},
    'creation': {'contracts'},
    'design_queries': set(),
    'editorial': {'contracts'},
    'entities': {'contracts'},
    'evidence': {'contracts'},
    'facts': {'contracts', 'entities', 'evidence', 'narrative', 'spatial'},
    'narrative': {'contracts'},
    'planning': {'contracts', 'entities', 'narrative', 'craft', 'story_memory'},
    'quality': {'contracts', 'evidence'},
    'result_templates': {'contracts', 'world', 'scopes', 'editorial', 'narrative'},
    'revision_impact': {'contracts', 'story_memory'},
    'scopes': {'contracts'},
    'spatial': {'contracts'},
    'story_memory': {'contracts'},
    'understanding': {'contracts'},
    'world': {'contracts'},
    'briefs': {'contracts', 'creation'},
    'workflow': {'contracts', 'creation', 'facts', 'narrative', 'planning', 'quality',
                 'scopes', 'world', 'craft', 'editorial', 'understanding',
                 'design_queries', 'evidence'},
    'application': {'contracts', 'ports', 'creation', 'facts', 'narrative', 'planning',
                    'quality', 'workflow', 'world', 'craft', 'editorial',
                    'story_memory', 'understanding', 'revision_service', 'contract_activation'},
    'revision_service': {'contracts', 'ports', 'editorial', 'facts', 'narrative', 'revision_impact',
                         'story_memory', 'understanding', 'workflow'},
    'contract_activation': {'contracts', 'ports', 'workflow'},
    'context': {'contracts', 'ports', 'briefs', 'creation', 'narrative', 'scopes',
                'world', 'editorial', 'story_memory', 'understanding', 'planning',
                'design_queries'},
    'publication': {'ports'},
    'workspace': {'contracts'},
    'delivery': {'contracts', 'ports', 'result_templates', 'publication', 'workspace'},
    'bookpage': {'contracts', 'ports', 'publication', 'workspace', 'planning',
                 'world', 'creation', 'understanding', 'briefs'},
    'presentation': {'ports', 'bookpage', 'delivery', 'workspace'},
    'sqlite_store': {'contracts', 'book_state'},
    'host': {'contracts', 'ports'},
    'bootstrap': {'contracts', 'application', 'context', 'presentation', 'sqlite_store',
                  'workspace', 'workflow', 'host', 'delivery', 'bookpage'},
    'novel': {'contracts', 'bootstrap'},
}

# These modules can evaluate values and invoke injected capabilities, but cannot
# discover files, databases, environment variables, processes or dynamic code.
CORE_EXTERNAL = {
    '__init__': set(),
    'contracts': {'__future__', 'copy', 'hashlib', 'json', 'dataclasses', 'typing'},
    'ports': {'__future__', 'typing'},
    'book_state': {'__future__', 'copy'},
    'craft': {'__future__', 'copy'},
    'creation': {'__future__', 'copy'},
    'design_queries': {'__future__'},
    'editorial': {'__future__', 'copy'},
    'entities': {'__future__', 'copy'},
    'evidence': {'__future__'},
    'facts': {'__future__', 'copy', 'decimal'},
    'narrative': {'__future__', 'copy'},
    'planning': {'__future__', 'copy', 'math'},
    'quality': {'__future__', 'copy'},
    'result_templates': {'__future__'},
    'revision_impact': {'__future__'},
    'scopes': {'__future__'},
    'spatial': {'__future__', 'copy'},
    'story_memory': {'__future__', 'copy'},
    'understanding': {'__future__', 'copy'},
    'world': {'__future__', 'copy'},
    'briefs': {'__future__'},
    'workflow': {'__future__', 'copy'},
    'application': {'__future__', 'copy'},
    'revision_service': {'__future__', 'copy'},
    'contract_activation': {'__future__', 'copy'},
    'context': {'__future__', 'copy', 'json'},
    'publication': {'__future__'},
}
FORBIDDEN_CORE_NAMES = {'open', '__import__', 'eval', 'exec', 'Path'}


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
    """Block builtin aliases too: loading `open` is already an I/O capability leak."""
    return {(node.lineno, node.id if isinstance(node, ast.Name) else node.attr)
            for node in ast.walk(tree)
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                and node.id in FORBIDDEN_CORE_NAMES)
            or (isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_CORE_NAMES)}


def diagram():
    source = (ROOT / 'references' / 'architecture.md').read_text(encoding='utf-8')
    return re.search(r'```mermaid\n(.*?)```', source, re.S).group(1).strip()


class ArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {path.stem: path for path in PACKAGE.glob('*.py')}
        cls.sources['novel'] = ROOT / 'scripts' / 'novel.py'
        cls.trees = {name: ast.parse(path.read_text(encoding='utf-8'), feature_version=(3, 9))
                     for name, path in cls.sources.items()}

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
        self.assertEqual({name for _, name in forbidden_core_accesses(tree)},
                         FORBIDDEN_CORE_NAMES)

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
