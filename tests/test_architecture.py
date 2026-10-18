"""Executable layer boundaries: allowed directions matter in addition to acyclicity."""
import ast
import re
import sys
import unittest
from pathlib import Path

from architecture_table import (ADAPTERS, ALLOWED, CORE_EXTERNAL, FORBIDDEN_CORE_NAMES,
                                allowed_edges)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'scripts' / 'novel_ledger'


def package_source():
    return '\n'.join(path.read_text(encoding='utf-8') for path in PACKAGE.glob('*.py'))


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


def resolve_label(label):
    """The module a diagram node names, or None for an aggregate group."""
    for name in sorted(ALLOWED, key=len, reverse=True):
        if re.search(r'(?<![\w])' + re.escape(name) + r'(?![\w])', label):
            return name
    return None


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

    def resolve(node):
        return resolve_label(labels.get(node, ''))

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

    def test_shared_numeric_defaults_are_declared_once(self):
        """A policy default belongs to `contracts.DEFAULTS` and to nothing else.

        Layer boundaries are one half of decoupling; the other half is that a *value* shared across
        layers has one source. Raising the volume outline's floor from 1000 to 2000 once meant editing
        five literals in four modules — a missed copy would have left two layers disagreeing about
        "the default". This guard reads the sources, so the next such change is one edit.
        """
        sys.path.insert(0, str(ROOT / 'scripts'))
        from novel_ledger import contracts, style
        self.assertEqual(style.DEFAULT_WINDOW, contracts.policy_default('style_window'))
        self.assertEqual(style.MIN_HAN, contracts.DEFAULTS['style_floor_han'])
        skeleton = contracts.contract_skeleton()
        for key in ('volume_outline', 'chapter_outline', 'style_window'):
            with self.subTest(policy=key):
                self.assertEqual(skeleton[key], contracts.policy_default(key))
        # opening/5's structural floors: per-tier minimums for the world's tier ladder and the scale
        # ladder, plus the theme-anchor deadline ceiling. The opening gates read that one declaration.
        ladder = contracts.DEFAULTS['world_ladder']
        self.assertEqual(set(ladder), {'tier_min', 'stage_min', 'anchor_max_chapter'})
        tiers = {row['id'] for row in contracts.SCALE_TIERS}
        self.assertEqual(set(ladder['tier_min']), tiers)
        self.assertEqual(set(ladder['stage_min']), tiers)
        for mapping in ('tier_min', 'stage_min'):
            for tier_id in tiers:
                with self.subTest(floor=mapping, tier=tier_id):
                    self.assertIs(type(ladder[mapping][tier_id]), int)
                    self.assertGreaterEqual(ladder[mapping][tier_id], 2)
        self.assertIs(type(ladder['anchor_max_chapter']), int)
        self.assertGreater(ladder['anchor_max_chapter'], 0)
        creation_source = (ROOT / 'scripts' / 'novel_ledger' / 'creation.py').read_text(encoding='utf-8')
        self.assertIn("DEFAULTS['world_ladder']", creation_source,
                      '开书门必须读共享声明，不得自己写死位阶/阶梯下限')
        # The same numbers must not reappear as literals outside the declaration. Only the shared
        # ones are listed: a module-local threshold (a lint window, a time marker set) is that
        # module's business and stays where it is.
        literals = ("'words': 2500", '"words": 2500', "'tolerance': 500", "'repetition': 0.12",
                    '{"scope": "all"', "'scope': 'all', 'words'",
                    "'anchor_max_chapter': 30", "'tier_min': {'t0'", "'stage_min': {'t0'")
        for name, path in self.sources.items():
            if name == 'contracts':
                continue
            text = path.read_text(encoding='utf-8')
            for needle in literals:
                with self.subTest(module=name, literal=needle):
                    self.assertNotIn(needle, text, '%s 重新硬编码了共享默认值：%s' % (name, needle))

    def test_every_stop_point_declares_where_the_author_decides(self):
        """A stop with no declared channel is how a converging project dead-ends.

        The table in `workflow` is the registry; this checks it still names the points that exist in
        the code, that every channel is explained, and that every stop the v2 pipeline can actually
        reach is in it. v2 removed every stop that existed only because a reviewer could refuse, so
        the surviving stops are the spent/stalled chapter budget and the author channel itself.
        """
        sys.path.insert(0, str(ROOT / 'scripts'))
        from novel_ledger import workflow
        source = package_source()
        for ident, channel in workflow.STOP_POINTS.items():
            with self.subTest(stop=ident):
                self.assertIn(channel, workflow.AUTHOR_CHANNELS,
                              'stop point must name a channel that is explained')
                self.assertIn(ident.split(':')[0], source, 'declared stop point no longer exists in the code')
        for ident in ('author_block', 'repair-exhausted:chapter_repair',
                      'repair-stalled:chapter_repair', 'revision-blocked', 'remedy-exhausted'):
            self.assertIn(ident, workflow.STOP_POINTS)
        # The review stops are gone with the stages that raised them.
        self.assertFalse({ident for ident in workflow.STOP_POINTS
                          if 'review' in ident or ident.startswith('scope-')})

    def test_kv_keys_are_built_only_in_the_declared_module(self):
        """A raw 'claim:' + id in an adapter would make the key space part of the adapter."""
        sys.path.insert(0, str(ROOT / 'scripts'))
        from novel_ledger import store_keys
        fixed = set(store_keys.KEYS) | {store_keys.BOOK_ROOT}
        for name, tree in self.trees.items():
            # The declaring module is where the keys are written down; the SQLite adapter builds its
            # own layout but names every key through that table, so it is not exempt either.
            if name == 'store_keys':
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                called = node.func.attr if isinstance(node.func, ast.Attribute) else None
                if called not in ('put', 'get'):
                    continue
                receiver = node.func.value
                receiver = receiver.attr if isinstance(receiver, ast.Attribute) else getattr(receiver, 'id', None)
                if receiver != 'repo':
                    continue
                first = node.args[0]
                literal = first.value if isinstance(first, ast.Constant) else None
                built = literal if isinstance(literal, str) else None
                if built is None and isinstance(first, ast.BinOp) and isinstance(first.left, ast.Constant):
                    built = first.left.value
                if not isinstance(built, str):
                    continue
                with self.subTest(module=name, line=node.lineno):
                    self.assertNotIn(built, fixed,
                                     f'{name}:{node.lineno} builds the kv key {built!r} directly.')
                    self.assertFalse(built.startswith(store_keys.PREFIXES),
                                     f'{name}:{node.lineno} builds a prefixed kv key {built!r} directly.')

    def test_dispatched_stages_are_registered(self):
        """A dispatched stage missing from the registry would degrade silently."""
        sys.path.insert(0, str(ROOT / 'scripts'))
        from novel_ledger import stages

        def literals(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                yield node.value
            elif isinstance(node, ast.IfExp):
                yield from literals(node.body)
                yield from literals(node.orelse)

        for name, tree in self.trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or getattr(node.func, 'id', None) != 'Job' or not node.args:
                    continue
                for value in literals(node.args[0]):
                    with self.subTest(module=name, line=node.lineno):
                        self.assertIn(value, stages.STAGES,
                                      f'{name}:{node.lineno} dispatches unregistered stage {value!r}')
                        self.assertEqual(stages.require_stage(value), value)

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

    def test_diagram_nodes_are_concrete_modules_or_declared_aggregates(self):
        """A misspelled module is skipped by the edge check, so it has to be caught here.

        The diagram is a summary: it draws the main edges and one aggregate group, and does not
        draw every allowed edge. What it may not do is invent a node — an unresolved label is
        either the declared aggregate or a typo that would silently escape the check above.
        """
        _, labels = diagram_edges()
        aggregates = {'纯领域规则'}
        unresolved = sorted({node for node, label in labels.items()
                             if resolve_label(label) is None and label.strip() not in aggregates})
        self.assertEqual(unresolved, [], 'every diagram node must name a module or a declared aggregate')
        for node, label in labels.items():
            if label.strip() in aggregates:
                continue
            with self.subTest(node=node):
                self.assertIn(resolve_label(label), ALLOWED)

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

    def test_the_diagram_is_a_mermaid_source_with_no_derived_copy(self):
        """The diagram's source of truth is Mermaid, and no rendered copy is kept in the repo.

        A committed SVG used to live beside it and fell out of date the moment `drift` and `style`
        were added — a derived artifact that nothing regenerates is a file that lies. The source is
        compared against `references/architecture.md` (so a hand-edited snapshot fails), and the
        absence of a rendered copy is part of the contract: regenerate one on demand with any Mermaid
        renderer instead of committing it.
        """
        source = diagram()
        mmd = (ROOT / 'docs' / 'architecture.mmd').read_text(encoding='utf-8')
        documented = re.search(r'```mermaid\n(.*?)```',
                               (ROOT / 'references' / 'architecture.md').read_text(encoding='utf-8'),
                               re.S).group(1).strip()
        self.assertEqual(source, documented)
        self.assertIn('drift', mmd)
        self.assertFalse(any('待重新生成' in line for line in mmd.splitlines()[:8]),
                         'the snapshot is the source now: a staleness marker has nothing to point at')
        self.assertEqual(sorted(path.name for path in (ROOT / 'docs').glob('*.svg')), [],
                         '渲染件不入库：需要图片时从 docs/architecture.mmd 现场导出')


if __name__ == '__main__':
    unittest.main()
