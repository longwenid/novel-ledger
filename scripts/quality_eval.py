#!/usr/bin/env python3
"""Prepare external blind literary cases and score source-bound review receipts.

No model is called and no novel is written into the Skill directory. Seeded
defects measure detection; unadjudicated original prose is never treated as gold.
"""
from __future__ import annotations
import argparse
import json
import uuid
from pathlib import Path
from novel_ledger.contracts import Error, digest, dump, require, text as nonblank
from novel_ledger.delivery import json_write as write_json

CRITERIA=('knowledge','motivation','cost','causality','progress','payoff','language','pacing')
# The frozen first read is this tool's own protocol now: v2 removed the reviewer stages, so the
# validator lives here instead of in a review-receipt module. It still exists because a blind
# offline evaluation is the one independent judgment left once reviewers are gone.
FIRST_READ=('desire','obstacle','change','read_on_reason')
ROOT=Path(__file__).resolve().parents[1]


def first_read(data, sources):
    """A frozen first read must cover every chapter with four concrete impressions each."""
    require(isinstance(data, dict) and isinstance(data.get('reads'), list), 'first_read',
            '首读需要 reads 数组。', {'expect': {'reads': [{'chapter': 'int', **{k: 'str' for k in FIRST_READ}}]}})
    reads = data['reads']
    require(len(reads) == len(sources)
            and all(isinstance(row, dict) and type(row.get('chapter')) is int and row['chapter'] in sources for row in reads)
            and {row['chapter'] for row in reads} == set(sources), 'first_read', '首读须完整覆盖全部冻结正文。',
            {'expect_chapters': sorted(sources)})
    for row in reads:
        require(all(nonblank(row.get(k)) for k in FIRST_READ), 'first_read', '每章首读四项均须为具体非空体验。')
    return data


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def external(path):
    path=Path(path).resolve()
    require(path!=ROOT and ROOT not in path.parents,'project_isolation','评测数据目录必须在 Skill 源码目录外')
    return path


def validate_locations(work, locations):
    texts = {row['chapter']: row['prose'] for row in work['chapters']}
    require(isinstance(locations, list), 'coverage', '植入位置须为数组。')
    for location in locations:
        require(isinstance(location, dict) and type(location.get('chapter')) is int
                and location['chapter'] in texts, 'coverage', '植入章必须在评审实际收到的冻结章节中。')
        start, end = location.get('start'), location.get('end')
        require(type(start) is int and type(end) is int
                and 0 <= start <= end <= len(texts[location['chapter']]),
                'patch', '植入位置须为冻结正文内的有效字符范围。')
        require(location.get('criterion') in CRITERIA, 'criterion', '未知文学判断项。')


def prepare(manifest_path,out):
    manifest_path=Path(manifest_path).resolve();manifest=load(manifest_path);out=external(out)
    require(not (out/'private.json').exists(),'exists','评测批次已存在；用新目录保存冻结样本')
    require(isinstance(manifest,dict) and isinstance(manifest.get('chapters'),list) and manifest['chapters']
            and isinstance(manifest.get('cases'),list) and manifest['cases'],
            'manifest','评测清单须为对象，chapters 和 cases 为非空数组。')
    source={}
    for row in manifest['chapters']:
        require(isinstance(row,dict) and nonblank(row.get('path')),'manifest','来源章须为含 path 的对象。')
        n=row.get('chapter');require(type(n) is int and n>0 and n not in source,'chapter','源章号须为唯一正整数')
        path=Path(row['path']);path=path if path.is_absolute() else manifest_path.parent/path
        prose=path.read_text(encoding='utf-8')
        source[n]={'chapter':n,'prose':prose,'source_hash':digest(prose),**({'volume':row['volume']} if 'volume' in row else {})}
    records=[];packages=[]
    for case in manifest['cases']:
        require(isinstance(case,dict),'manifest','每个评测案例须为对象。')
        chapters={n:dict(row) for n,row in source.items()}
        chosen=case.get('chapters',sorted(chapters));targets=case.get('targets',chosen)
        require(isinstance(chosen,list) and chosen and all(type(n) is int for n in chosen)
                and len(chosen)==len(set(chosen)) and all(n in chapters for n in chosen)
                and isinstance(targets,list) and targets and all(type(n) is int for n in targets)
                and len(targets)==len(set(targets)) and set(targets)<=set(chosen),
                'coverage','评测目标与依赖原章须明确且全部存在')
        edits=case.get('edits',[]);locations=[]
        require(isinstance(edits,list) and all(isinstance(e,dict) and type(e.get('chapter')) is int
                and type(e.get('start')) is int for e in edits),'edits','edits 须为含有效章号和字符位置的对象数组')
        require(all(e['chapter'] in chosen for e in edits),'coverage','植入章必须在评审实际收到的冻结章节中。')
        for n in {e['chapter'] for e in edits}:
            require(n in chapters,'chapter','修改章须属于已冻结来源')
            text=chapters[n]['prose'];ordered=sorted([e for e in edits if e['chapter']==n],key=lambda e:e['start']);previous=0;shift=0
            for edit in ordered:
                start=edit['start'];old=edit['old'];new=edit['new']
                require(type(start) is int and start>=previous and isinstance(old,str) and old and text[start:start+len(old)]==old and isinstance(new,str),'patch','变体须精确定位且修改范围不能重叠')
                locations.append({'chapter':n,'start':start+shift,'end':start+shift+len(new),'criterion':edit['criterion']})
                require(edit['criterion'] in CRITERIA,'criterion','未知文学判断项')
                shift+=len(new)-len(old);previous=start+len(old)
            for edit in reversed(ordered):text=text[:edit['start']]+edit['new']+text[edit['start']+len(edit['old']):]
            chapters[n]['prose']=text;chapters[n]['source_hash']=digest(text)
        ident=uuid.uuid4().hex
        work={'schema':'novel-ledger.literary-case/1','case_id':ident,'target_chapters':targets,
              'chapters':[chapters[n] for n in sorted(chosen)],'criteria':list(CRITERIA),
              'instruction':'独立阅读正文，先记录 first_read，再检查所知、动机变化、已付代价、因果、主线、承诺兑现、语言取舍和节奏。静章不因事件少而判差；高潮不强求插休息。依赖章必须完整核对；不要寻找预设错误，不读作者自评。每个发现提供 criterion、severity、reason、evidence[{chapter,start,quote}]，quote 为完整必要语境的精确原文。无问题也按实际判断，不承诺质量由字段证明。'}
        validate_locations(work, locations)
        packages.append((ident,work))
        records.append({'case_id':ident,'label':case.get('label',ident),'input_hash':digest(work),'locations':locations,
                        'expectations':case.get('expectations',[]),'chapters':sorted(chosen),'targets':targets})
    private={'schema':'novel-ledger.literary-evaluation/1','manifest_hash':digest(manifest),
             'source_hashes':{str(n):row['source_hash'] for n,row in source.items()},'cases':records}
    # Validate the complete batch before creating any public or private artifacts.
    for ident,work in packages:
        write_json(out/ident/'input.json',work)
    write_json(out/'private.json',private)
    return {'directory':str(out),'cases':[{'case_id':r['case_id'],'input':str(out/r['case_id']/'input.json'),'output':str(out/r['case_id']/'review.json')} for r in records],
            'boundary':'评审仅收到各自 input；private 与原始 manifest 含变体预期，必须对评审隔离。'}


def validate_review(work,review):
    require(isinstance(review,dict) and review.get('case_id')==work['case_id'] and review.get('input_hash')==digest(work),'stale_case','回执未绑定当前冻结样本')
    require(isinstance(review.get('first_read'),dict) and review['first_read'],'review','须先记录真实首读体验')
    checks=review.get('checks');findings=review.get('findings')
    require(isinstance(checks,list) and all(isinstance(c,dict) and c.get('id') in CRITERIA for c in checks)
            and {c['id'] for c in checks}==set(CRITERIA) and len(checks)==len(CRITERIA),'checks','须覆盖八项独立判断')
    require(isinstance(findings,list) and all(isinstance(f,dict) and f.get('criterion') in CRITERIA for f in findings),
            'findings','findings 须为含有效 criterion 的对象数组')
    texts={c['chapter']:c['prose'] for c in work['chapters']}
    for index,row in enumerate(checks+findings):
        is_check=index<len(checks)
        require(isinstance(row.get('reason'),str) and row['reason'].strip(),'review','每项须给出适用项与判断理由')
        if is_check:require(row.get('result') in ('pass','fix','not_applicable'),'checks','判断结果为 pass/fix/not_applicable')
        else:require(row.get('severity') in ('blocking','major','minor'),'severity','发现须标记影响程度')
        evidence=row.get('evidence',[])
        require(isinstance(evidence,list),'evidence','evidence 须为数组')
        require(evidence or is_check and row.get('result')=='not_applicable','evidence','判断须以正文必要语境举证')
        for ref in evidence:
            require(isinstance(ref,dict),'evidence','证据须为对象')
            n=ref.get('chapter');start=ref.get('start');quote=ref.get('quote')
            require(type(n) is int and n in texts and type(start) is int and start>=0 and isinstance(quote,str) and quote and texts[n][start:start+len(quote)]==quote,'evidence','证据须精确匹配冻结正文')
    for check in checks:
        matching=[f for f in findings if f['criterion']==check['id']]
        require((check['result']=='fix')==bool(matching),'verdict','fix须有对应发现，pass/not_applicable不能有该项发现')
    return review


def score(directory):
    directory=external(directory);private=load(directory/'private.json');cases=[];tp=fn=0;control_alerts=0;gold_tp=gold_fp=gold_fn=0;pending=gold_evaluated=0
    for case in private['cases']:
        folder=directory/case['case_id'];work=load(folder/'input.json');require(digest(work)==case['input_hash'],'source','评测工作包被改动')
        validate_locations(work, case.get('locations'))
        review=validate_review(work,load(folder/'review.json'));sealed=load(folder/'first-read.json');require(sealed['input_hash']==digest(work) and review['first_read']==sealed['data'],'first_read_frozen','评测首读必须先冻结，不能在核对材料后改写');detections=[]
        for location in case['locations']:
            detected=any(f['criterion']==location['criterion'] and any(e['chapter']==location['chapter'] and e['start']<location['end'] and e['start']+len(e['quote'])>location['start'] for e in f['evidence']) for f in review['findings'])
            tp+=detected;fn+=not detected;detections.append({**location,'detected':detected})
        if not case['locations']:control_alerts+=len(review['findings'])
        for expectation in case['expectations']:
            require(expectation.get('criterion') in CRITERIA and expectation.get('expected') in ('pass','fix'),'gold','预期判断项无效')
            if not expectation.get('adjudicator') or not expectation.get('reason'):
                pending+=1;continue
            gold_evaluated+=1
            fix=any(f['criterion']==expectation['criterion'] and any(e['chapter'] in case['targets'] for e in f['evidence']) for f in review['findings'])
            gold_tp+=fix and expectation['expected']=='fix';gold_fp+=fix and expectation['expected']=='pass';gold_fn+=not fix and expectation['expected']=='fix'
        cases.append({'case_id':case['case_id'],'label':case['label'],'input_hash':case['input_hash'],
                      'review_hash':digest(review),'input_chars':len(dump(work))+1,'review_chars':len(dump(review))+1,
                      'targets':case['targets'],'seeded_detections':detections,'findings':len(review['findings'])})
    result={'schema':'novel-ledger.literary-score/1','cases':cases,'seeded':{'true_positive':tp,'false_negative':fn,'recall':tp/(tp+fn) if tp+fn else None},
            'controls':{'alerts_pending_adjudication':control_alerts},
            'adjudicated':{'expectations_evaluated':gold_evaluated,'true_positive':gold_tp if gold_evaluated else None,'false_positive':gold_fp if gold_evaluated else None,'false_negative':gold_fn if gold_evaluated else None,'pending_expectations':pending,
                          'precision':gold_tp/(gold_tp+gold_fp) if gold_tp+gold_fp else None},
            'billed_tokens':None,'boundary':'精确引文与覆盖只证格式；植入缺陷命中是定位指标，不单独证明推理正确。原稿和模型评价不是专家金标准，跨卷结论须有真实卷界与覆盖。'}
    write_json(directory/'score.json',result);return result


def seal(input_path, receipt_path):
    input_path = external(input_path)
    work, receipt = load(input_path), load(receipt_path)
    require(isinstance(receipt, dict) and receipt.get('case_id') == work['case_id']
            and receipt.get('input_hash') == digest(work), 'stale_case', '首读须绑定准确样本。')
    value = first_read(receipt.get('data'), {c['chapter']: c['prose'] for c in work['chapters']})
    path = input_path.parent / 'first-read.json'
    frozen = {'case_id': work['case_id'], 'input_hash': digest(work), 'data': value}
    require(not path.exists() or load(path) == frozen, 'first_read_frozen', '已冻结首读不可改写。')
    if not path.exists():
        write_json(path, frozen)
    return {'sealed': True, 'path': str(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--manifest', required=True)
    prep.add_argument('--out', required=True)
    report = sub.add_parser('score')
    report.add_argument('--directory', required=True)
    first = sub.add_parser('first-read')
    first.add_argument('--input', required=True)
    first.add_argument('--file', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            result = prepare(args.manifest, args.out)
        elif args.command == 'first-read':
            result = seal(args.input, args.file)
        else:
            result = score(args.directory)
    except (Error, OSError, ValueError, KeyError) as exc:
        print(dump({'error': getattr(exc, 'code', 'evaluation'), 'message': str(exc)}))
        raise SystemExit(1)
    print(dump(result))


if __name__ == '__main__':
    main()
