import inspect
import urllib.parse
from tempfile import TemporaryDirectory

import requests
import requests.auth

import detail_resolvers
from model import EventData


class Nextcloud:
    _reshare_cache = None
    detail_resolvers = []
    DOWNLOADABLE_ACTIONS = ("file_created", "file_changed")

    def __init__(self, base_url, username, password):
        self._base_url = base_url
        self._auth = requests.auth.HTTPBasicAuth(username, password)
        self.import_detail_resolvers()

    def import_detail_resolvers(self):
        for name, obj in inspect.getmembers(detail_resolvers):
            if (
                    inspect.isclass(obj)
                    and issubclass(obj, detail_resolvers.DetailResolver)
                    and obj != detail_resolvers.DetailResolver
            ):
                self.detail_resolvers.append(obj)

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
        try:
            events = self.ocs(
                "activity/api/v2/activity/files",
                params={
                    "previews": "true",
                    "since": start_index
                }
            )
        # catch HTTP 304 (no activity)
        except AssertionError as e:
            if str(e).endswith("returned status code 304"):
                return []
            raise
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
        ]

    def load_event_data(self, event: EventData):
        if event.action in self.DOWNLOADABLE_ACTIONS:
            with TemporaryDirectory() as download_dir:
                target_path = f"{download_dir}/{event.file_name}"
                r = requests.get(self.create_direct_link(event.file_id))
                assert r.status_code == 200, f"direct download of fileId {event.file_id} failed"
                with open(target_path, "wb") as f:
                    f.write(r.content)
                event.additional_info = []
                for resolver_class in self.detail_resolvers:
                    resolver: detail_resolvers.DetailResolver = resolver_class(target_path)
                    if not resolver.is_relevant():
                        continue
                    event.additional_info.append(resolver.get_field_dict())
        return event

    def create_direct_link(self, file_id):
        r = self.ocs(
            "dav/api/v1/direct",
            request_type=requests.post,
            params={
                "fileId": file_id
            }
        )
        return r.get("url")

    def url_for(self, file_path, file_id=None, file_name=None):
        # TODO opening files just doesn't work?? -> ignore for now
        for path, url in self.reshare_cache.items():
            if file_path.startswith(path):
                params = {"path": file_path[len(path):]}
                if file_id or file_name:
                    return None
                return url + "?" + urllib.parse.urlencode(params)
        return None
