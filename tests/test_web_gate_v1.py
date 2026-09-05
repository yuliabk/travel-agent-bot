from src.api.web_gate_v1 import webform_gate_decision


def test_unprotected_path_is_not_gated():
    assert webform_gate_decision("/health", None, enabled=False, expected_token="") == (None, None)


def test_web_draft_is_disabled_fail_closed():
    status, message = webform_gate_decision(
        "/v1/web/draft",
        "Bearer anything",
        enabled=False,
        expected_token="secret",
    )
    assert status == 503
    assert "disabled" in message


def test_web_draft_requires_configured_token():
    status, _ = webform_gate_decision(
        "/v1/web/draft",
        "Bearer anything",
        enabled=True,
        expected_token="",
    )
    assert status == 503


def test_web_draft_rejects_wrong_token():
    status, _ = webform_gate_decision(
        "/v1/web/draft",
        "Bearer wrong",
        enabled=True,
        expected_token="correct",
    )
    assert status == 403


def test_web_draft_allows_matching_token():
    assert webform_gate_decision(
        "/v1/web/draft",
        "Bearer correct",
        enabled=True,
        expected_token="correct",
    ) == (None, None)


def test_normalize_endpoint_uses_same_gate():
    assert webform_gate_decision(
        "/v1/intake/abacus/normalize",
        "Bearer correct",
        enabled=True,
        expected_token="correct",
    ) == (None, None)
