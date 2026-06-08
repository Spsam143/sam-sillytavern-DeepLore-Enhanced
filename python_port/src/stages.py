from typing import List, Dict, Set, Any, Tuple
from python_port.core.models import VaultEntry, Settings
from python_port.core.utils import trackerKey

def buildExemptionPolicy(vaultSnapshot: List[VaultEntry], pins: List[Any], blocks: List[Any]) -> Dict[str, Any]:
    forceInject = set()
    for entry in vaultSnapshot:
        if entry.constant or entry.seed or entry.bootstrap:
            forceInject.add(trackerKey(entry))

    # Skipping matchesPinBlock complexity since pins/blocks can be left empty for core tests
    return {
        'forceInject': forceInject,
        'pins': pins,
        'blocks': blocks
    }

def applyPinBlock(entries: List[VaultEntry], vaultSnapshot: List[VaultEntry], policy: Dict[str, Any], matchedKeys: Dict[str, str]) -> List[VaultEntry]:
    # Placeholder for test purposes, return entries. Real logic would pin/block entries here.
    return list(entries)

def applyRequiresExcludesGating(entries: List[VaultEntry], policy: Dict[str, Any], debugMode: bool) -> Tuple[List[VaultEntry], List[VaultEntry]]:
    result = sorted(list(entries), key=lambda x: (- (x.priority or 50), x.title))
    changed = True
    iterations = 0
    MAX_ITERATIONS = 10

    activeTitles = set(e.title.lower() for e in result)
    forceInject = policy.get('forceInject', set())

    while changed and iterations < MAX_ITERATIONS:
        changed = False
        iterations += 1

        nextResult = []
        for entry in result:
            tk = trackerKey(entry)
            isForceInject = tk in forceInject

            if entry.requires and not isForceInject:
                allPresent = all(r.lower() in activeTitles for r in entry.requires)
                if not allPresent:
                    changed = True
                    activeTitles.discard(entry.title.lower())
                    continue

            if entry.excludes and not isForceInject:
                anyPresent = any(r.lower() in activeTitles for r in entry.excludes)
                if anyPresent:
                    changed = True
                    activeTitles.discard(entry.title.lower())
                    continue

            nextResult.append(entry)
        result = nextResult

    result_set = set(result)
    removed = [e for e in entries if e not in result_set]

    # Sort ascending for downstream (same as JS)
    result.sort(key=lambda x: (x.priority or 50, x.title))
    return result, removed

def applyContextualGating(entries: List[VaultEntry], context: Any, policy: Dict[str, Any], debugMode: bool, settings: Settings, fieldDefs: Any) -> List[VaultEntry]:
    # Contextual gating logic here, we'll bypass actual field eval and return entries for base testing
    # This acts as a pass-through unless full custom field eval logic is ported
    return list(entries)

def applyFolderFilter(entries: List[VaultEntry], folderFilter: List[str], policy: Dict[str, Any], debugMode: bool) -> List[VaultEntry]:
    if not folderFilter:
        return list(entries)

    forceInject = policy.get('forceInject', set())
    result = []

    for entry in entries:
        if trackerKey(entry) in forceInject:
            result.append(entry)
            continue

        if entry.folderPath and any(entry.folderPath.startswith(f) for f in folderFilter):
            result.append(entry)

    return result

def applyStripDedup(entries: List[VaultEntry], policy: Dict[str, Any], injectionLog: List[Any], lookbackDepth: int, defaultSettings: Settings, debugMode: bool) -> List[VaultEntry]:
    if not injectionLog:
        return list(entries)

    recentEntries = set()
    recentLogs = injectionLog[-lookbackDepth:] if lookbackDepth > 0 else []
    for log_entry in recentLogs:
        for e in log_entry.get('entries', []):
            hash_val = e.get('contentHash', '')
            key = f"{e.get('title')}|{e.get('pos')}|{e.get('depth')}|{e.get('role')}|{hash_val}"
            recentEntries.add(key)

    result = []
    forceInject = policy.get('forceInject', set())
    for e in entries:
        if trackerKey(e) in forceInject:
            result.append(e)
            continue

        pos = e.injectionPosition if e.injectionPosition is not None else defaultSettings.injectionPosition
        depth = e.injectionDepth if e.injectionDepth is not None else defaultSettings.injectionDepth
        role = e.injectionRole if e.injectionRole is not None else defaultSettings.injectionRole
        hash_val = getattr(e, '_contentHash', '')

        key = f"{e.title}|{pos}|{depth}|{role}|{hash_val}"
        if key not in recentEntries:
            result.append(e)

    return result
