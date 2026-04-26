from scout.utils.url_norm import canonicalize, url_hash


def test_canonicalize_lowercases_host_and_drops_www():
    assert canonicalize("https://WWW.Example.COM/Path") == "https://example.com/Path"


def test_canonicalize_drops_default_ports():
    assert canonicalize("http://example.com:80/x") == "http://example.com/x"
    assert canonicalize("https://example.com:443/x") == "https://example.com/x"


def test_canonicalize_keeps_nondefault_ports():
    assert canonicalize("https://example.com:8443/x") == "https://example.com:8443/x"


def test_canonicalize_strips_tracking():
    canon = canonicalize("https://example.com/x?utm_source=foo&utm_medium=bar&q=1&ref=baz")
    assert canon == "https://example.com/x?q=1"


def test_canonicalize_strips_fragment():
    assert canonicalize("https://example.com/x#section") == "https://example.com/x"


def test_canonicalize_treats_relative_url_as_opaque():
    # Defensive: don't crash on user-typed garbage.
    assert canonicalize("/path/only") == "/path/only"


def test_url_hash_stable_after_tracking_param_change():
    a = url_hash("https://example.com/x?utm_source=a&q=1")
    b = url_hash("https://example.com/x?q=1&utm_medium=b")
    assert a == b


def test_url_hash_distinguishes_different_paths():
    assert url_hash("https://example.com/a") != url_hash("https://example.com/b")
