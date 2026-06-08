import asyncio
from typing import List, Dict, Any, Optional
from python_port.core.models import VaultEntry, Settings
from python_port.src.stages import (
    buildExemptionPolicy, applyRequiresExcludesGating,
    applyContextualGating, applyFolderFilter, applyStripDedup
)
from python_port.src.pipeline.match import matchEntries

async def runPipeline(chat: List[Dict[str, Any]], vaultSnapshot: List[VaultEntry], settings: Settings,
                      contextualGatingContext: Any = None, pins: List[Any] = None, blocks: List[Any] = None,
                      folderFilter: List[str] = None, characterName: str = None) -> Dict[str, Any]:

    pins = pins or []
    blocks = blocks or []
    folderFilter = folderFilter or []

    await asyncio.sleep(0)  # Yield control to event loop

    # Step 1: Match Entries
    match_result = matchEntries(chat, vaultSnapshot, settings, characterName)
    finalEntries = match_result['matched']
    matchedKeys = match_result['matchedKeys']

    await asyncio.sleep(0)

    # Step 2: Requires/Excludes Gating
    policy = buildExemptionPolicy(vaultSnapshot, pins, blocks)
    finalEntries, removed = applyRequiresExcludesGating(finalEntries, policy, settings.debugMode)

    await asyncio.sleep(0)

    # Step 3: Contextual Gating
    if contextualGatingContext:
        finalEntries = applyContextualGating(finalEntries, contextualGatingContext, policy, settings.debugMode, settings, None)

    await asyncio.sleep(0)

    # Step 4: Folder Filter
    if folderFilter:
        finalEntries = applyFolderFilter(finalEntries, folderFilter, policy, settings.debugMode)

    await asyncio.sleep(0)

    # Note: Strip Dedup and other post-generation tracking logic is often applied via wrapper functions.
    # In pure logic scope, we return the filtered items.

    # Priority sort to finalize
    finalEntries.sort(key=lambda x: (x.priority, x.title))

    return {
        'finalEntries': finalEntries,
        'matchedKeys': matchedKeys
    }
