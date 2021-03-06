import os
import time
import unittest
from datetime import datetime
from tempfile import TemporaryDirectory

# NOTE to use this with docker desktop, enable the exposing option there and set
#      DOCKER_HOST=http://localhost:2375 in your testing env
import docker
import requests
import webdav3.client

import nextcloud_api
from .common import expand_single, flatten


class DavClient:

    def __init__(self, url, username, password):
        self.client = webdav3.client.Client(
            {
                "webdav_hostname": f"{url}/remote.php/dav/files/{username}/",
                "webdav_login": username,
                "webdav_password": password
            }
        )

    def upload_file(self, local_path, remote_path):
        self.client.upload_sync(local_path=local_path, remote_path=remote_path)

    def make_txt_file(self, remote_path, content="asdasd"):
        with TemporaryDirectory() as temp_dir:
            with open(file_path := f"{temp_dir}/file.txt", "w") as f:
                f.write(content)
            self.upload_file(local_path=file_path, remote_path=remote_path)


class NextcloudTest(unittest.TestCase):
    ADMIN_USER = "admin"
    ADMIN_PASS = "admin"
    NEXTCLOUD_CONFIG = {
        "skeletondirectory": ""
    }
    # magic number: nextcloud groups events into groups of up to 5
    EVENTS_PER_ACTIVITY = 5

    def setUp(self):
        self.config_dir = TemporaryDirectory()
        os.chmod(self.config_dir.name, 0o777)
        self.prepare_config_file(f"{self.config_dir.name}/custom.config.php")

        self.docker_client = docker.from_env()
        self.docker_container = self.docker_client.containers.run(
            "nextcloud",
            auto_remove=True,
            detach=True,
            environment={
                "SQLITE_DATABASE": "nextcloud.db",
                "NEXTCLOUD_ADMIN_USER": self.ADMIN_USER,
                "NEXTCLOUD_ADMIN_PASSWORD": self.ADMIN_PASS,
            },
            ports={
                80: 0  # auto-bind
            },
            volumes={
                self.config_dir.name: {"bind": "/var/www/html/config/"}
            }
        )
        self.docker_container.reload()
        host_port = self.docker_container.ports['80/tcp'][0]["HostPort"]
        nextcloud_url = f"http://localhost:{host_port}"
        for _ in range(20):
            try:
                r = requests.get(nextcloud_url)
                assert r.status_code == 200, f"nextcloud not OK - {r.status_code}"
                break
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
        else:
            self.fail("failed to launch a healthy nextcloud container")
        nextcloud_params = (nextcloud_url, self.ADMIN_USER, self.ADMIN_PASS)
        self.nextcloud = nextcloud_api.Nextcloud(*nextcloud_params)
        self.dav = DavClient(*nextcloud_params)

    def prepare_config_file(self, path):
        with open(path, "w") as f:
            f.write("<?php\n$CONFIG = array(\n")
            for key, value in self.NEXTCLOUD_CONFIG.items():
                if isinstance(value, str):
                    value = f"'{value}'"
                f.write(f"'{key}' => {value},\n")
            f.write(");\n")

    def tearDown(self):
        self.docker_container.stop()
        self.config_dir.cleanup()
        self.docker_client.close()

    def get_events_shallow(self, limit=100):
        return [
            event
            for activity in self.nextcloud.fetch_activities(limit=limit)
            for event in self.nextcloud.shallow_events_from_activity(activity)
        ]

    def get_events(self, limit=100):
        return [
            self.nextcloud.load_event_data(event)
            for event in self.get_events_shallow(limit=limit)
        ]

    def test_no_activity(self):
        activities = self.nextcloud.fetch_activities(limit=3)
        self.assertIsInstance(activities, list)
        self.assertEqual(len(activities), 0)

    def test_activity_event_grouping(self):
        for i in range(self.EVENTS_PER_ACTIVITY + 1):
            self.dav.make_txt_file(f"test-{i}.txt")
        events = self.get_events_shallow(limit=1)
        self.assertEqual(len(events), self.EVENTS_PER_ACTIVITY)

    @expand_single(range(3))
    def test_simple_event_groups(self, num_activities):
        for i in range(self.EVENTS_PER_ACTIVITY * num_activities):
            self.dav.make_txt_file(f"test-{i}.txt")
        activities = self.nextcloud.fetch_activities(limit=2 * num_activities)
        self.assertEqual(len(activities), num_activities)

    @expand_single(range(0, 20, 4))
    def test_simple_event_count(self, num_events):
        for i in range(num_events):
            self.dav.make_txt_file(f"test-{i}.txt")
        events = self.get_events_shallow(limit=2 * self.EVENTS_PER_ACTIVITY * num_events)
        self.assertEqual(len(events), num_events)

    def test_direct_download(self):
        self.dav.make_txt_file("file.txt", content=(file_content := "hellowo"))
        event = self.get_events_shallow()[0]
        url = self.nextcloud.create_direct_link(event.file_id)
        r = requests.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, file_content)

    def test_field_resolution(self):
        self.dav.make_txt_file(file_name := "file.txt")
        from detail_resolvers import DetailResolver

        class TestResolver(DetailResolver):
            display_name = "file name"

            def resolve_detail(self, file_path):
                return file_path.rsplit("/", 1)[-1]

        self.nextcloud.detail_resolvers = [TestResolver]
        event = self.get_events_shallow()[0]
        fields = self.nextcloud.load_event_data(event).additional_info
        self.assertEqual(
            fields, [{
                "name": TestResolver.display_name,
                "value": file_name,
                "inline": TestResolver.is_inline
            }]
        )

    def test_event_timestamp(self):
        self.dav.make_txt_file("file.txt")
        event = self.get_events_shallow()[0]
        event_time = datetime.fromisoformat(event.iso_timestamp)
        delay = datetime.now().astimezone() - event_time
        self.assertGreater(delay.total_seconds(), 0)
        self.assertLess(delay.total_seconds(), 10)
