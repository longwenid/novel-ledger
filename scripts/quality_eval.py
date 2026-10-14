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
from novel_ledger.contracts import Error, digest, dump, require
from novel_ledger.delivery import json_write as write_json
from novel_ledger.quality import first_read

CRITERIA=('knowledge','motivation','cost','causality','progress','payoff','language','pacing')
ROOT=Path(__file__).resolve().parents[1]


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def external(path):
    path=Path(path).resolve()
    require(path!=ROOT and ROOT not in path.parents,'project_isolation','评测数据目录必须在 Skill 源码目录外')
    return path


def prepare(manifest_path,out):
    manifest_path=Path(manifest_path).resolve();manifest=load(manifest_path);out=external(out)
    require(not (out/'private.json').exists(),'exists','评测批次已存在；用新目录保存冻结样本')
    source={}
    for row in manifest['chapters']:
        n=row['chapter'];require(type(n) is int and n>0 and n not in source,'chapter','源章号须为唯一正整数')
        path=Path(row['path']);path=path if path.is_absolute() else manifest_path.parent/path
        prose=path.read_text(encoding='utf-8')
        source[n]={'chapter':n,'prose':prose,'source_hash':digest(prose),**({'volume':row['volume']} if 'volume' in row else {})}
    records=[]
    for case in manifest['cases']:
        chapters={n:dict(row) for n,row in source.items()}
        edits=case.get('edits',[]);locations=[]
        require(isinstance(edits,list),'edits','edits 须为数组')
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
        chosen=case.get('chapters',sorted(chapters));targets=case.get('targets',chosen)
        require(chosen and len(chosen)==len(set(chosen)) and all(n in chapters for n in chosen) and targets and set(targets)<=set(chosen),'coverage','评测目标与依赖原章须明确且全部存在')
        ident=uuid.uuid4().hex
        work={'schema':'novel-ledger.literary-case/1','case_id':ident,'target_chapters':targets,
              'chapters':[chapters[n] for n in sorted(chosen)],'criteria':list(CRITERIA),
              'instruction':'独立阅读正文，先记录 first_read，再检查所知、动机变化、已付代价、因果、主线、承诺兑现、语言取舍和节奏。静章不因事件少而判差；高潮不强求插休息。依赖章必须完整核对；不要寻找预设错误，不读作者自评。每个发现提供 criterion、severity、reason、evidence[{chapter,start,quote}]，quote 为完整必要语境的精确原文。无问题也按实际判断，不承诺质量由字段证明。'}
        write_json(out/ident/'input.json',work)
        records.append({'case_id':ident,'label':case.get('label',ident),'input_hash':digest(work),'locations':locations,
                        'expectations':case.get('expectations',[]),'chapters':sorted(chosen),'targets':targets})
    private={'schema':'novel-ledger.literary-evaluation/1','manifest_hash':digest(manifest),
             'source_hashes':{str(n):row['source_hash'] for n,row in source.items()},'cases':records}
    write_json(out/'private.json',private)
    return {'directory':str(out),'cases':[{'case_id':r['case_id'],'input':str(out/r['case_id']/'input.json'),'output':str(out/r['case_id']/'review.json')} for r in records],
            'boundary':'评审仅收到各自 input；private 与原始 manifest 含变体预期，必须对评审隔离。'}


def validate_review(work,review):
    require(isinstance(review,dict) and review.get('case_id')==work['case_id'] and review.get('input_hash')==digest(work),'stale_case','回执未绑定当前冻结样本')
    require(isinstance(review.get('first_read'),dict) and review['first_read'],'review','须先记录真实首读体验')
    checks=review.get('checks');findings=review.get('findings')
    require(isinstance(checks,list) and {c.get('id') for c in checks}==set(CRITERIA) and len(checks)==len(CRITERIA),'checks','须覆盖八项独立判断')
    require(isinstance(findings,list),'findings','findings 须为数组')
    texts={c['chapter']:c['prose'] for c in work['chapters']}
    for row in checks+findings:
        require(row.get('id',row.get('criterion')) in CRITERIA and isinstance(row.get('reason'),str) and row['reason'].strip(),'review','每项须给出适用项与判断理由')
        if row in checks:require(row.get('result') in ('pass','fix','not_applicable'),'checks','判断结果为 pass/fix/not_applicable')
        else:require(row.get('severity') in ('blocking','major','minor'),'severity','发现须标记影响程度')
        evidence=row.get('evidence',[])
        require(isinstance(evidence,list),'evidence','evidence 须为数组')
        require(evidence or row.get('result')=='not_applicable','evidence','判断须以正文必要语境举证')
        for ref in evidence:
            n=ref.get('chapter');start=ref.get('start');quote=ref.get('quote')
            require(n in texts and type(start) is int and start>=0 and isinstance(quote,str) and quote and texts[n][start:start+len(quote)]==quote,'evidence','证据须精确匹配冻结正文')
    for check in checks:
        matching=[f for f in findings if f['criterion']==check['id']]
        require((check['result']=='fix')==bool(matching),'verdict','fix须有对应发现，pass/not_applicable不能有该项发现')
    return review


def score(directory):
    directory=external(directory);private=load(directory/'private.json');cases=[];tp=fn=0;control_alerts=0;gold_tp=gold_fp=gold_fn=0;pending=gold_evaluated=0
    for case in private['cases']:
        folder=directory/case['case_id'];work=load(folder/'input.json');require(digest(work)==case['input_hash'],'source','评测工作包被改动')
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
    input_path = Path(input_path).resolve()
    work, receipt = load(input_path), load(receipt_path)
    require(receipt.get('case_id') == work['case_id'] and receipt.get('input_hash') == digest(work), 'stale_case', '首读须绑定准确样本。')
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
