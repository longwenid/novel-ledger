"""Synthetic behavior tests for tracked stories; never claims of literary quality."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from support import contract, node, response
from novel_ledger import context, facts, narrative, planning, scopes, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import CHECKS_VERSION, RESULT, Error, Job, digest, dump
from novel_ledger.sqlite_store import SQLiteRepository


def tracked_contract(chapters=6):
    raw = contract(chapters)
    raw.update(narrative_tracking=True, review_chunk=2, review_interval=3, planning_window=3)
    return raw


def story_node(ident, chapter, line='main', dependencies=(), required=True):
    return {**node(ident, dependencies), 'line': line, 'required': required, 'window': [chapter, chapter]}


def pace(role='pressure'):
    return {'role': role, 'pressure_in': '来源不明，工人担心承担责任。', 'pressure_out': '有了核对方向但关系更紧张。',
            'emotional_aftereffect': '先处理被怀疑后的犹豫，再决定下一步。', 'recovery_purpose': '缓和争执，确认谁愿意合作。'}


def tracked_response(app):
    result = response(app)
    work = app.repo.pending()['input']
    stage, n = work['stage'], work['chapter']
    book = app.repo.load()
    total = book['contract']['volumes'][-1]['end']
    if stage == 'book_plan':
        kinds = ('main', 'side', 'hidden') if total >= 3 else ('main',)
        result['data'] = {'intent': '核查退件并面对人情代价。', 'ending_conditions': '各线证据和后果交代完整。',
            'threads': [{'id': k, 'kind': k, 'purpose': '核对证据与利益。', 'ending_condition': '处理该线造成的后果。', 'required': True} for k in kinds],
            'nodes': [story_node('n'+str(k), k, kinds[(k-1) % len(kinds)], () if k==1 else ('n'+str(k-1),)) for k in range(1, total+1)]}
    elif stage == 'volume_plan':
        result['data'].update(intent='展开本卷行动与余波。', ending_conditions='证据成立且关系变化。', threads=[],
                              nodes=[{**story_node(work['scope'], n, required=False), 'window': [n, total]}])
    elif stage == 'plan':
        for plan in result['data']['plans']:
            k = plan['chapter']
            plan.update(node_ids=['n'+str(k)], node_actions=[{'node': 'n'+str(k), 'after': 'resolved'}],
                        preconditions=[], pacing=pace(('pressure', 'aftermath', 'recovery')[(k-1)%3]),
                        disclosures=[{'topic': 'source', 'after': 'hinted' if k < total else 'confirmed'}] if k in (3,total) else [])
    elif stage == 'chapter_review':
        plan = book['plans'][str(n)]
        ref = {'chapter': n, 'quote': '要求先核对退件人的名字再开箱'}
        events = result['data']['facts']['events']
        events += [{'op': 'story_node', 'node': a['node'], 'before': narrative.progress(book['state'], a['node']),
                    'after': a['after'], 'outcome': '核对来源并作出行动选择。', 'evidence': ref} for a in plan['node_actions']]
        for d in plan['disclosures']:
            events.append({'op': 'reader_knowledge', 'topic': d['topic'], 'before': book['state']['reader_knowledge'].get(d['topic'], {}).get('status'),
                           'after': d['after'], 'claim': '读者看到了来源核对的证据。', 'evidence': ref})
        nodes, threads = narrative.registry(book)
        for ident in threads:
            last = max(v['window'][1] for v in nodes.values() if v['line']==ident and v['required'])
            if n == last:
                events.append({'op': 'story_thread', 'thread': ident, 'before': 'active', 'after': 'resolved', 'reason': '该线的必要证据和后果已完成。', 'evidence': ref})
        result['data']['reader']['pacing'] = {**pace(plan['pacing']['role']), 'evidence': ref}
    elif stage in ('scope_review', 'scope_synthesis') and work['payload'].get('review_tree'):
        sources = app._sources(work)
        result['data']['handoff'] = {**{k: '工程夹具：本范围核对证据、后果和衔接，未发现需要后续处理的问题。' for k in scopes.HANDOFF_FIELDS},
                                   'evidence': [{'chapter': work['first'], 'quote': '次日'}]}
        if work['payload']['children']:
            reports = scopes.reports(book)
            result['data']['coverage'] = [{'part_id': ident, 'reason': '工程夹具：检查子范围与下一范围的因果承接。',
                'evidence': {'chapter': reports[ident]['first'], 'quote': '次日'}} for ident in work['payload']['children']]
    return result


def drive_tracked(app, owner=None, until=None):
    for _ in range(300):
        handoff = app.advance(owner=owner)
        if handoff['action']=='await_author':
            app.approve(handoff['prose_hash'], '工程夹具认可当前首章。', owner)
        elif handoff['action']!='task_ready':
            return handoff
        elif until and handoff['task']['stage']==until:
            return handoff
        else:
            app.submit(tracked_response(app))
    raise AssertionError('跟踪工程流未停止')


class NarrativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository.initialize(Path(self.temp.name)/'book', workflow.new_book(tracked_contract()))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def assertCode(self, code, fn, *args):
        with self.assertRaises(Error) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)

    def test_new_projects_default_to_tracking_but_legacy_seed_is_unchanged(self):
        raw = contract()
        del raw['narrative_tracking']
        self.assertIn('story_nodes', workflow.new_book(raw)['state'])
        self.assertNotIn('story_nodes', facts.seed(contract()))

    def test_three_lines_complete_and_replay_with_evidence(self):
        owner = self.app.run(finish=True)['owner']
        self.assertEqual(drive_tracked(self.app, owner)['action'], 'ready_to_complete')
        self.assertTrue(self.app.complete(owner)['completed'])
        state = self.repo.load()['state']
        self.assertEqual({t['status'] for t in state['thread_progress'].values()}, {'resolved'})
        self.assertEqual(state['reader_knowledge']['source']['status'], 'confirmed')
        self.assertEqual([p['role'] for p in state['pace_history']], ['pressure','aftermath','recovery']*2)
        self.assertTrue(self.app.audit()['ok'])

    def test_payoff_plan_cannot_skip_unrealized_dependency(self):
        drive_tracked(self.app, until='plan')
        result = tracked_response(self.app)
        first = result['data']['plans'][0]
        first.update(node_ids=['n2'], node_actions=[{'node':'n2','after':'resolved'}])
        self.repo.load()
        # Put the payoff inside the same window to isolate the missing causal prerequisite.
        b = self.repo.load(); b['designs']['book']['nodes'][1]['window']=[1,2]; self.repo.save(b)
        self.assertCode('story_dependency', self.app.submit, result)
        self.assertEqual(self.repo.load()['state']['story_nodes'], {})

    def test_missing_node_event_rolls_back_entire_chapter(self):
        drive_tracked(self.app, until='chapter_review')
        result = tracked_response(self.app)
        result['data']['facts']['events'] = [e for e in result['data']['facts']['events'] if e['op']!='story_node']
        self.assertCode('story_coverage', self.app.submit, result)
        self.assertEqual(self.repo.headers('main'), [])

    def test_bad_event_coordinate_returns_domain_error_not_traceback(self):
        drive_tracked(self.app,until='chapter_review')
        result=tracked_response(self.app)
        result['data']['facts']['events'][1]['node']={'invalid':'shape'}
        self.assertCode('story_coverage',self.app.submit,result)

    def test_unplanned_reveal_is_rejected(self):
        drive_tracked(self.app, until='chapter_review')
        result = tracked_response(self.app)
        result['data']['facts']['events'].append({'op':'reader_knowledge','topic':'source','before':None,'after':'confirmed','claim':'提前揭晓。','evidence':{'chapter':1,'quote':'次日'}})
        self.assertCode('disclosure', self.app.submit, result)

    def test_required_line_cannot_close_early(self):
        drive_tracked(self.app, until='chapter_review')
        result = tracked_response(self.app)
        result['data']['facts']['events'].append({'op':'story_thread','thread':'main','before':'active','after':'resolved','reason':'提前结束。','evidence':{'chapter':1,'quote':'次日'}})
        self.assertCode('story_closure', self.app.submit, result)

    def test_current_character_state_is_evidenced_and_replans_changed_assumption(self):
        b=self.repo.load(); b['target']=6; self.repo.save(b)
        drive_tracked(self.app, until='chapter_review')
        result = tracked_response(self.app)
        change = {'desire':'保护同事。','stance':'愿意承担责任。','relationship_focus':'信任被怀疑的同事。'}
        result['data']['facts']['events'].append({'op':'character_current','entity':'shen','before':None,'after':change,'choice':'站出来担责。','cost':'可能丢掉工作。','change':'先保住同事。','evidence':{'chapter':1,'quote':'次日'}})
        self.app.submit(result)
        self.app.approve(self.repo.chapter('main',1)['prose'], '工程认可。')
        b=self.repo.load(); b['target']=6; b['plans']['2']['preconditions']=[{'kind':'character_current','key':'shen','expected':None}]; self.repo.save(b)
        handle=self.app.advance()
        self.assertEqual(handle['task']['stage'],'plan')
        self.assertEqual(self.repo.load()['state']['character_current']['shen']['value'],change)

    def test_dormant_line_requires_a_return_condition(self):
        event={'op':'story_thread','thread':'side','before':None,'after':'dormant','reason':'等主角回来。','evidence':{'chapter':1,'quote':'次日'}}
        self.assertCode('story_thread',facts.settle,self.repo.load()['state'],[event],'次日',1)
        event['return_by']=3
        state,_=facts.settle(self.repo.load()['state'],[event],'次日',1)
        self.assertCode('thread_due',facts.settle,state,[],'第三日',3)

    def test_completion_requires_all_required_nodes_and_lines(self):
        b=self.repo.load(); b['designs']['book']={'nodes':[story_node('end',6)],'threads':[{'id':'main','kind':'main','required':True}]}
        self.assertCode('story_closure',narrative.closure,b)

    def test_dynamic_budget_detects_unreachable_total_before_dispatch(self):
        raw=json.loads((Path(__file__).resolve().parents[1]/'assets/contract.example.json').read_text())
        c=planning.validate_contract(raw)
        self.assertCode('word_budget',narrative.word_budget,c,1200000,451)
        budget=narrative.word_budget(c,1497000,500)
        self.assertEqual(budget['minimum'],3000)

    def test_variable_chapter_cap_can_exceed_average_budget(self):
        raw=tracked_contract(2); raw.update(chapter_min=20,chapter_aim=70,chapter_max=150,word_range=[100,200])
        c=planning.validate_contract(raw)
        self.assertEqual(narrative.word_budget(c,140,2)['maximum'],60)

    def test_narrow_revision_budget_reserves_unchanged_suffix(self):
        raw=tracked_contract(3); raw.update(chapter_min=20,chapter_aim=50,chapter_max=100,word_range=[120,180])
        c=planning.validate_contract(raw)
        budget=narrative.word_budget(c,50,2,60,1)
        self.assertEqual((budget['minimum'],budget['maximum']),(20,70))

    def test_normalized_plan_does_not_mutate_receipt_or_break_idempotence(self):
        drive_tracked(self.app,until='plan')
        result=tracked_response(self.app)
        original=copy.deepcopy(result)
        self.app.submit(result)
        self.assertEqual(result,original)
        self.assertTrue(self.app.submit(original)['idempotent'])

    def test_every_cold_stage_has_brief_and_blind_stage_hides_formal_brief(self):
        handle=drive_tracked(self.app,until='write')['task']
        work=self.repo.pending()['input']
        self.assertTrue(work['brief']); self.assertIn('craft.md',str(handle['guides']))
        self.app.submit(tracked_response(self.app))
        blind=self.app.advance()['task']
        self.assertEqual(blind['delivery_phase'],'first_read')
        self.assertNotIn('node_actions',blind['brief'])
        self.assertNotIn('input_path',blind)

    def test_story_context_uses_direct_dependencies_not_500_ancestors(self):
        drive_tracked(self.app,until='write')
        self.repo.cancel_pending('工程上下文测量')
        b=self.repo.load()
        b['designs']['book']['nodes']=[{**story_node('a'+str(i),1,dependencies=() if i==0 else ['a'+str(i-1)]),'required':False} for i in range(500)]
        b['plans']['1'].update(node_ids=['a499'],node_actions=[{'node':'a499','after':'seeded'}],node_contracts={'a499':b['designs']['book']['nodes'][-1]})
        self.repo.save(b)
        self.app.advance()
        w=self.repo.pending()['input']
        self.assertEqual(len(self.repo.read_document(w['records']['story'])),2)
        self.assertEqual(len(self.repo.read_document(w['records']['design:book'])['nodes']),500)

    def test_later_planner_receives_completed_direct_prerequisites(self):
        owner=self.app.run(finish=True)['owner']
        for _ in range(80):
            h=self.app.advance(owner=owner)
            if h['action']=='await_author':
                self.app.approve(h['prose_hash'],'工程认可。',owner); continue
            w=self.repo.pending()['input']
            if w['stage']=='plan' and w['chapter']==4:
                frontier=self.repo.read_document(w['records']['progress_frontier'])
                self.assertEqual(frontier['nodes']['n3']['status'],'resolved')
                return
            self.app.submit(tracked_response(self.app))
        self.fail('没有出现下一窗口')

    def test_memory_lookup_is_frozen_and_blind_lookup_is_sealed(self):
        owner=self.app.run(finish=True)['owner']
        drive_tracked(self.app,owner,until='chapter_review')
        task=self.repo.pending()
        self.assertCode('first_read_sealed',self.app.recall,task['id'],None,False,'entity','shen')
        self.app.submit(tracked_response(self.app))
        self.app.approve(self.repo.chapter('main',1)['prose'],'工程认可。',owner)
        self.app.advance(owner=owner)
        task=self.repo.pending()
        found=self.app.recall(task['id'],None,False,'node','n1')
        self.assertEqual(found['matches'][0]['chapter'],1)
        self.assertEqual(found['matches'][0]['evidence']['quote'],'要求先核对退件人的名字再开箱')

    def test_receipt_cannot_downgrade_frozen_check_version(self):
        drive_tracked(self.app,until='chapter_review')
        result=tracked_response(self.app)
        result['data']['facts']['checks_version']=1
        self.assertCode('checks_version',self.app.submit,result)

    def test_original_inflight_review_keeps_original_check_set(self):
        self.repo.save(workflow.new_book(contract()))
        from support import drive
        drive(self.app,until='chapter_review')
        original=copy.deepcopy(self.repo.pending()['input'])
        original.pop('checks_version')
        self.repo.cancel_pending('工程模拟更新前的冻结任务')
        self.repo.add_task(original)
        result=response(self.app)
        self.assertEqual(result['data']['facts']['checks_version'],1)
        self.app.submit(result)
        self.assertTrue(self.app.audit()['ok'])

    def test_book_view_contains_narrative_progress_and_reader_state(self):
        from novel_ledger import bookpage
        owner=self.app.run(finish=True)['owner']
        drive_tracked(self.app,owner)
        html=bookpage.render(self.repo)
        self.assertIn('节点实际推进',html)
        self.assertIn('读者已见信息',html)
        self.assertIn('近期节奏与情绪承接',html)

    def test_world_secret_stays_optional_and_disclosure_boundary_is_explicit(self):
        drive_tracked(self.app,until='write')
        self.repo.cancel_pending('工程隐秘材料')
        b=self.repo.load(); b['plans']['1']['world_refs']=['characters:shen']
        b['world']={'premise':'仓库','rules':[],'story_capacity':'工程模型','characters':[{'id':'shen','links':['mysteries:source']}],
                    'mysteries':[{'id':'source','truth':'真正退件人是主管','disclosure':'卷末','causal_role':'追查责任','links':[]}]}
        self.repo.save(b); self.app.advance(); w=self.repo.pending()['input']
        self.assertNotIn('真正退件人是主管',dump({k:self.repo.read_document(w['records'][k]) for k in w['required']}))
        self.assertIn('真正退件人是主管',dump(self.repo.read_document(w['records']['world_author_records'])))
        self.assertEqual(self.repo.read_document(w['records']['disclosure_boundary'])['allowed_changes'],[])

    def test_review_tree_bounds_parent_fanout_and_invalidates_changed_chain(self):
        headers=[{'n':i,'chain':str(i)} for i in range(1,501)]
        parts=scopes.tree(headers,1,500,3,3)
        self.assertEqual((parts[-1]['first'],parts[-1]['last']),(1,500))
        self.assertLessEqual(max(len(p['children']) for p in parts),3)
        headers[-1]['chain']='changed'
        newer=scopes.tree(headers,1,500,3,3)
        self.assertNotEqual(parts[-1]['part_id'],newer[-1]['part_id'])
        self.assertEqual(parts[0]['part_id'],newer[0]['part_id'])

    def test_scope_coverage_and_synthesis_are_bounded_in_real_workflow(self):
        self.repo.save(workflow.new_book(tracked_contract(12)))
        owner=self.app.run(finish=True)['owner']
        seen=[]
        for _ in range(300):
            h=self.app.advance(owner=owner)
            if h['action']=='await_author':
                self.app.approve(h['prose_hash'],'工程认可。',owner); continue
            if h['action']!='task_ready':
                self.assertEqual(h['action'],'ready_to_complete'); break
            w=self.repo.pending()['input']
            if w['stage']=='scope_synthesis':
                self.assertLessEqual(len(w['prose']),6)
                self.assertLessEqual(len(w['payload']['children']),3)
                seen.append(w['payload']['level'])
                result=tracked_response(self.app)
                bad=copy.deepcopy(result); bad['data']['coverage'].pop()
                self.assertCode('scope_coverage',self.app.submit,bad)
                self.app.submit(result)
            else:
                self.app.submit(tracked_response(self.app))
        self.assertGreaterEqual(max(seen),2)
        self.assertTrue(self.app.complete(owner)['completed'])

    def test_tracked_narrow_revision_carries_suffix_and_reaudits(self):
        owner=self.app.run(finish=True)['owner']
        drive_tracked(self.app,owner); self.app.complete(owner)
        self.app.revise(1,'工程仅改标题。',owner,1)
        self.assertEqual(drive_tracked(self.app,owner)['action'],'revision_ready')
        self.app.promote(owner)
        self.assertTrue(self.app.audit()['ok'])


if __name__=='__main__':
    unittest.main()
