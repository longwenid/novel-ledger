#!/usr/bin/env python3
"""Summarize provider-supplied usage without changing a story or inventing costs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from novel_ledger.contracts import Error, dump, require, text


def summarize(path):
    calls = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        require(isinstance(row, dict) and all(text(row.get(k)) for k in ('provider', 'session_id', 'request_id')),
                'observation', '每项需 provider/session_id/request_id；只导入宿主实际报告。')
        for field in ('input_tokens', 'cache_read_tokens', 'output_tokens'):
            require(row.get(field) is None or type(row[field]) is int and row[field] >= 0, 'observation', 'token 须非负整数或 null。')
        key = (row['provider'], row['session_id'], row['request_id'])
        require(key not in calls or calls[key] == row, 'observation_conflict', '同一调用的不同观测不可重复累加。')
        calls[key] = row
    values = list(calls.values())
    fields = ('input_tokens', 'cache_read_tokens', 'output_tokens')
    totals = {k: sum(r[k] for r in values) if values and all(r.get(k) is not None for r in values) else None for k in fields}
    return {'calls': len(values), **totals,
            'gross_tokens': sum(totals.values()) if all(v is not None for v in totals.values()) else None,
            'cost': None, 'boundary': '输入 token 须为非缓存部分，cache_read_tokens 单列；缺日志或用量时为 null。费用按供应商规则另算。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('summary',))
    parser.add_argument('path')
    args = parser.parse_args()
    try:
        print(dump(summarize(args.path)))
    except (Error, OSError, ValueError) as exc:
        print(dump({'error': getattr(exc, 'code', 'observation'), 'message': str(exc)}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
