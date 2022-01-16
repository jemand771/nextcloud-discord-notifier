import time
import unittest
from tempfile import TemporaryDirectory

# NOTE to use this with docker desktop, enable the exposing option there and set
#      DOCKER_HOST=http://localhost:2375 in your testing env
import docker
import requests

import nextcloud_api


class NextcloudTest(unittest.TestCase):
    ADMIN_USER = "admin"
    ADMIN_PASS = "admin"
    NEXTCLOUD_CONFIG = {
        "skeletondirectory": ""
    }

    def setUp(self):
        self.config_dir = TemporaryDirectory()
        self.prepare_config_file(f"{self.config_dir.name}/custom.config.php")

        client = docker.from_env()
        self.docker_container = client.containers.run(
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
                assert requests.get(nextcloud_url).status_code == 200
                break
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
        else:
            self.fail("failed to launch a healthy nextcloud container")
        self.nextcloud = nextcloud_api.Nextcloud(nextcloud_url, self.ADMIN_USER, self.ADMIN_PASS)

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

    def test_no_activity(self):
        activities = self.nextcloud.fetch_activities(limit=3)
        self.assertIsInstance(activities, list)
        self.assertEqual(len(activities), 0)
