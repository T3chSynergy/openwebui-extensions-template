from conftest import load_extension

pipe = load_extension("functions/pipes/echo.py")


def test_echoes_messages_with_roles():
    answer = pipe.Pipe().pipe({"messages": [{"role": "system", "content": "S"}, {"role": "user", "content": "Hallo"}]})
    assert "### system\n\nS" in answer
    assert "### user\n\nHallo" in answer


def test_truncates_long_messages():
    p = pipe.Pipe()
    p.valves.max_zeichen = 5
    answer = p.pipe({"messages": [{"role": "user", "content": "0123456789"}]})
    assert "01234 … (5 Zeichen gekürzt)" in answer


def test_handles_list_content_and_empty_body():
    answer = pipe.Pipe().pipe({"messages": [{"role": "user", "content": [{"type": "text", "text": "Bild?"}]}]})
    assert "Bild?" in answer
    assert "(keine Nachrichten)" in pipe.Pipe().pipe({})
