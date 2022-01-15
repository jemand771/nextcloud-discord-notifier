from dataclasses import dataclass


@dataclass
class EventData:

    user_name: str
    action: str
    file_id: str
    file_path: str
    parent_activity_id: int

    display_name: str = None
    file_url: str = None
    folder_url: str = None

    @property
    def key(self):
        return f"{self.parent_activity_id}_{self.file_id}"

    @property
    def file_name(self):
        return self.file_path.split("/")[-1]

    @property
    def file_dir(self):
        return self.file_path.rsplit("/", 1)[0]
