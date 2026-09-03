"""Tests for runtime context behavior."""

from trademonitor.core.context import RuntimeContexts


def test_empty_runtime_contexts_have_canonical_names() -> None:
    contexts = RuntimeContexts.empty()

    assert set(contexts.contexts) == {
        "broker",
        "market",
        "trade",
        "position",
        "risk",
        "decision",
        "health",
    }


def test_context_patch_increments_version() -> None:
    context = RuntimeContexts.empty().get("market")

    context.patch({"feed": "HEALTHY"})
    context.patch({"last_tick": "10:15:00"})

    assert context.version == 2
    assert context.data == {"feed": "HEALTHY", "last_tick": "10:15:00"}
