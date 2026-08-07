from events.bus import EventBus


def test_priority_order():
    bus = EventBus()
    bus.subscribe(lambda e: "low", priority=0)
    bus.subscribe(lambda e: "high", priority=10)
    assert bus.publish("x") == ["high", "low"]


def test_equal_priority_keeps_registration_order():
    bus = EventBus()
    bus.subscribe(lambda e: "first", priority=0)
    bus.subscribe(lambda e: "second", priority=0)
    assert bus.publish("x") == ["first", "second"]
