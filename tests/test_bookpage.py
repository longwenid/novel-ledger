"""Single-file HTML book view: derived, self-contained, and safe on an empty book."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import bookpage, planning
from novel_ledger.application import Application
from novel_ledger.sqlite_store import SQLiteRepository
from novel_ledger.workflow import new_book
from support import contract, drive


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
                       '设计与因果节点', '章计划', '人物档案', '事实账本', '章审记录', '账本核验',
                       'novel.sqlite3', 'ch-index', 'view-read', 'view-settings'):
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

    def test_empty_project_renders_without_crashing(self):
        self.repo.save(new_book(contract(2, 1)))
        page = bookpage.render(self.repo)
        self.assertIn('创作约定', page)
        self.assertIn('尚无已提交章节', page)
        self.assertIn('尚无设计', page)
        self.assertIn('尚无章计划', page)

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

    def test_escaping_neutralises_markup_in_prose_and_names(self):
        book = self.repo.load()
        book['contract']['title'] = '标题 <b>粗体</b> & "引号"'
        self.repo.save(book)
        page = bookpage.render(self.repo)
        self.assertIn('标题 &lt;b&gt;粗体&lt;/b&gt; &amp; &quot;引号&quot;', page)
        self.assertNotIn('<b>粗体</b>', page)

    def test_view_containers_nest_correctly(self):
        """#view-settings must close before #view-read opens, or the reader swallows the settings."""
        page = self.written()
        settings = page.index('<div id="view-settings">')
        reader = page.index('<div id="view-read"')
        self.assertLess(settings, reader)
        # every div opened in the body is closed: count balance over the rendered document
        body = page[page.index('<body>'):]
        self.assertEqual(body.count('<div'), body.count('</div>'))
        self.assertEqual(body.count('<section class="chapter"'), page.count('</section>'))
        self.assertLess(reader, page.index('id="ch-index"'))

    def test_html_command_writes_a_file_and_is_repeatable(self):
        self.written()
        first = self.app  # keep the app alive; the command path is exercised below
        result = bookpage.write(self.repo)
        target = Path(result['path'])
        self.assertEqual(target.name, 'book.html')
        self.assertTrue(target.is_file())
        self.assertTrue(result['inside_project'])
        self.assertEqual(result['chapters'], 1)
        body = target.read_text(encoding='utf-8')
        self.assertEqual(len(body), result['chars'])
        again = bookpage.write(self.repo)
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
