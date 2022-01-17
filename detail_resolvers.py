import re


class DetailResolver:
    file_name_regex = ".*"
    display_name = "ERR_NO_NAME"
    is_inline = True
    priority = 0

    def __init__(self, file_path):
        self._file_path = file_path

    def is_relevant(self):
        return bool(re.match(self.file_name_regex, self._file_path))

    def get_field_dict(self):
        return {
            "name": self.display_name,
            "value": self.resolve_detail(self._file_path),
            "inline": self.is_inline
        }

    def resolve_detail(self, file_path):
        pass
