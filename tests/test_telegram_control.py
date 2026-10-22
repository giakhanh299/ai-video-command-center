from backend.telegram_control import control_chat_id


def test_current_group_used(monkeypatch):
    monkeypatch.delenv('TELEGRAM_CONTROL_CHAT_ID', raising=False)
    assert control_chat_id({'-5273638075', '-1004439918026'}) == '-5273638075'


def test_explicit_group_must_be_allowed(monkeypatch):
    monkeypatch.setenv('TELEGRAM_CONTROL_CHAT_ID', '-1')
    assert control_chat_id({'-5273638075'}) is None
    assert control_chat_id({'-1'}) == '-1'


def test_no_arbitrary_destination(monkeypatch):
    monkeypatch.delenv('TELEGRAM_CONTROL_CHAT_ID', raising=False)
    assert control_chat_id({'-1004439918026'}) is None
