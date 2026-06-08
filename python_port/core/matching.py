import re
import unicodedata
from typing import Dict, Any, List, Optional, Tuple, Set
from python_port.core.models import VaultEntry, Settings
from python_port.core.utils import escapeRegex

# Regex cache
# JS uses a WeakMap or similar keyed by entry. We'll use id(entry) since Python's id is unique for the lifetime of the object,
# or a dict using the object reference. We will use a regular dict with the id as the key.
_regex_cache: Dict[int, Dict[str, Any]] = {}

_last_scan_text: str = ""
_last_scan_text_lower: str = ""

def getCachedRegexes(entry: VaultEntry, settings: Settings) -> Dict[str, Any]:
    global _regex_cache
    entry_id = id(entry)
    cache_key = f"{settings.caseSensitive}|{settings.matchWholeWords}"

    if entry_id in _regex_cache:
        cache = _regex_cache[entry_id]
        if cache.get('_key') == cache_key:
            return cache

    MAX_KEYWORD_LENGTH = 200
    cache = {'_key': cache_key, 'primary': [], 'refine': []}

    for raw_key in entry.keys:
        if not raw_key or not raw_key.strip():
            continue

        # We don't implement the console.warn since it's just pure logic. We'll just truncate.
        truncated_key = raw_key[:MAX_KEYWORD_LENGTH]

        # JS normalize('NFC') is equivalent to unicodedata.normalize('NFC', ...)
        key = truncated_key if settings.caseSensitive else unicodedata.normalize('NFC', truncated_key).lower()

        if settings.matchWholeWords:
            # JS: /\s/.test(key)
            if re.search(r'\s', key):
                cache['primary'].append({
                    'rawKey': raw_key,
                    'key': key,
                    'regex': None,
                    'regexG': None,
                    'isMultiWord': True
                })
            else:
                escaped = escapeRegex(key)
                # JS: /^\w/.test(key) ? '\\b' : '(?<!\\w)'
                prefix = r'\b' if re.match(r'^\w', key) else r'(?<!\w)'
                suffix = r'\b' if re.search(r'\w$', key) else r'(?!\w)'
                flags = 0 if settings.caseSensitive else re.IGNORECASE
                cache['primary'].append({
                    'rawKey': raw_key,
                    'key': key,
                    'regex': re.compile(f"{prefix}{escaped}{suffix}", flags),
                    'regexG': re.compile(f"{prefix}{escaped}{suffix}", flags), # Python regex doesn't need 'g' flag, findall handles it
                    'isMultiWord': False
                })
        else:
            cache['primary'].append({'rawKey': raw_key, 'key': key, 'regex': None, 'regexG': None, 'isMultiWord': False})

    if entry.refineKeys:
        for rk in entry.refineKeys:
            r_key = rk if settings.caseSensitive else unicodedata.normalize('NFC', rk).lower()
            if settings.matchWholeWords:
                if re.search(r'\s', r_key):
                    cache['refine'].append({'rKey': r_key, 'regex': None, 'isMultiWord': True})
                else:
                    escaped = escapeRegex(r_key)
                    prefix = r'\b' if re.match(r'^\w', r_key) else r'(?<!\w)'
                    suffix = r'\b' if re.search(r'\w$', r_key) else r'(?!\w)'
                    flags = 0 if settings.caseSensitive else re.IGNORECASE
                    cache['refine'].append({
                        'rKey': r_key,
                        'regex': re.compile(f"{prefix}{escaped}{suffix}", flags),
                        'isMultiWord': False
                    })
            else:
                cache['refine'].append({'rKey': r_key, 'regex': None, 'isMultiWord': False})

    _regex_cache[entry_id] = cache
    return cache

def _get_haystack(scanText: str, settings: Settings) -> str:
    global _last_scan_text, _last_scan_text_lower
    if settings.caseSensitive:
        return scanText
    else:
        if scanText != _last_scan_text:
            _last_scan_text_lower = unicodedata.normalize('NFC', scanText).lower()
            _last_scan_text = scanText
        return _last_scan_text_lower

def testEntryMatch(entry: VaultEntry, scanText: str, settings: Settings, trace: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    if not entry.keys:
        return None

    cached = getCachedRegexes(entry, settings)
    haystack = _get_haystack(scanText, settings)

    primary_match = None
    for item in cached['primary']:
        if settings.matchWholeWords:
            if item.get('isMultiWord'):
                if item['key'] in haystack:
                    primary_match = item['rawKey']
                    break
            elif item['regex'].search(haystack):
                primary_match = item['rawKey']
                break
        else:
            if item['key'] in haystack:
                primary_match = item['rawKey']
                break

    if not primary_match:
        if trace is not None:
            trace.append({
                'title': entry.title,
                'vaultSource': entry.vaultSource,
                'result': 'no-primary',
                'primaryMatched': None,
                'refineKeys': [r['rKey'] for r in cached['refine']],
                'reason': 'no primary key in scan text'
            })
        return None

    if cached['refine']:
        has_refine = False
        for item in cached['refine']:
            if settings.matchWholeWords:
                if item.get('isMultiWord'):
                    if item['rKey'] in haystack:
                        has_refine = True
                        break
                elif item['regex'].search(haystack):
                    has_refine = True
                    break
            else:
                if item['rKey'] in haystack:
                    has_refine = True
                    break

        if not has_refine:
            if trace is not None:
                trace.append({
                    'title': entry.title,
                    'vaultSource': entry.vaultSource,
                    'result': 'refine-blocked',
                    'primaryMatched': primary_match,
                    'refineKeys': [r['rKey'] for r in cached['refine']],
                    'reason': f'primary matched "{primary_match}" but no refine_keys present in scan text'
                })
            return None

    if trace is not None:
        trace.append({
            'title': entry.title,
            'vaultSource': entry.vaultSource,
            'result': 'match',
            'primaryMatched': primary_match,
            'refineKeys': [r['rKey'] for r in cached['refine']],
            'reason': None
        })
    return primary_match

def testPrimaryMatchOnly(entry: VaultEntry, scanText: str, settings: Settings) -> Optional[str]:
    if not entry.keys:
        return None

    cached = getCachedRegexes(entry, settings)
    haystack = _get_haystack(scanText, settings)

    for item in cached['primary']:
        if settings.matchWholeWords:
            if item.get('isMultiWord'):
                if item['key'] in haystack:
                    return item['rawKey']
            elif item['regex'].search(haystack):
                return item['rawKey']
        else:
            if item['key'] in haystack:
                return item['rawKey']
    return None

def countKeywordOccurrences(entry: VaultEntry, scanText: str, settings: Settings) -> int:
    count = 0
    cached = getCachedRegexes(entry, settings)
    text = _get_haystack(scanText, settings)

    for item in cached['primary']:
        if settings.matchWholeWords:
            if item.get('isMultiWord'):
                idx = 0
                key_len = len(item['key'])
                if key_len > 0:
                    while True:
                        idx = text.find(item['key'], idx)
                        if idx == -1:
                            break
                        count += 1
                        idx += key_len
            else:
                matches = item['regex'].findall(text)
                if matches:
                    count += len(matches)
        else:
            idx = 0
            key_len = len(item['key'])
            if key_len > 0:
                while True:
                    idx = text.find(item['key'], idx)
                    if idx == -1:
                        break
                    count += 1
                    idx += key_len
    return count

def clearScanTextCache():
    global _last_scan_text, _last_scan_text_lower
    _last_scan_text = ""
    _last_scan_text_lower = ""
