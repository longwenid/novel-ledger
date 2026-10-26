"""Lightweight preview entry and explicit offline book views."""
import json
import re
import sys
import subprocess
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import bookpage, world
from novel_ledger.bootstrap import local_application as Application, local_workspace
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.workflow import new_book
from support import contract, drive
from test_opening import rows_for


class BookPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, new_book(contract(2, 1)))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def written(self):
        drive(self.app, until='write')
        from support import response

        self.app.submit(response(self.app))
        from support import drive as continue_drive

        continue_drive(self.app)
        book = self.repo.load()
        self.assertGreaterEqual(len(self.repo.headers(book['branch'])), 1)
        return bookpage.render(self.repo)

    def test_render_covers_every_surface_and_is_self_contained(self):
        page = self.written()
        for marker in ('<!DOCTYPE html>', '看设定', '读正文', '概览', '创作约定', '夜班退件', '世界与选择',
                       '卷纲与章纲', '章纲结算行', '事实账本', '漂移挂账', '账本核验',
                       '作品账本', 'ch-index', 'view-read', 'view-settings',
                       # The volume card's own rows: the ladder rung and the two optional terminals
                       # render even when a volume declares none of them.
                       '格局层级', '关系终值', '读者认知终值'):
            self.assertIn(marker, page, marker)
        # the committed prose must be readable, and single quotes in JS must not escape the script
        book = self.repo.load()
        row = self.repo.headers(book['branch'])[0]
        self.assertIn(self.repo.read_document(row['prose']).split('\n')[0][:12], page)
        self.assertEqual(page.count('<script>'), 1)
        self.assertEqual(page.count('</script>'), 1)
        # self-contained: no external requests of any kind
        self.assertNotIn('http://', page)
        self.assertNotIn('https://', page)
        self.assertNotIn('<link', page)
        self.assertNotIn(' src=', page)
        # the reader controls and reader body are present
        for control in ('readerSize', 'readerWide', 'readerTheme', 'readerFamily', 'filterIndex', 'openChapter'):
            self.assertIn(control, page)
        self.assertIn('class="chapter" id="read-' + str(row['n']) + '"', page)
        self.assertIn('第' + str(row['n']) + ' 章 ' + row['title'], page)
        # #view-settings must close before #view-read opens, or the reader swallows the settings;
        # every div opened in the body is closed.
        settings = page.index('<div id="view-settings">')
        reader = page.index('<div id="view-read"')
        self.assertLess(settings, reader)
        body = page[page.index('<body>'):]
        self.assertEqual(body.count('<div'), body.count('</div>'))
        self.assertEqual(body.count('<section class="chapter"'), page.count('</section>'))
        self.assertLess(reader, page.index('id="ch-index"'))

    def test_empty_project_renders_without_crashing(self):
        self.repo.save(new_book(contract(2, 1)))
        page = bookpage.render(self.repo)
        self.assertIn('创作约定', page)
        self.assertIn('尚无已提交章节', page)
        self.assertIn('尚无卷纲与章纲', page)
        self.assertIn('尚无章纲结算行', page)

    def test_contract_fields_render_with_their_own_labels(self):
        """A contract written before a field existed must not render as a decision left blank, and
        the six opening/5 fields are decisions, so the page names them, not raw keys."""
        book = self.repo.load()
        self.assertNotIn('叙述视角', bookpage.render(self.repo))
        book['contract'].update(tone='冷硬的夜班底色。', theme='责任怎样在人之间传递。',
                                pov='第三人称限知，只跟沈桐的所见与所知。')
        self.repo.save(book)
        page = bookpage.render(self.repo)
        for label in ('基调', '母题', '叙述视角'):
            self.assertIn(label, page)
        self.assertIn('第三人称限知，只跟沈桐的所见与所知。', page)

        book = self.repo.load()
        book['contract'].update(
            core_premise={'novelty': '登记制度本身会记住每一个签字的人。',
                          'first_cause': '旧登记制度在一次退件事故后自我封闭。',
                          'stance': '利用', 'dark_side': '上层剥削'},
            world_scale={'opening': '第一章只见一座仓库与一条夜班线。', 'terminal': '势力',
                         'unchanged': '跨卷不变的是登记制度本身。'},
            world_tiers=[{'name': '一阶登记员', 'condition': '完成一次退件核对。',
                          'gain': '可调阅一层凭据。', 'cost': '承担一层登记责任。',
                          'limit': '不得超过一层权限。'}],
            world_ladder=[{'stage': '青云城', 'scope': '一城', 'growth': '地盘',
                           'new_rule': '城内登记由城主分配。', 'cost': '失去旧身份。'}],
            world_resource={'name': '登记凭证', 'source': '夜班结余里扣下的一份。',
                            'allocator': '夜班主管'},
            promise_anchor={'deliverable': '第 12 章前必须当众兑现一次责任落位。',
                            'deadline_chapter': '12'})
        self.repo.save(book)
        page = bookpage.render(self.repo)
        for label in ('核心设想', '格局尺度', '升格阶梯', '位阶阶梯', '硬通货', '主题锚点'):
            self.assertIn(label, page, label)
        for value in ('登记制度本身会记住每一个签字的人。', '第一章只见一座仓库与一条夜班线。',
                      '一阶登记员', '青云城', '登记凭证',
                      '第 12 章前必须当众兑现一次责任落位。'):
            self.assertIn(value, page, value)
        # The nested keys are labelled too: raw JSON keys would read as a field that was skipped.
        for label in ('核心设想', '第一推动力', '世界暗面来源', '必须兑现的东西', '最迟兑现章'):
            self.assertIn(label, page, label)

    def test_powers_and_cosmology_render_as_their_own_world_sections(self):
        """The two new domains get their frozen section titles and their record content."""
        book = self.repo.load()
        model = dict(premise='仓库', story_capacity='退件与责任', selection_hash='fixture')
        for section, fields in world.SECTIONS.items():
            model[section] = [{**{field: section + ' ' + field for field in fields},
                               'id': section + '1', 'links': []}]
        model['powers'] = [{'id': 'rank1', 'name': '一阶登记员', 'condition': '完成一次退件核对。',
                            'gain': '可调阅一层凭据。', 'cost': '承担一层登记责任。',
                            'limit': '不得超过一层权限。', 'links': []}]
        model['cosmology'] = [{'id': 'layer1', 'name': '青云界', 'inhabitant': '界内势力与居民。',
                               'law': '跨界需要通行凭证。', 'entry': '沿旧凭据的入口进入。',
                               'links': []}]
        book['world'] = model
        self.repo.save(book)
        page = bookpage.render(self.repo)
        self.assertIn(world.LABELS['powers'], page)
        self.assertIn(world.LABELS['cosmology'], page)
        for value in ('一阶登记员', '完成一次退件核对。', '青云界', '跨界需要通行凭证。'):
            self.assertIn(value, page, value)
        self.assertIn('12 条', page)          # every declared domain renders its own record count

    def test_structural_choice_renders_as_a_size_not_as_a_scene_pitch(self):
        from novel_ledger import creation, workflow

        def offered(gate, value, field):
            rows = []
            for ident in ('A', 'B', 'C'):
                entry = dict(value)
                if ident != 'A':
                    entry = {**value, field: value[field] + '侧重' + ident + '。'}
                rows.append({'id': ident, 'title': '方案' + ident, 'premise': '具体方案' + ident + '。',
                             'pitch': '看一眼就想翻开的一句话' + ident + '。',
                             'scene': ['夜班仓库里，他把退件箱推到灯下核对封条。', '凌晨的登记台前，他逐页翻经手的那栏。'],
                             'driver': '方案' + ident + '以不同的核对顺序推进。',
                             'tradeoff': '相比另两案，选它要放弃' + ident + '那条更快的路。',
                             'fit_reason': '承接夜班题材，把推进压在一件具体物件上。', 'value': entry})
            return {'gate': gate, 'options': rows}

        state = creation.begin('工程夹具。')
        state = creation.offer(state, offered('genre', {'genre': '都市生活', 'reader_promise': '在夜班退件里查清责任。',
                                                       'tone': '冷硬的夜班底色。'}, 'reader_promise'))
        state = creation.pick(state, 'A', state['board']['hash'], 'A')
        premise = {'novelty': '登记制度本身会记住每一个签字的人。', 'first_cause': '旧登记制度在一次退件事故后自我封闭。',
                   'stance': '利用', 'dark_side': '制度'}
        state = creation.offer(state, offered('premise', premise, 'novelty'))
        state = creation.pick(state, 'A', state['board']['hash'], 'A')
        board = state['board']                                     # the structural gate answered itself
        state = creation.pick(state, board['options'][0]['id'], board['hash'], '选它。')
        # opening/7: voice sits behind world and ladder, so both are answered before the pov.
        for gate in ('world', 'ladder'):
            state = creation.offer(state, {'gate': gate, 'options': rows_for(gate)})
            state = creation.pick(state, state['board']['options'][0]['id'], state['board']['hash'], '选它。')
        voice = {'pov': '第三人称限知，只跟沈桐的所见与所知。', 'voice': '具体动作与有立场的对白。',
                 'style_traits': ['少重复解释。']}
        state = creation.offer(state, offered('voice', voice, 'voice'))
        state = creation.pick(state, 'A', state['board']['hash'], 'A')
        book = workflow.preparing_book(guided=True)
        book['creation'] = state
        self.repo.save(book)
        page = bookpage.render(self.repo)
        self.assertIn(board['options'][0]['title'], page)
        self.assertIn('总字数区间', page)
        self.assertIn('卷数', page)
        self.assertNotIn('可写完章数区间', page)      # engine bookkeeping, not an author-facing field

    def test_init_creates_unified_page_for_guided_and_imported_books(self):
        for name, imported in (('guided', False), ('imported', True)):
            project = Path(self.temp.name) / name
            args = [sys.executable, str(ROOT / 'scripts' / 'novel.py'), '--project', str(project), 'init']
            if imported:
                source = Path(self.temp.name) / 'contract.json'
                source.write_text(json.dumps(contract(), ensure_ascii=False), encoding='utf-8')
                args.extend(['--contract', str(source)])
            result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            info = json.loads(result.stdout)
            self.assertEqual(Path(info['book_view']['path']), (project / 'book.html').resolve())
            page = (project / 'book.html').read_text(encoding='utf-8')
            self.assertIn('世界与选择', page)
            self.assertIn('打开作品预览', page)
            self.assertIn('preview', info['book_view']['preview_command'])
            self.assertEqual((project / 'world.html').exists(), False)

    def test_graphs_preserve_explicit_links_and_escape_all_labels(self):
        book = self.repo.load()
        model = dict(premise='仓库', story_capacity='退件与责任', selection_hash='fixture')
        for section, fields in world.SECTIONS.items():
            model[section] = [{**{field: section + ' ' + field for field in fields}, 'id': section + '1', 'links': []}]
        model['characters'][0]['name'] = '人物 <script>alert(1)</script> & "引号"'
        model['characters'][0]['links'] = ['geography:geography1']
        # Reciprocal references represent one undirected association.
        model['geography'][0]['links'] = ['characters:characters1']
        book['world'] = model
        book['state']['entities']['boss'] = {'id': 'boss', 'name': '主管', 'kind': 'person'}
        book['state']['relations'] = {'shen>boss:信任': '下降'}
        book['state']['places'] = {'door': {'id': 'door', 'name': '门口'}, 'room': {'id': 'room', 'name': '仓库', 'parent': 'door'}}
        book['state']['placements'] = {'shen': 'room'}
        self.repo.save(book)
        page = bookpage.render(self.repo)
        svgs = [ET.fromstring(svg) for svg in re.findall(r'<svg\b.*?</svg>', page, re.S)]
        self.assertEqual(len(svgs), 3)
        self.assertEqual([len(svg.findall("path[@class='graph-edge']")) for svg in svgs], [1, 1, 2])
        targets = set(re.findall(r'\bid="([^"]+)"', page))
        for svg in svgs:
            for node in svg.findall("a[@class='graph-node']"):
                self.assertIn(node.attrib['href'][1:], targets)
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertIn('信任：下降', page)
        self.assertIn('历史时间线', page)
        self.assertNotIn('https://', page)

    def test_progress_and_resource_charts_keep_exact_values_and_units(self):
        self.written()
        book = self.repo.load()
        book['state']['resources'] = {
            json.dumps(['shen', '车费', '元'], ensure_ascii=False): '0',
            json.dumps(['shen', '库存', '件'], ensure_ascii=False): '123.4500',
        }
        self.repo.save(book)
        page = bookpage.render(self.repo)
        for title in ('写作进度', '分卷进度', '章节篇幅', '资源分布 · 车费'):
            self.assertIn(title, page)
        self.assertIn('0 元', page)
        self.assertIn('123.4500 件', page)
        self.assertNotIn('nan%', page)
        self.assertNotIn('inf%', page)

    def test_written_page_matches_database_and_stays_derived(self):
        page = self.written()
        book = self.repo.load()
        rows = self.repo.headers(book['branch'])
        total = sum(row['han'] for row in rows)
        self.assertIn('%d 章 · ' % len(rows), page)
        self.assertIn('%s 汉字' % format(book['written_han'], ','), page)
        self.assertEqual(book['written_han'], total)
        # regenerating must not touch the database
        before = (self.project / 'novel.sqlite3').read_bytes()
        bookpage.render(self.repo)
        self.assertEqual(before, (self.project / 'novel.sqlite3').read_bytes())

    def test_escaping_neutralises_markup_and_template_values_once(self):
        """Markup in prose and names is escaped, template placeholders pass through inertly, and no
        reinterpreted value ever re-enters the page as live markup."""
        book = self.repo.load()
        book['contract']['title'] = '标题 <b>粗体</b> & "引号"'
        self.repo.save(book)
        page = bookpage.render(self.repo)
        self.assertIn('标题 &lt;b&gt;粗体&lt;/b&gt; &amp; &quot;引号&quot;', page)
        self.assertNotIn('<b>粗体</b>', page)
        book = self.repo.load()
        book['contract']['title'] = '$script ${reader} <b>书名</b> & "引号"'
        self.repo.save(book)
        page = bookpage.render(self.repo)
        self.assertIn('$script ${reader} &lt;b&gt;书名&lt;/b&gt; &amp; &quot;引号&quot;', page)
        self.assertEqual(page.count('<script>'), 1)

    def test_copied_installation_renders_preview_from_an_unrelated_directory(self):
        install = Path(self.temp.name) / 'installed'
        shutil.copytree(ROOT / 'scripts', install / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        project = Path(self.temp.name) / 'copied-book'
        result = subprocess.run(
            [sys.executable, str(install / 'scripts' / 'novel.py'), '--project', str(project), 'init'],
            cwd=self.temp.name, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        page = (project / 'book.html').read_text(encoding='utf-8')
        self.assertIn('toggleSide()', page)
        self.assertIn('--reader-size:19px', page)
        self.assertNotIn('<link', page)
        self.assertNotIn(' src=', page)
        self.assertNotIn('$settings', page)

    def test_html_command_writes_a_file_and_is_repeatable(self):
        self.written()
        first = self.app  # keep the app alive; the command path is exercised below
        result = bookpage.write(self.repo, workspace=local_workspace(self.repo))
        target = Path(result['path'])
        self.assertEqual(target.name, 'book.html')
        self.assertTrue(target.is_file())
        self.assertTrue(result['inside_project'])
        self.assertEqual(result['chapters'], 1)
        body = target.read_text(encoding='utf-8')
        self.assertEqual(len(body), result['chars'])
        again = bookpage.write(self.repo, workspace=local_workspace(self.repo))
        self.assertEqual(again['chars'], result['chars'])
        self.assertTrue(first is not None)

    def test_audit_report_flags_overdue_hooks_and_length_drift(self):
        self.written()
        book = self.repo.load()
        book['state']['hooks']['probe'] = {'text': '测试承诺', 'status': 'open', 'due': 1, 'seed_chapter': 1,
                                           'extensions': 0}
        book['written_han'] = 999999
        self.repo.save(book)
        page = bookpage.render(self.repo)
        self.assertIn('已过期未兑现', page)
        self.assertIn('汉字计数投影与各章之和不一致', page)
        self.assertIn('否', page)


if __name__ == '__main__':
    unittest.main()
