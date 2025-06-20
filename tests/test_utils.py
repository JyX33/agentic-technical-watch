# ABOUTME: Test utilities providing real implementations instead of mocks
# ABOUTME: Implements test doubles that follow A2A protocol specifications

from typing import Any

from reddit_watcher.a2a_protocol import EventQueue, RequestContext


class FakeEventQueue(EventQueue):
    """Fake implementation of EventQueue with inspection capabilities."""

    def __init__(self):
        super().__init__()
        self.enqueue_event_called = False
        self.enqueue_event_call_count = 0

    async def enqueue_event(self, event: Any) -> None:
        """Track enqueue_event calls."""
        self.enqueue_event_called = True
        self.enqueue_event_call_count += 1
        await super().enqueue_event(event)

    def assert_event_enqueued(self, expected_content: str | None = None) -> None:
        """Assert that an event was enqueued."""
        assert self.enqueue_event_called, "enqueue_event was not called"

        if expected_content is not None:
            events = self.get_events()
            assert len(events) > 0, "No events in queue"

            # Check if any event contains the expected content
            found = False
            for event in events:
                if isinstance(event, dict):
                    content = event.get("content", "")
                    if expected_content in str(content):
                        found = True
                        break

            assert found, f"Expected content '{expected_content}' not found in events"

    def reset(self) -> None:
        """Reset test state."""
        self.clear()
        self.enqueue_event_called = False
        self.enqueue_event_call_count = 0


class FakeRequestContext(RequestContext):
    """Fake implementation of RequestContext."""

    def __init__(self, message: str | None = None, metadata: dict | None = None):
        super().__init__(message, metadata)
        self.accessed = False

    @property
    def message(self):
        """Track message access."""
        self.accessed = True
        return self._message

    @message.setter
    def message(self, value):
        self._message = value


def create_test_context(message: str, **metadata) -> FakeRequestContext:
    """Create a test request context."""
    return FakeRequestContext(message=message, metadata=metadata)


def create_test_event_queue() -> FakeEventQueue:
    """Create a test event queue."""
    return FakeEventQueue()


class AsyncContextManager:
    """Simple async context manager for testing."""

    def __init__(self, return_value=None):
        self.return_value = return_value
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        return False
