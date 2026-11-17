import json

from conftest import load_extension

tool = load_extension("tools/text_statistik.py")


def test_counts_words_sentences_and_reading_time():
    text = "Das ist ein Satz. Und noch einer! Wirklich?"
    result = json.loads(tool.Tools().text_statistik(text))
    assert result == {
        "woerter": 8,
        "zeichen": len(text),
        "zeichen_ohne_leerzeichen": len(text.replace(" ", "")),
        "saetze": 3,
        "lesezeit_minuten": 1,
    }


def test_umlauts_and_hyphenated_words_count_once():
    assert tool.statistik("Größenänderung ist E-Mail-fähig")["woerter"] == 3


def test_reading_time_uses_valve():
    tools = tool.Tools()
    tools.valves.woerter_pro_minute = 2
    assert json.loads(tools.text_statistik("eins zwei drei"))["lesezeit_minuten"] == 2


def test_empty_text():
    assert tool.statistik("")["woerter"] == 0
    assert tool.statistik("")["lesezeit_minuten"] == 0
