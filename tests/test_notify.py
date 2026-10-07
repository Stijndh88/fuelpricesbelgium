import json

from fuelprices import notify


def advice(diesel="wait", e10="no_difference"):
    return {
        "advice": [
            {
                "product": "diesel_b7",
                "label": "Diesel B7",
                "action": diesel,
                "headline": diesel.title(),
                "reason": "Reason d.",
            },
            {
                "product": "e10",
                "label": "E10",
                "action": e10,
                "headline": e10.title(),
                "reason": "Reason e.",
            },
        ]
    }


def write(path, data):
    path.write_text(json.dumps(data))
    return path


def test_changed_detects_action_change_and_first_run():
    assert not notify.changed(advice(), advice())
    assert notify.changed(advice(diesel="fill_up_today"), advice())
    assert notify.changed(advice(), None)


def test_message_has_both_products():
    title, body = notify.build_message(advice())
    assert "Diesel B7" in title and "E10" in title
    assert body.splitlines() == ["Diesel B7: Reason d.", "E10: Reason e."]


def test_unchanged_sends_nothing(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "send", lambda *a: sent.append(a))
    cur, prev = write(tmp_path / "c.json", advice()), write(tmp_path / "p.json", advice())
    assert "unchanged" in notify.run(cur, prev, "t", False, False)
    assert not sent


def test_change_sends_and_daily_forces(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "send", lambda *a: sent.append(a))
    cur = write(tmp_path / "c.json", advice(diesel="fill_up_today"))
    prev = write(tmp_path / "p.json", advice())
    assert notify.run(cur, prev, "secret", False, False) == "Notification sent."
    same = write(tmp_path / "s.json", advice())
    notify.run(same, prev, "secret", True, False)
    assert len(sent) == 2


def test_missing_topic_skips_and_dry_run_prints(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "send", lambda *a: 1 / 0)
    cur = write(tmp_path / "c.json", advice())
    assert "not set" in notify.run(cur, None, "", False, False)
    assert "Dry run" in notify.run(cur, None, "", False, True)


def test_message_is_dutch_only_by_default():
    data = {
        "advice": [
            {
                "product": "diesel_b7",
                "label": "Diesel B7",
                "action": "wait",
                "headline": "Wait",
                "reason": "English text",
                "reason_code": "wait_published",
                "reason_params": {
                    "day": "2026-10-07",
                    "cents": 4.0,
                    "today": 2.432,
                    "tomorrow": 2.392,
                },
            }
        ]
    }
    title, body = notify.build_message(data)
    assert title == "Tankadvies: Diesel B7: Wacht"
    assert "\n\n" not in body
    assert "Wacht tot morgen (wo 07/10): de maximumprijs daalt 4.0 cent/L" in body
    _, both = notify.build_message(data, ("nl", "en"))
    dutch, english = both.split("\n\n")
    assert "Wait until tomorrow (Wed 07/10): the maximum price drops 4.0 cent/L" in english
    _, only_english = notify.build_message(data, ("en",))
    assert "\n\n" not in only_english
