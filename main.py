import os
import time

import discord_helper
from nextcloud_api import Nextcloud


# direct: https://cloud.clnp.eu/ocs/v2.php/apps/dav/api/v1/direct?fileId=1190853


def main():
    try:
        sleep_time = int(os.environ.get("SLEEP_TIME", ""))
    except ValueError:
        sleep_time = 10
    # this can be used to debug the bot - will send and exit instead of ignoring the first batch of events
    run_once = bool(os.environ.get("RUN_ONCE"))
    known_activity_keys = [] if run_once else None

    nextcloud = Nextcloud(
        base_url=os.environ.get("NEXTCLOUD_URL"),
        username=os.environ.get("NEXTCLOUD_USERNAME"),
        password=os.environ.get("NEXTCLOUD_PASSWORD")
    )

    while True:
        nextcloud.update_reshare_cache()
        events = [
            event
            for activity in reversed(nextcloud.fetch_activities(limit=3))
            for event in nextcloud.shallow_events_from_activity(activity)
        ]

        if known_activity_keys is None and not run_once:
            known_activity_keys = [event.key for event in events]
            continue

        event_data = [
            nextcloud.load_event_data(event)
            for event
            in events
            if event.key not in known_activity_keys
        ]

        for start_idx in range(0, len(event_data), 10):
            events_to_send = event_data[start_idx:start_idx + 10]
            discord_helper.send_message([
                discord_helper.create_event_embed(event)
                for event
                in events_to_send
            ])
            known_activity_keys.extend(event.key for event in events_to_send)
        if run_once:
            break
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
