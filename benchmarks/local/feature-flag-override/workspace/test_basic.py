from flags.rollout import FlagSet


def test_zero_percent_is_off_for_everyone():
    fs = FlagSet({"beta": {"percent": 0}})
    assert not any(fs.is_enabled("beta", f"user{i}") for i in range(300))


def test_false_override_wins_over_the_rollout():
    fs = FlagSet({"beta": {"percent": 100, "overrides": {"vip": False}}})
    assert fs.is_enabled("beta", "vip") is False
