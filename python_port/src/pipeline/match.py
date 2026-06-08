from typing import List, Dict, Tuple, Any, Optional
import random
from python_port.core.models import VaultEntry, Settings
from python_port.core.utils import trackerKey
from python_port.core.matching import testEntryMatch, testPrimaryMatchOnly, countKeywordOccurrences

def matchEntries(chat: List[Dict[str, Any]], snapshot: List[VaultEntry], settings: Settings, characterName: Optional[str] = None) -> Dict[str, Any]:
    entries = snapshot
    matchedSet = set()
    matchedKeys = {}
    probabilitySkipped = []
    warmupFailed = []
    refineKeyBlocked = []

    cooldownTracker = {} # Mock cooldown tracker for pure logic testing

    for entry in entries:
        if entry.constant:
            matchedSet.add(entry)
            matchedKeys[entry.title] = '(constant)'

    if len(chat) <= settings.newChatThreshold:
        for entry in entries:
            if entry.bootstrap and entry not in matchedSet:
                matchedSet.add(entry)
                matchedKeys[entry.title] = '(bootstrap)'

    # Build scan text based on chat. We mock buildScanText to just concatenate chat texts.
    def getScanText(depth: int) -> str:
        messages = chat if depth <= 0 else chat[-depth:]
        return "\n".join([m.get("mes", "") for m in messages])

    if settings.scanDepth > 0:
        globalScanText = getScanText(settings.scanDepth)

        for entry in entries:
            if entry.constant:
                continue

            scanText = getScanText(entry.scanDepth) if entry.scanDepth is not None else globalScanText
            key = testEntryMatch(entry, scanText, settings)

            if not key and entry.refineKeys:
                primaryHit = testPrimaryMatchOnly(entry, scanText, settings)
                if primaryHit:
                    refineKeyBlocked.append({
                        'title': entry.title,
                        'primaryKey': primaryHit,
                        'refineKeys': list(entry.refineKeys)
                    })

            if key:
                if entry.warmup is not None:
                    occurrences = countKeywordOccurrences(entry, scanText, settings)
                    if occurrences < entry.warmup:
                        warmupFailed.append({'title': entry.title, 'needed': entry.warmup, 'found': occurrences})
                        continue

                if entry.probability == 0:
                    probabilitySkipped.append({'title': entry.title, 'probability': 0, 'roll': 0})
                    continue

                if entry.probability is not None and entry.probability < 1.0:
                    roll = random.random()
                    if roll > entry.probability:
                        probabilitySkipped.append({'title': entry.title, 'probability': entry.probability, 'roll': roll})
                        continue

                remaining = cooldownTracker.get(trackerKey(entry), 0)
                if remaining > 0:
                    continue

                matchedSet.add(entry)
                matchedKeys[entry.title] = key

        # Character Context Scan
        titleMap = {e.title.lower(): e for e in entries}
        if settings.characterContextScan and characterName:
            nameLower = characterName.lower()
            charEntry = titleMap.get(nameLower)
            if not charEntry:
                for e in entries:
                    if any(k.lower() == nameLower for k in e.keys):
                        charEntry = e
                        break
            if charEntry and charEntry not in matchedSet:
                matchedSet.add(charEntry)
                matchedKeys[charEntry.title] = '(active character)'

        # Cascade Links
        cascadeSource = list(matchedSet)
        for entry in cascadeSource:
            if not entry.cascadeLinks:
                continue
            for linkTitle in entry.cascadeLinks:
                linked = titleMap.get(linkTitle.lower())
                if linked and linked not in matchedSet:
                    if cooldownTracker.get(trackerKey(linked), 0) > 0:
                        continue
                    if linked.probability == 0:
                        continue
                    if linked.probability is not None and linked.probability < 1.0 and random.random() > linked.probability:
                        continue
                    matchedSet.add(linked)
                    matchedKeys[linked.title] = f'(cascade from: {entry.title})'

    matched = sorted(list(matchedSet), key=lambda x: (x.priority, x.title))

    if settings.keywordOccurrenceWeighting:
        scanText = getScanText(settings.scanDepth)
        occurrenceCache = {}
        def getCachedCount(e):
            if e.title not in occurrenceCache:
                occurrenceCache[e.title] = countKeywordOccurrences(e, scanText, settings)
            return occurrenceCache[e.title]

        matched.sort(key=lambda x: (x.priority, -getCachedCount(x), x.title))

    return {
        'matched': matched,
        'matchedKeys': matchedKeys,
        'probabilitySkipped': probabilitySkipped,
        'warmupFailed': warmupFailed,
        'refineKeyBlocked': refineKeyBlocked
    }

def formatAndGroup(entries: List[VaultEntry], settings: Settings, promptTagPrefix: str = 'deeplore_') -> Dict[str, Any]:
    template = settings.injectionTemplate or '<{{title}}>\n{{content}}\n</{{title}}>'
    totalTokens = 0
    count = 0

    outletEntries = [e for e in entries if e.outlet]
    positionalEntries = [e for e in entries if not e.outlet]

    accepted = []

    for entry in positionalEntries:
        if not settings.unlimitedEntries and count >= settings.maxEntries:
            break
        if not settings.unlimitedBudget and totalTokens + entry.tokenEstimate > settings.maxTokensBudget:
            # We skip truncation logic in this port to simplify, just drop if it exceeds budget
            break

        accepted.append({
            'entry': entry,
            'position': entry.injectionPosition if entry.injectionPosition is not None else settings.injectionPosition,
            'depth': entry.injectionDepth if entry.injectionDepth is not None else settings.injectionDepth,
            'role': entry.injectionRole if entry.injectionRole is not None else settings.injectionRole,
        })
        totalTokens += entry.tokenEstimate
        count += 1

    return {
        'count': count + len(outletEntries),
        'totalTokens': totalTokens,
        'acceptedEntries': [a['entry'] for a in accepted] + outletEntries
    }
