from events.bus import EventBus


def test_self_unsubscribe_does_not_skip_others():
    bus = EventBus()
    seen = []

    def once(event):
        seen.append("once")
        bus.unsubscribe(once)
        return "once"

    bus.subscribe(once, priority=5)
    bus.subscribe(lambda e: seen.append("after") or "after", priority=1)

    assert bus.publish("x") == ["once", "after"]
    assert seen == ["once", "after"]
    # Second publish sees only the surviving handler.
    seen.clear()
    assert bus.publish("y") == ["after"]


def test_three_equal_priorities_in_order():
    bus = EventBus()
    for name in ("a", "b", "c"):
        bus.subscribe(lambda e, n=name: n, priority=0)
    assert bus.publish("x") == ["a", "b", "c"]


def test_mixed_priorities_stable_within_level():
    bus = EventBus()
    bus.subscribe(lambda e: "lo1", priority=0)
    bus.subscribe(lambda e: "hi1", priority=9)
    bus.subscribe(lambda e: "lo2", priority=0)
    bus.subscribe(lambda e: "hi2", priority=9)
    assert bus.publish("x") == ["hi1", "hi2", "lo1", "lo2"]


def test_unsubscribe_unknown_handler_is_noop():
    bus = EventBus()
    bus.subscribe(lambda e: "a")
    bus.unsubscribe(lambda e: "other")
    assert bus.publish("x") == ["a"]


def test_publish_with_no_handlers():
    assert EventBus().publish("x") == []
