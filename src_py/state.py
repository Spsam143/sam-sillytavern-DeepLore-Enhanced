from typing import Callable, Coroutine, Any, Optional
import functools
import asyncio
from PySide6.QtCore import QObject, Signal, Slot

class EpochChangedError(Exception):
    """Raised when an epoch changes during an async operation, preventing a zombie write."""
    pass

class StateManager(QObject):
    """
    Robust state manager inheriting from PySide6 QObject.
    Uses Signals and Slots for thread-safe observation.
    Implements Epoch tracking for concurrency control.
    """
    # Signals for replacing JS CustomEvent observer pattern
    indexUpdated = Signal()
    aiStatsUpdated = Signal()
    circuitStateChanged = Signal()
    pipelineComplete = Signal()
    injectionSourcesReady = Signal()
    gatingChanged = Signal()
    pinBlockChanged = Signal()
    generationLockChanged = Signal()
    fieldDefinitionsUpdated = Signal()
    indexingChanged = Signal()
    loreGapsChanged = Signal()
    chatInjectionCountsUpdated = Signal()
    pipelineTraceUpdated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chatEpoch: int = 0
        self._lockEpoch: int = 0

    @property
    def chatEpoch(self) -> int:
        return self._chatEpoch

    @property
    def lockEpoch(self) -> int:
        return self._lockEpoch

    def increment_chat_epoch(self) -> None:
        """Increment the chat epoch, typically called when the active chat changes."""
        self._chatEpoch += 1

    def increment_lock_epoch(self) -> None:
        """Increment the lock epoch, typically called when generation locks/unlocks."""
        self._lockEpoch += 1

    def notify_index_updated(self) -> None:
        self.indexUpdated.emit()

    def notify_ai_stats_updated(self) -> None:
        self.aiStatsUpdated.emit()

    def notify_circuit_state_changed(self) -> None:
        self.circuitStateChanged.emit()

    def notify_pipeline_complete(self) -> None:
        self.pipelineComplete.emit()

    def notify_injection_sources_ready(self) -> None:
        self.injectionSourcesReady.emit()

    def notify_gating_changed(self) -> None:
        self.gatingChanged.emit()

    def notify_pin_block_changed(self) -> None:
        self.pinBlockChanged.emit()

    def notify_generation_lock_changed(self) -> None:
        self.increment_lock_epoch()
        self.generationLockChanged.emit()

    def notify_field_definitions_updated(self) -> None:
        self.fieldDefinitionsUpdated.emit()

    def notify_indexing_changed(self) -> None:
        self.indexingChanged.emit()

    def notify_lore_gaps_changed(self) -> None:
        self.loreGapsChanged.emit()

    def notify_chat_injection_counts_updated(self) -> None:
        self.chatInjectionCountsUpdated.emit()

    def notify_pipeline_trace_updated(self) -> None:
        self.pipelineTraceUpdated.emit()


class EpochGuard:
    """
    Context manager to verify that the Epoch hasn't changed.
    """
    def __init__(self, state_manager: StateManager, check_chat: bool = True, check_lock: bool = True):
        self.sm = state_manager
        self.check_chat = check_chat
        self.check_lock = check_lock
        self.initial_chat_epoch = state_manager.chatEpoch
        self.initial_lock_epoch = state_manager.lockEpoch

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def check(self):
        """Manually verify that epochs have not changed."""
        if self.check_chat and self.sm.chatEpoch != self.initial_chat_epoch:
            raise EpochChangedError("chatEpoch changed during async operation.")
        if self.check_lock and self.sm.lockEpoch != self.initial_lock_epoch:
            raise EpochChangedError("lockEpoch changed during async operation.")

def epoch_guarded(state_manager: StateManager, check_chat: bool = True, check_lock: bool = True):
    """
    Decorator that captures epochs before executing an async function
    and verifies they haven't changed upon completion before returning.
    Useful for ensuring 'zombie writes' don't happen if the user switches context
    while an async call (like an AI request) is pending.
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            initial_chat_epoch = state_manager.chatEpoch
            initial_lock_epoch = state_manager.lockEpoch

            result = await func(*args, **kwargs)

            if check_chat and state_manager.chatEpoch != initial_chat_epoch:
                raise EpochChangedError("chatEpoch changed during async operation.")
            if check_lock and state_manager.lockEpoch != initial_lock_epoch:
                raise EpochChangedError("lockEpoch changed during async operation.")

            return result
        return wrapper
    return decorator
