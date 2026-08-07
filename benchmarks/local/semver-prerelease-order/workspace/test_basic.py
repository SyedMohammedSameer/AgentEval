from semver.compare import compare


def test_patch_order():
    assert compare("1.0.1", "1.0.0") == 1


def test_prerelease_is_older_than_release():
    assert compare("1.0.0-alpha", "1.0.0") == -1
