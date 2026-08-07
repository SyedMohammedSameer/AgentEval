from flags.hashing import bucket_of
from flags.rollout import FlagSet


def test_true_override_wins_over_a_zero_rollout():
    fs = FlagSet({"beta": {"percent": 0, "overrides": {"vip": True}}})
    assert fs.is_enabled("beta", "vip") is True


def test_override_does_not_affect_other_users():
    fs = FlagSet({"beta": {"percent": 100, "overrides": {"vip": False}}})
    assert fs.is_enabled("beta", "someone-else") is True


def test_hundred_percent_is_on_for_everyone():
    fs = FlagSet({"beta": {"percent": 100}})
    assert all(fs.is_enabled("beta", f"user{i}") for i in range(100))


def test_bucketing_is_stable_across_calls():
    fs = FlagSet({"beta": {"percent": 50}})
    first = [fs.is_enabled("beta", f"u{i}") for i in range(100)]
    second = [fs.is_enabled("beta", f"u{i}") for i in range(100)]
    assert first == second


def test_buckets_stay_in_range():
    assert all(0 <= bucket_of("f", f"u{i}") < 100 for i in range(200))


def test_flags_bucket_independently():
    a = [bucket_of("alpha", f"u{i}") for i in range(50)]
    b = [bucket_of("beta", f"u{i}") for i in range(50)]
    assert a != b


def test_rollout_share_tracks_the_percentage():
    fs = FlagSet({"beta": {"percent": 30}})
    on = sum(fs.is_enabled("beta", f"u{i}") for i in range(2000))
    assert 500 <= on <= 700


def test_unknown_flag_is_off():
    assert FlagSet({}).is_enabled("nope", "u") is False
