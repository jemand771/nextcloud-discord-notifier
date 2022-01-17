import os
import time

import discord_helper
from nextcloud_api import Nextcloud


class Bot:
    known_activity_keys = []
    should_run = True

    def __init__(self, nextcloud):
        self.nextcloud = nextcloud

    def run_once(self, init=False):
        events = self.get_events()
        if init:
            self.known_activity_keys.extend(event.key for event in events)
            return
        self.send_events(self.load_event_data(events))

    def loop(self, sleep_time):
        self.run_once(init=True)
        while self.should_run:
            self.run_once()
            for _ in range(sleep_time):
                if not self.should_run:
                    return
                time.sleep(1)

    def get_events(self):
        self.nextcloud.update_reshare_cache()
        return [
            event
            for activity in reversed(self.nextcloud.fetch_activities(limit=3))
            for event in reversed(self.nextcloud.shallow_events_from_activity(activity))
        ]

    def load_event_data(self, events):
        return [
            self.nextcloud.load_event_data(event)
            for event
            in events
            if event.key not in self.known_activity_keys
        ]

    def send_events(self, events):
        for start_idx in range(0, len(events), 10):
            events_to_send = events[start_idx:start_idx + 10]
            discord_helper.send_message(
                [
                    discord_helper.create_event_embed(event)
                    for event
                    in events_to_send
                ]
            )
            self.known_activity_keys.extend(event.key for event in events_to_send)

    def signal_handler(self):
        self.should_run = False


def main():
    try:
        sleep_time = int(os.environ.get("SLEEP_TIME", ""))
    except ValueError:
        sleep_time = 10
    bot = Bot(
        nextcloud=Nextcloud(
            base_url=os.environ.get("NEXTCLOUD_URL"),
            username=os.environ.get("NEXTCLOUD_USERNAME"),
            password=os.environ.get("NEXTCLOUD_PASSWORD")
        )
    )
    bot.loop(sleep_time)


if __name__ == "__main__":
    main()
