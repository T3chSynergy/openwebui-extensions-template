import asyncio

from conftest import load_extension

action = load_extension("functions/actions/textstatistik_anzeigen.py")


def body(content, message_id="a1"):
    return {
        "id": message_id,
        "messages": [
            {"id": "u1", "role": "user", "content": "Schreib etwas"},
            {"id": message_id, "role": "assistant", "content": content},
        ],
    }


def test_embeds_card_for_clicked_message(emitter):
    asyncio.run(action.Action().action(body("Eins zwei drei. Vier."), __event_emitter__=emitter))
    [event] = emitter.of_type("embeds")
    assert event["data"]["replace"] is True
    card = event["data"]["embeds"][0]
    assert "<span class='zahl'>4</span><span class='label'>Wörter</span>" in card
    assert "iframe:height" in card


def test_uses_clicked_message_not_last():
    data = body("erste Antwort", "a1")
    data["messages"].append({"id": "a2", "role": "assistant", "content": "zweite"})
    assert action.message_text(data) == "erste Antwort"


def test_escapes_html():
    card = action.build_card({"woerter": "<b>", "zeichen": 1, "saetze": 1, "lesezeit_minuten": 1})
    assert "<b>" not in card and "&lt;b&gt;" in card


def test_notifies_on_empty_message(emitter):
    asyncio.run(action.Action().action(body("   "), __event_emitter__=emitter))
    assert [e["type"] for e in emitter.events] == ["notification"]
