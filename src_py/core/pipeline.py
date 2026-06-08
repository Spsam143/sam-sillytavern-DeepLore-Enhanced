from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class VaultEntry(BaseModel):
    """
    A single entry loaded from the Obsidian vault.
    Highly optimized for fast serialization.
    """
    filename: str
    title: str
    keys: List[str] = Field(default_factory=list)
    content: str
    summary: str = ""
    priority: int = 100
    constant: bool = False
    seed: bool = False
    bootstrap: bool = False
    guide: bool = False
    tokenEstimate: int = 0
    scanDepth: Optional[int] = None
    excludeRecursion: bool = False
    links: List[str] = Field(default_factory=list)
    resolvedLinks: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    requires: List[str] = Field(default_factory=list)
    excludes: List[str] = Field(default_factory=list)
    refineKeys: List[str] = Field(default_factory=list)
    cascadeLinks: List[str] = Field(default_factory=list)
    outlet: Optional[str] = None
    injectionPosition: Optional[int] = None
    injectionDepth: Optional[int] = None
    injectionRole: Optional[int] = None
    cooldown: Optional[int] = None
    warmup: Optional[int] = None
    probability: Optional[float] = None
    folderPath: Optional[str] = None
    vaultSource: str = ""
    customFields: Dict[str, Any] = Field(default_factory=dict)
    graph: bool = True
    _parserWarnings: Optional[List[Dict[str, Any]]] = None

    class Config:
        validate_assignment = True
        extra = "allow"
