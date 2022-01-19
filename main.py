import os
import time

import discord_helper
from nextcloud_api import Nextcloud


class Bot:
    known_activity_keys = []
    should_run = True

    def __init__(self, nextcloud, fetch_limit, action_blacklist=None):
        self.nextcloud = nextcloud
        self.fetch_limit = fetch_limit
        self.action_blacklist = action_blacklist or []

    def run_once(self, init=False):
        # fetch some more on init to avoid weird grouping issues
        events = self.get_events(self.fetch_limit + 10 * init)
        if init:
            self.known_activity_keys.extend(event.key for event in events)
            return
        # this is split into multiple statements to make debugging easier
        events = self.filter_events(events)
        events = self.load_event_data(events)
        self.send_events(events)

    def loop(self, sleep_time):
        self.run_once(init=True)
        while self.should_run:
            self.run_once()
            for _ in range(sleep_time):
                if not self.should_run:
                    return
                time.sleep(1)

    def get_events(self, fetch_limit):
        self.nextcloud.update_reshare_cache()
        return [
            event
            for activity in reversed(self.nextcloud.fetch_activities(limit=fetch_limit))
            for event in reversed(self.nextcloud.shallow_events_from_activity(activity))
            if event.action not in self.action_blacklist
        ]

    def filter_events(self, events):
        return [
            event for event in events
            if event.key not in self.known_activity_keys
        ]

    def load_event_data(self, events):
        return [
            self.nextcloud.load_event_data(event)
            for event
            in events
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


def int_from_env(name, default):
    try:
        return int(os.environ.get(name, ""))
    except ValueError:
        return default


def main():
    sleep_time = int_from_env("SLEEP_TIME", 10)
    fetch_limit = int_from_env("FETCH_LIMIT", 20)
    action_blacklist = os.environ.get("ACTION_BLACKLIST")
    if action_blacklist:
        action_blacklist = action_blacklist.split(",")
    bot = Bot(
        nextcloud=Nextcloud(
            base_url=os.environ.get("NEXTCLOUD_URL"),
            username=os.environ.get("NEXTCLOUD_USERNAME"),
            password=os.environ.get("NEXTCLOUD_PASSWORD")
        ),
        fetch_limit=fetch_limit,
        action_blacklist=action_blacklist
    )
    bot.loop(sleep_time)


if __name__ == "__main__":
    main()
