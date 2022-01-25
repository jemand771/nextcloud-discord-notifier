from dataclasses import dataclass


@dataclass
class EventData:

    user_name: str
    display_name: str
    action: str
    file_id: str
    file_path: str
    parent_activity_id: int
    iso_timestamp: str

    file_url: str = None
    folder_url: str = None
    additional_info = None

    @property
    def key(self):
        return f"{self.action}/{self.file_id}" + f"/{self.parent_activity_id}" if self.action == "file_changed" else ""

    @property
    def file_name(self):
        return self.file_path.split("/")[-1]

    @property
    def file_dir(self):
        return self.file_path.rsplit("/", 1)[0]
