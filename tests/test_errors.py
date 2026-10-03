from rwa_xray_editor.errors import public_error


def test_hides_urls_paths_and_tokens():
    exc = RuntimeError("GET https://10.0.0.2:3005/api/x failed: /app/geoip/geosite.dat missing token=abc123")
    text = public_error(exc)
    assert "10.0.0.2" not in text
    assert "/app/geoip" not in text
    assert "abc123" not in text
    assert "<url>" in text and "<path>" in text and "<hidden>" in text


def test_keeps_meaning_and_limits_length():
    assert "невалидный JSON" in public_error(ValueError("невалидный JSON: line 3"))
    long = public_error(RuntimeError("x" * 1000))
    assert len(long) <= 300 and long.endswith("…")


def test_empty_message_falls_back_to_class_name():
    assert public_error(KeyError()) == "KeyError"
