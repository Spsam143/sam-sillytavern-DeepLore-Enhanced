import pytest
import asyncio
from ai_subsystem import AiCircuitBreaker, StateManager, state_manager, CacheManager, AiSearchCache, CacheEntry, simple_hash

@pytest.mark.asyncio
async def test_circuit_breaker():
    cb = AiCircuitBreaker(threshold=2, cooldown=0.1)

    assert not await cb.is_circuit_open()

    await cb.record_failure()
    assert not await cb.is_circuit_open()

    await cb.record_failure()
    assert await cb.is_circuit_open()

    await asyncio.sleep(0.2)
    # Now it's half open, let's try to acquire
    assert await cb.try_acquire_half_open_probe()
    assert await cb.is_circuit_open() # still "open" for others

    await cb.record_success()
    assert not await cb.is_circuit_open()

def test_cache_tier1():
    cache = AiSearchCache()
    cm = CacheManager(cache)

    entry = CacheEntry(
        hash_val="hash1",
        manifest_hash="manhash1",
        chat_line_count=5,
        prefix_hash="prefhash1",
        results=[{"title": "test"}],
        matched_entry_set=set(),
        entity_regex_version=1
    )
    cache.set_cache(entry)

    res = cm.check_cache(
        chat_hash="hash1",
        manifest_hash="manhash1",
        candidate_entries=[],
        chat_lines=["a"] * 5,
        ai_search_mode="normal",
        entity_regex_version=1,
        entity_name_set=set(),
        entity_short_name_regexes={}
    )

    assert res is not None
    assert res["cached"] is True
