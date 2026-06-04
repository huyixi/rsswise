beat_schedule = {
    "refresh-all-feeds-hourly": {
        "task": "feeds.refresh_all",
        "schedule": 3600.0,
    },
    "email-digest-every-five-minutes": {
        "task": "email_digest.run_due",
        "schedule": 300.0,
    }
}
