from app.beat import beat_schedule


def test_feed_refresh_runs_hourly():
    schedule = beat_schedule["refresh-all-feeds-hourly"]

    assert schedule["task"] == "feeds.refresh_all"
    assert schedule["schedule"] == 3600.0
