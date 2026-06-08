import pytest
import asyncio
from python_port.core.models import VaultEntry, Settings
from python_port.src.pipeline.pipeline import runPipeline

@pytest.fixture
def settings():
    return Settings(
        enabled=True,
        scanDepth=10,
        newChatThreshold=0,
        caseSensitive=False,
        matchWholeWords=True
    )

@pytest.fixture
def vault():
    return [
        VaultEntry(filename="sword.md", title="Sword of Truth", keys=["sword", "blade"], priority=100),
        VaultEntry(filename="shield.md", title="Aegis Shield", keys=["shield"], priority=50, requires=["Sword of Truth"]),
        VaultEntry(filename="dragon.md", title="Red Dragon", keys=["dragon", "beast"], priority=100, excludes=["Aegis Shield"]),
        VaultEntry(filename="constant.md", title="World Map", keys=[], constant=True, priority=10),
        VaultEntry(filename="word_bound.md", title="Word Bound Test", keys=["bound"], priority=100)
    ]

@pytest.mark.asyncio
async def test_runPipeline_basic(settings, vault):
    chat = [
        {"name": "user", "mes": "I pick up the sword and face the dragon."}
    ]

    result = await runPipeline(chat, vault, settings)
    entries = result['finalEntries']
    titles = [e.title for e in entries]

    # constant should be present
    assert "World Map" in titles

    # 'sword' triggers "Sword of Truth"
    assert "Sword of Truth" in titles

    # 'dragon' triggers "Red Dragon"
    assert "Red Dragon" in titles

    # "Aegis Shield" is not triggered by keys
    assert "Aegis Shield" not in titles

@pytest.mark.asyncio
async def test_runPipeline_requires_excludes(settings, vault):
    chat = [
        {"name": "user", "mes": "I use my shield and sword to fight the dragon."}
    ]

    result = await runPipeline(chat, vault, settings)
    entries = result['finalEntries']
    titles = [e.title for e in entries]

    # 'sword', 'shield', 'dragon' present in chat
    # "Sword of Truth" matched.
    assert "Sword of Truth" in titles

    # "Aegis Shield" matched, requires "Sword of Truth" (which is matched), so it survives.
    # "Red Dragon" matched, but excludes "Aegis Shield". So one of them should drop depending on logic.
    # Excludes drop the entry that has the exclude rule if the excluded is present?
    # Actually, if Red Dragon excludes Aegis Shield, and Aegis Shield is active, Red Dragon drops itself.
    assert "Aegis Shield" in titles
    assert "Red Dragon" not in titles

@pytest.mark.asyncio
async def test_runPipeline_word_boundary(settings, vault):
    chat = [
        {"name": "user", "mes": "This is a boundless world."} # "boundless" shouldn't trigger "bound" if matchWholeWords=True
    ]

    result = await runPipeline(chat, vault, settings)
    entries = result['finalEntries']
    titles = [e.title for e in entries]

    assert "Word Bound Test" not in titles

    chat2 = [
        {"name": "user", "mes": "He is bound to win."} # "bound" should trigger
    ]
    result2 = await runPipeline(chat2, vault, settings)
    assert "Word Bound Test" in [e.title for e in result2['finalEntries']]


@pytest.mark.asyncio
async def test_runPipeline_word_boundary_multi(settings, vault):
    # Testing multi-word matching behavior
    vault.append(VaultEntry(filename="multi.md", title="Red Dragon Sword", keys=["dragon sword"], priority=100))
    chat = [
        {"name": "user", "mes": "I use the dragon sword."}
    ]
    result = await runPipeline(chat, vault, settings)
    titles = [e.title for e in result['finalEntries']]
    assert "Red Dragon Sword" in titles

    # Multi-word shouldn't match partial boundaries per JS fallback behavior (it uses substring match if it contains space)
    chat2 = [
        {"name": "user", "mes": "I use the xdragon swordx."}
    ]
    result2 = await runPipeline(chat2, vault, settings)
    titles2 = [e.title for e in result2['finalEntries']]
    assert "Red Dragon Sword" in titles2 # Because fallback is substring match for keys with spaces
