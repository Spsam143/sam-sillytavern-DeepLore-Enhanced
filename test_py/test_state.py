import pytest
import asyncio
from src_py.state import StateManager, EpochGuard, EpochChangedError, epoch_guarded

@pytest.fixture
def state_manager():
    # Since QObject requires a QCoreApplication instance to use Signals/Slots
    # if we were testing emit in thread. We'll use pytest-qt's qtbot if needed,
    # but for simple property/epoch tests, we just instantiate it.
    return StateManager()

def test_epoch_increment(state_manager):
    assert state_manager.chatEpoch == 0
    assert state_manager.lockEpoch == 0

    state_manager.increment_chat_epoch()
    assert state_manager.chatEpoch == 1
    assert state_manager.lockEpoch == 0

    state_manager.increment_lock_epoch()
    assert state_manager.chatEpoch == 1
    assert state_manager.lockEpoch == 1

def test_epoch_guard_success(state_manager):
    guard = EpochGuard(state_manager)
    # Shouldn't raise
    guard.check()

def test_epoch_guard_failure(state_manager):
    guard = EpochGuard(state_manager)

    state_manager.increment_chat_epoch()

    with pytest.raises(EpochChangedError, match="chatEpoch changed"):
        guard.check()

@pytest.mark.asyncio
async def test_epoch_guarded_decorator_success(state_manager):

    @epoch_guarded(state_manager)
    async def async_task():
        await asyncio.sleep(0.01)
        return "success"

    result = await async_task()
    assert result == "success"

@pytest.mark.asyncio
async def test_epoch_guarded_decorator_failure_chat(state_manager):

    @epoch_guarded(state_manager)
    async def async_task():
        await asyncio.sleep(0.01)
        state_manager.increment_chat_epoch()
        return "success"

    with pytest.raises(EpochChangedError, match="chatEpoch changed"):
        await async_task()

@pytest.mark.asyncio
async def test_epoch_guarded_decorator_failure_lock(state_manager):

    @epoch_guarded(state_manager)
    async def async_task():
        await asyncio.sleep(0.01)
        state_manager.increment_lock_epoch()
        return "success"

    with pytest.raises(EpochChangedError, match="lockEpoch changed"):
        await async_task()

@pytest.mark.asyncio
async def test_epoch_guarded_decorator_ignore_lock(state_manager):

    @epoch_guarded(state_manager, check_lock=False)
    async def async_task():
        await asyncio.sleep(0.01)
        # We mutate lockEpoch but decorator ignores it
        state_manager.increment_lock_epoch()
        return "success"

    result = await async_task()
    assert result == "success"

def test_signals_emit(qtbot, state_manager):
    """Test that PySide6 signals emit correctly using pytest-qt."""
    with qtbot.waitSignal(state_manager.indexUpdated, timeout=1000):
        state_manager.notify_index_updated()

    with qtbot.waitSignal(state_manager.generationLockChanged, timeout=1000):
        state_manager.notify_generation_lock_changed()

    # verify lock epoch increments on generation lock change
    assert state_manager.lockEpoch == 1


@pytest.mark.asyncio
async def test_epoch_guarded_concurrent_switching(state_manager):
    """
    Test simulating a user context switch (switching chats) while
    an AI request is yielding.
    """

    @epoch_guarded(state_manager)
    async def simulate_ai_call():
        # Yield to simulate network delay
        await asyncio.sleep(0.05)
        return "ai_result"

    async def run_call_and_switch():
        # Start AI call
        task = asyncio.create_task(simulate_ai_call())

        # While it's in flight, the user switches chat
        await asyncio.sleep(0.01)
        state_manager.increment_chat_epoch()

        # Await the result, which should now raise
        await task

    with pytest.raises(EpochChangedError, match="chatEpoch changed"):
        await run_call_and_switch()

@pytest.mark.asyncio
async def test_epoch_guarded_concurrent_switching_lock(state_manager):
    """
    Test simulating a user context switch (generation lock unlocked) while
    an AI request is yielding.
    """

    @epoch_guarded(state_manager)
    async def simulate_ai_call():
        # Yield to simulate network delay
        await asyncio.sleep(0.05)
        return "ai_result"

    async def run_call_and_switch():
        # Start AI call
        task = asyncio.create_task(simulate_ai_call())

        # While it's in flight, generation lock unlocks
        await asyncio.sleep(0.01)
        state_manager.increment_lock_epoch()

        # Await the result, which should now raise
        await task

    with pytest.raises(EpochChangedError, match="lockEpoch changed"):
        await run_call_and_switch()
