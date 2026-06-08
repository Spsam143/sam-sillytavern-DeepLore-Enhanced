from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union, Set

@dataclass
class VaultEntry:
    filename: str
    title: str
    keys: List[str] = field(default_factory=list)
    content: str = ""
    summary: str = ""
    priority: int = 100
    constant: bool = False
    seed: bool = False
    bootstrap: bool = False
    guide: bool = False
    tokenEstimate: int = 0
    scanDepth: Optional[int] = None
    excludeRecursion: bool = False
    links: List[str] = field(default_factory=list)
    resolvedLinks: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    excludes: List[str] = field(default_factory=list)
    refineKeys: List[str] = field(default_factory=list)
    cascadeLinks: List[str] = field(default_factory=list)
    outlet: Optional[str] = None
    injectionPosition: Optional[int] = None
    injectionDepth: Optional[int] = None
    injectionRole: Optional[int] = None
    cooldown: Optional[int] = None
    warmup: Optional[int] = None
    probability: Optional[float] = None
    folderPath: Optional[str] = None
    vaultSource: str = ""
    customFields: Dict[str, Any] = field(default_factory=dict)
    graph: bool = True
    _parserWarnings: Optional[List[Dict[str, Any]]] = None

    def __hash__(self):
        return id(self)

@dataclass
class Settings:
    enabled: bool = True
    debugMode: bool = False
    caseSensitive: bool = False
    matchWholeWords: bool = True
    scanDepth: int = 0
    newChatThreshold: int = 5
    recursiveScan: bool = False
    maxRecursionSteps: int = 0
    fuzzySearchEnabled: bool = False
    fuzzySearchMinScore: float = 0.5
    characterContextScan: bool = False
    keywordOccurrenceWeighting: bool = False
    aiSearchEnabled: bool = False
    aiSearchMode: str = 'keywords-only'
    aiErrorFallback: str = 'keyword'
    aiEmptyFallback: str = 'constants'
    maxEntries: int = 5
    unlimitedEntries: bool = False
    maxTokensBudget: int = 1000
    unlimitedBudget: bool = False
    injectionMode: str = 'extension'
    injectionTemplate: str = '<{{title}}>\n{{content}}\n</{{title}}>'
    injectionPosition: int = 0
    injectionDepth: int = 0
    injectionRole: int = 0
    reinjectionCooldown: int = 0
    decayEnabled: bool = False
    decayBoostThreshold: int = 5
