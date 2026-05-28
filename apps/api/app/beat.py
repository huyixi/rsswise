beat_schedule = {
    "refresh-all-feeds-hourly": {
        "task": "feeds.refresh_all",
        "schedule": 3600.0,
    }
}
