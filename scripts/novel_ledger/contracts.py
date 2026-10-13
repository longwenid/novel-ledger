"""Shared wire contracts and value utilities; no I/O or domain imports."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

VERSION = '1.0.0'
SCHEMA = 'novel-ledger/2'
TASK = 'novel-ledger.task/1'
RESULT = 'novel-ledger.result/1'
FACT_CHECKS = ('coverage', 'continuity', 'resources', 'knowledge', 'time', 'world_rules', 'space')
READER_CHECKS = ('read_on', 'character', 'change', 'emotion_cost', 'language', 'repetition', 'substance')
LONG_CHECKS = ('causality', 'character_arcs', 'payoffs', 'pacing', 'world_rules', 'coverage')
DESIGN_CHECKS = ('author_constraints', 'causality', 'characters', 'disclosure', 'scale')
WORLD_CHECKS = ('choice_alignment', 'rule_consistency', 'spatial_connections', 'historical_causes',
                'faction_interests', 'economic_consequences', 'social_pressure', 'character_boundaries', 'disclosure', 'story_capacity')
FIRST_READ = ('desire', 'obstacle', 'change', 'read_on_reason')
REPAIRS = 2
REDESIGNS = 1
TIME_MARKERS = tuple('日天夜晨早晚午时年月春夏秋冬晓暮昏宵旬翌昨今明') + ('星期', '分钟', '秒钟')
DEFAULT_TERMS = ['账本', '入账', '回执']
DEFAULT_NAME_CHARS = ['砚']
# Work-directory artifacts the controller may regenerate; everything else in a task directory
# is authored by a Worker and is never rewritten behind its back.
FORM_ARTIFACTS = ('input.json', 'result.template.json')

# Single authority for the author contract: field, kind, default, whether the guided opening
# must preserve it, and whether an empty value is a valid skeleton entry. The delivery
# template, the validator and the alignment check are all derived from this table.
CONTRACT_TYPES = {
    'text': (str,),
    'int': (int,),
    'bool': (bool,),
    'band': (list,),
    'rows': (list,),
    'map': (dict,),
}
CONTRACT_FIELDS = (
    {'key': 'title', 'kind': 'text', 'default': '', 'alignment': True},
    {'key': 'reader_promise', 'kind': 'text', 'default': '', 'alignment': True},
    {'key': 'ending', 'kind': 'text', 'default': '', 'alignment': True},
    {'key': 'genre', 'kind': 'text', 'default': '', 'alignment': True},
    {'key': 'story_engine', 'kind': 'text', 'default': '', 'alignment': True},
    {'key': 'opposition', 'kind': 'text', 'default': '', 'alignment': True},
    {'key': 'world_premise', 'kind': 'text', 'default': '', 'alignment': True},
    {'key': 'voice', 'kind': 'text', 'default': '', 'alignment': True},
    {'key': 'allow_special_mechanism', 'kind': 'bool', 'default': None, 'alignment': True},
    {'key': 'red_lines', 'kind': 'rows', 'default': [], 'alignment': True, 'optional': True},
    {'key': 'style_traits', 'kind': 'rows', 'default': [], 'alignment': True},
    {'key': 'relationships', 'kind': 'rows', 'default': [], 'alignment': True},
    {'key': 'world_rules', 'kind': 'rows', 'default': [], 'alignment': True},
    {'key': 'protagonist_setup', 'kind': 'map', 'default': '', 'alignment': True,
     'shape': ('id', 'name', 'identity', 'desire', 'limit')},
    {'key': 'entities', 'kind': 'rows', 'default': [], 'alignment': True},
    {'key': 'initial_resources', 'kind': 'rows', 'default': [], 'alignment': False},
    {'key': 'volumes', 'kind': 'rows', 'default': [], 'alignment': True,
     'shape': ('id', 'purpose', 'end'), 'blank': False, 'count': 1},
    {'key': 'word_range', 'kind': 'band', 'default': [], 'alignment': True},
    {'key': 'chapter_min', 'kind': 'int', 'default': None, 'alignment': True},
    {'key': 'chapter_max', 'kind': 'int', 'default': None, 'alignment': True},
    {'key': 'chapter_aim', 'kind': 'int', 'default': None, 'alignment': True},
    {'key': 'planning_window', 'kind': 'int', 'default': 3, 'alignment': False},
    {'key': 'review_interval', 'kind': 'int', 'default': 10, 'alignment': False},
    {'key': 'review_chunk', 'kind': 'int', 'default': 3, 'alignment': False},
    {'key': 'initial_facts', 'kind': 'rows', 'default': [], 'alignment': False, 'optional': True},
    {'key': 'places', 'kind': 'rows', 'default': [], 'alignment': False, 'optional': True},
    {'key': 'placements', 'kind': 'map', 'default': {}, 'alignment': False, 'optional': True},
    {'key': 'arcs', 'kind': 'rows', 'default': [], 'alignment': False, 'optional': True},
)
CONTRACT_KEYS = tuple(row['key'] for row in CONTRACT_FIELDS)
CONTRACT_ALIGNMENT = tuple(row['key'] for row in CONTRACT_FIELDS if row['alignment'])
CHARACTERS = ('name', 'role', 'desire', 'limit', 'knowledge_boundary')
POLICY_FIELDS = ('forbidden_terms', 'forbidden_name_chars')


def _placeholder(row):
    if row['kind'] in ('rows', 'band'):
        if row.get('shape'):
            entries = [{field: (0 if field == 'end' else '') for field in row['shape']}]
            return entries * row.get('count', 1)
        return copy.deepcopy(row['default'])
    if row['kind'] == 'map':
        return {field: '' for field in row.get('shape', ())}
    if row['kind'] == 'int':
        return 0
    return copy.deepcopy(row['default'])


def contract_skeleton():
    """A contract-shaped object carrying every key; never a valid contract on its own."""
    return {row['key']: _placeholder(row) for row in CONTRACT_FIELDS}


def contract_errors(raw):
    """Mechanical shape check against CONTRACT_FIELDS. Returns complaints, never raises."""
    complaints = []
    if not isinstance(raw, dict):
        return ['约定须为对象。']
    for unknown in sorted(set(raw) - set(CONTRACT_KEYS)):
        complaints.append('未知约定字段：' + unknown)
    for row in CONTRACT_FIELDS:
        key, kind = row['key'], row['kind']
        if key not in raw:
            if not row.get('optional'):
                complaints.append('缺少约定字段：' + key)
            continue
        value = raw[key]
        if kind == 'band':
            if not isinstance(value, list) or len(value) != 2 or not all(type(n) is int and n > 0 for n in value) \
                    or value[0] > value[1]:
                complaints.append('word_range 须为有效总汉字区间。')
            continue
        if kind == 'rows':
            if not isinstance(value, list):
                complaints.append(key + ' 须为数组。')
            elif row.get('blank') is False and len(value) < row.get('count', 1):
                complaints.append(key + ' 须提供至少 ' + str(row.get('count', 1)) + ' 条完整记录。')
            continue
        if kind == 'map':
            if not isinstance(value, dict) or any(field not in value for field in row.get('shape', ())):
                complaints.append(key + ' 须包含字段：' + '/'.join(row.get('shape', ())))
            continue
        if kind == 'text':
            if not text(value):
                complaints.append(key + ' 须为非空文本。')
            continue
        if value is None:
            continue
        if kind == 'bool':
            if type(value) is not bool:
                complaints.append(key + ' 须为布尔值。')
        elif type(value) is not int or value <= 0:
            complaints.append(key + ' 须为正整数。')
    return complaints



class Error(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message = code, message
        self.details = details or {'recover': '按当前任务模板修正后重提；不要改库或替换任务身份。'}

    def as_dict(self):
        return {'error': self.code, 'message': self.message, 'details': self.details}


def require(ok, code, message, details=None):
    if not ok:
        raise Error(code, message, details)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(dump(value).encode('utf-8')).hexdigest()


def han_count(prose):
    return sum('\u3400' <= c <= '\u4dbf' or '\u4e00' <= c <= '\u9fff' or '\U00020000' <= c <= '\U0003134f' for c in prose)


@dataclass(frozen=True)
class Job:
    stage: str
    chapter: int
    scope: str = 'chapter'
    first: int = 0
    last: int = 0
    payload: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class Outcome:
    book: Dict[str, Any]
    chapter: Optional[Dict[str, Any]] = None


class Repository(Protocol):
    """Only operations used by application/query layers; never handed to domains."""
    def load(self): ...
    def save(self, book): ...
    def document(self, value): ...
    def read_document(self, key): ...
    def pending(self): ...
    def task(self, task_id): ...
    def add_task(self, work): ...
    def finish_task(self, task_id, result): ...
    def headers(self, branch): ...
    def chapter(self, branch, chapter): ...
    def add_chapter(self, branch, row): ...
    def session_task(self, session): ...
    def bind_session(self, session, task_id): ...
    def record(self, action, value): ...

