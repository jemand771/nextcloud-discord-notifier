import urllib.parse

import requests
import requests.auth

from model import EventData


class Nextcloud:

    _reshare_cache = None

    def __init__(self, base_url, username, password):
        self._base_url = base_url
        self._auth = requests.auth.HTTPBasicAuth(username, password)

    def ocs(self, path, request_type=requests.get, headers=None, params=None, **kwargs):
        r = request_type(
            f"{self._base_url}/ocs/v2.php/apps/{path}",
            auth=self._auth,
            headers={
                "OCS-APIRequest": "true",
                **(headers or {})
            },
            params={
                "format": "json",
                **(params or {})
            },
            **kwargs
        )
        assert r.status_code == 200, f"api {path} returned status code {r.status_code}"
        return r.json().get("ocs").get("data")

    def fetch_activities(self, limit, start_index=0):
        events = self.ocs(
            "activity/api/v2/activity/all",
            params={
                "previews": "true",
                "since": start_index
            }
        )
        if len(events) >= limit:
            return events[:limit]
        return events + self.fetch_activities(limit - len(events), start_index=events[-1].get("activity_id"))

    def fetch_shared_with_me(self):
        return self.ocs(
            "files_sharing/api/v1/shares",
            params={
                "shared_with_me": "true"
            }
        )

    def fetch_reshares(self, share, public_only=True):
        reshares = self.ocs(
            "files_sharing/api/v1/shares",
            params={
                "reshares": "true",
                "path": share.get("path")
            }
        )
        return [
            reshare for reshare in reshares
            if not public_only or reshare.get("url")
        ]

    def update_reshare_cache(self):
        self._reshare_cache = {
            reshare.get("path"): reshare.get("url")
            for share in self.fetch_shared_with_me()
            for reshare in self.fetch_reshares(share)
        }

    @property
    def reshare_cache(self):
        if self._reshare_cache is None:
            self.update_reshare_cache()
        return self._reshare_cache

    @staticmethod
    def shallow_events_from_activity(activity):
        display_name = activity.get("user")
        if user := activity.get("subject_rich")[1].get("user"):
            display_name = user.get("name")
        return [
            EventData(
                user_name=activity.get("user"),
                display_name=display_name,
                action=activity.get("type"),
                file_id=file_id,
                file_path=file_path,
                parent_activity_id=activity.get("activity_id")
            )
            for file_id, file_path in activity.get("objects").items()
            if activity.get("app") == "files"
        ]

    def load_event_data(self, event: EventData):
        return event

    def url_for(self, file_path, file_id=None, file_name=None):
        # TODO opening files just doesn't work?? -> ignore for now
        for path, url in self.reshare_cache.items():
            if file_path.startswith(path):
                params = {"path": file_path[len(path):]}
                if file_id or file_name:
                    return None
                return url + "?" + urllib.parse.urlencode(params)
        return None
