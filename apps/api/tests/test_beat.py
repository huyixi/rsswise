from app.beat import beat_schedule


def test_feed_refresh_runs_hourly():
    schedule = beat_schedule["refresh-all-feeds-hourly"]

    assert schedule["task"] == "feeds.refresh_all"
    assert schedule["schedule"] == 3600.0


def test_email_digest_schedule_registered() -> None:
    schedule = beat_schedule["email-digest-every-five-minutes"]

    assert schedule["task"] == "email_digest.run_due"
    assert schedule["schedule"] == 300.0
