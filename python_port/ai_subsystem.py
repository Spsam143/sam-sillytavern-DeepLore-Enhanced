import asyncio
import time
import httpx
import json
import logging
import hashlib
from typing import Any, Dict, List, Optional, Callable, Awaitable, Set

logger = logging.getLogger(__name__)

# Mock State Manager
class StateManager:
    def __init__(self):
        self.chatEpoch = 0
        self.generationLockEpoch = 0

state_manager = StateManager()

def simple_hash(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()

class AiCircuitBreaker:
    def __init__(self, threshold: int = 2, cooldown: float = 30.0, probe_timeout: float = 60.0):
        self.threshold = threshold
        self.cooldown = cooldown
        self.probe_timeout = probe_timeout

        self.is_open = False
        self.failures = 0
        self.opened_at = 0.0

        self.half_open_probe = False
        self.probe_timestamp = 0.0
        self._lock = asyncio.Lock()

    async def record_failure(self) -> None:
        async with self._lock:
            if self.half_open_probe:
                self.half_open_probe = False
                self.probe_timestamp = 0.0

            self.failures += 1
            if self.failures >= self.threshold:
                self.is_open = True
                self.opened_at = time.time()

    async def record_success(self) -> None:
        async with self._lock:
            self.half_open_probe = False
            self.probe_timestamp = 0.0
            self.failures = 0
            self.is_open = False
            self.opened_at = 0.0

    async def release_half_open_probe(self) -> None:
        async with self._lock:
            self.half_open_probe = False
            self.probe_timestamp = 0.0

    async def is_circuit_open(self) -> bool:
        async with self._lock:
            if not self.is_open:
                return False
            if time.time() - self.opened_at > self.cooldown:
                if self.half_open_probe:
                    if time.time() - self.probe_timestamp > self.probe_timeout:
                        return False # stale probe
                    return True # probe in flight, block others
                return False # no probe dispatched
            return True # still in cooldown

    async def try_acquire_half_open_probe(self) -> bool:
        async with self._lock:
            if not self.is_open:
                return True
            if time.time() - self.opened_at > self.cooldown:
                if self.half_open_probe:
                    if time.time() - self.probe_timestamp > self.probe_timeout:
                        pass # stale probe, reset and fall through
                    else:
                        return False # probe already dispatched, block
                self.half_open_probe = True
                self.probe_timestamp = time.time()
                return True
            return False

class CacheEntry:
    def __init__(self, hash_val: str, manifest_hash: str, chat_line_count: int, prefix_hash: str, results: List[Any], matched_entry_set: set, entity_regex_version: int):
        self.hash = hash_val
        self.manifest_hash = manifest_hash
        self.chat_line_count = chat_line_count
        self.prefix_hash = prefix_hash
        self.results = results
        self.matched_entry_set = matched_entry_set
        self.entity_regex_version = entity_regex_version

class AiSearchCache:
    def __init__(self):
        self.cache: Optional[CacheEntry] = None

    def set_cache(self, cache_entry: CacheEntry):
        self.cache = cache_entry

    def get_cache(self) -> Optional[CacheEntry]:
        return self.cache

class CacheManager:
    def __init__(self, ai_search_cache: AiSearchCache):
        self.ai_search_cache = ai_search_cache

    def cache_key(self, vault_source: str, title: str) -> str:
        return f"{vault_source or ''}:{title}"

    def check_cache(self, chat_hash: str, manifest_hash: str, candidate_entries: List[Dict], chat_lines: List[str], ai_search_mode: str, entity_regex_version: int, entity_name_set: Set[str], entity_short_name_regexes: Dict[str, Any]) -> Optional[Dict]:
        cache = self.ai_search_cache.get_cache()
        if not cache:
            return None

        # Tier 1: Exact Match
        if cache.hash == chat_hash and cache.manifest_hash == manifest_hash and cache.chat_line_count > 0:
            return {"results": cache.results, "error": False, "cached": True}

        # Tier 2: Keyword-set stability
        if ai_search_mode != 'ai-only' and cache.manifest_hash == manifest_hash and cache.matched_entry_set and isinstance(candidate_entries, list):
            cached_set = cache.matched_entry_set
            is_subset = True
            for e in candidate_entries:
                k = self.cache_key(e.get('vaultSource'), e.get('title'))
                if k != ':' and k not in cached_set:
                    is_subset = False
                    break
            if is_subset:
                return {"results": cache.results, "error": False, "cached": True}

        # Tier 3: Degenerate sliding-window
        if cache.manifest_hash == manifest_hash and cache.chat_line_count > 0 and len(chat_lines) <= cache.chat_line_count:
            current_content_hash = simple_hash('\n'.join(chat_lines))
            if cache.prefix_hash and current_content_hash != cache.prefix_hash:
                pass # Edit detected
            else:
                return {"results": cache.results, "error": False, "cached": True}

        # Tier 4: Sliding window
        if cache.manifest_hash == manifest_hash and cache.chat_line_count > 0 and len(chat_lines) > cache.chat_line_count and cache.entity_regex_version == entity_regex_version:
            prefix_lines = chat_lines[:cache.chat_line_count]
            prefix_hash = simple_hash('\n'.join(prefix_lines))
            if cache.prefix_hash and prefix_hash != cache.prefix_hash:
                pass # Edit detected
            else:
                new_lines = chat_lines[cache.chat_line_count:]
                new_text = ' '.join(new_lines).lower()

                has_new_entity_mention = False
                for name in entity_name_set:
                    regex = entity_short_name_regexes.get(name)
                    # mock regex test
                    if regex and regex.search(new_text):
                        has_new_entity_mention = True
                        break

                if not has_new_entity_mention:
                    return {"results": cache.results, "error": False, "cached": True}

        return None

class AiApiClient:
    def __init__(self, circuit_breaker: AiCircuitBreaker):
        self.circuit_breaker = circuit_breaker
        self.client = httpx.AsyncClient()

    async def close(self):
        await self.client.aclose()

    async def call_api(self, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        if not await self.circuit_breaker.try_acquire_half_open_probe():
            logger.warning("Circuit breaker is open. Blocking request.")
            return None

        current_epoch = state_manager.chatEpoch

        try:
            response = await self.client.post(url, headers=headers, json=payload, timeout=timeout)

            # Check epoch immediately upon returning
            if current_epoch != state_manager.chatEpoch:
                logger.info("Epoch changed while waiting for API. Discarding result.")
                await self.circuit_breaker.release_half_open_probe()
                return None

            if response.status_code == 429:
                # Rate limit handling - don't trip breaker for pure rate limits generally,
                # but might be implementation specific. Following port specs:
                # "handle rate-limiting (429), timeouts, and malformed JSON responses defensively."
                logger.warning("Rate limited (429).")
                # depending on rules, might record failure or just release probe. Let's record failure to trigger backoff
                await self.circuit_breaker.record_failure()
                return None

            response.raise_for_status()

            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.error("Malformed JSON response.")
                await self.circuit_breaker.record_failure()
                return None

            await self.circuit_breaker.record_success()
            return data

        except httpx.TimeoutException:
            logger.error("Request timed out.")
            await self.circuit_breaker.record_failure()
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error: {e}")
            await self.circuit_breaker.record_failure()
            return None
        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            await self.circuit_breaker.record_failure()
            return None

# Agentic Loop constants
PHASE_SEARCH = "SEARCH"
PHASE_FLAG = "FLAG"
MAX_ITERATIONS = 15

async def search_lore_action(queries: List[str]) -> str:
    # Dummy implementation for tool action
    return "### Lore Entry\nSome lore info"

async def run_agentic_loop(options: Dict[str, Any]) -> None:
    max_searches = options.get('max_searches', 3)
    search_enabled = options.get('search_enabled', True)
    flag_enabled = options.get('flag_enabled', True)
    epoch = options.get('epoch', state_manager.chatEpoch)
    lock_epoch = options.get('lock_epoch', state_manager.generationLockEpoch)

    phase = PHASE_SEARCH
    search_count = 0
    flag_count = 0
    write_done = False

    for iteration in range(MAX_ITERATIONS):
        if epoch != state_manager.chatEpoch or lock_epoch != state_manager.generationLockEpoch:
            logger.info("Agentic loop: epoch mismatch, aborting")
            break

        tools = []
        if phase == PHASE_SEARCH:
            tools.append({"type": "function", "function": {"name": "write"}})
            if search_enabled and search_count < max_searches:
                tools.append({"type": "function", "function": {"name": "search"}})
        elif phase == PHASE_FLAG:
            tools.append({"type": "function", "function": {"name": "write"}})
            if flag_enabled:
                tools.append({"type": "function", "function": {"name": "flag"}})

        # Dummy LLM call simulation
        # Here would be the actual call to the LLM using AiApiClient with the tools
        tool_call_response = None
        # Simulating AI decision
        if phase == PHASE_SEARCH and search_count < max_searches:
            tool_call_response = {"name": "search", "input": {"queries": ["test"]}}
        elif phase == PHASE_SEARCH:
            tool_call_response = {"name": "write", "input": {"content": "prose here"}}
        elif phase == PHASE_FLAG:
            tool_call_response = {"name": "flag", "input": {"title": "gap", "reason": "needed"}}

        if tool_call_response:
            name = tool_call_response["name"]
            if name == "search":
                search_count += 1
                search_result = await search_lore_action(tool_call_response["input"].get("queries", []))
                # Add to results
            elif name == "write":
                if write_done:
                    # Error handling double write
                    pass
                else:
                    write_done = True
                    phase = PHASE_FLAG
            elif name == "flag":
                if phase != PHASE_FLAG or not flag_enabled:
                    # Error handling
                    pass
                else:
                    flag_count += 1
                    break # end loop
        else:
            break
