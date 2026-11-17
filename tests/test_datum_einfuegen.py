from datetime import datetime
from zoneinfo import ZoneInfo

from conftest import load_extension

filter_module = load_extension("functions/filters/datum_einfuegen.py")


def test_appends_date_to_existing_system_prompt():
    body = {"messages": [{"role": "system", "content": "Du bist hilfreich."}, {"role": "user", "content": "Hallo"}]}
    result = filter_module.Filter().inlet(body)
    system = result["messages"][0]["content"]
    assert system.startswith("Du bist hilfreich.\n\nAktuelles Datum: ")
    assert len(result["messages"]) == 2


def test_inserts_system_message_when_missing():
    result = filter_module.Filter().inlet({"messages": [{"role": "user", "content": "Hallo"}]})
    assert result["messages"][0]["role"] == "system"
    assert result["messages"][0]["content"].startswith("Aktuelles Datum: ")


def test_does_not_add_date_twice():
    flt = filter_module.Filter()
    body = flt.inlet({"messages": [{"role": "user", "content": "Hallo"}]})
    body = flt.inlet(body)
    assert body["messages"][0]["content"].count("Aktuelles Datum:") == 1


def test_formats_german_date():
    moment = datetime(2026, 11, 17, 9, 5, tzinfo=ZoneInfo("Europe/Berlin"))
    assert filter_module.datumszeile(moment) == "Aktuelles Datum: Dienstag, 17.11.2026, 09:05 Uhr (CET)"


def test_unknown_timezone_falls_back_to_utc():
    flt = filter_module.Filter()
    flt.valves.zeitzone = "Mond/Krater"
    assert flt._jetzt().tzname() == "UTC"
