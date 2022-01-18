import unittest
from tempfile import NamedTemporaryFile

from parameterized import parameterized

import detail_resolvers


class FileResolverTest(unittest.TestCase):

    @staticmethod
    def resolve(class_, file_path):
        return class_(file_path=file_path).resolve_detail(file_path=file_path)

    @parameterized.expand(
        [
            (0, "0 Bytes"),
            (1, "1 Byte"),
            (2, "2 Bytes"),
            (10, "10 Bytes"),
            (100, "100 Bytes"),
            (999, "999 Bytes"),
            (1000, "1.0 kB"),
            (1049, "1.0 kB"),
            (1050, "1.1 kB"),
            (2000, "2.0 kB"),
            (10 ** 4, "10.0 kB"),
            (10 ** 5, "100.0 kB"),
            (10 ** 6, "1.0 MB"),
            (10 ** 9, "1.0 GB"),
        ]
    )
    def test_resolver_file_size(self, num_bytes, display_as):
        with NamedTemporaryFile("wb") as f:
            f.write(num_bytes * b"x")
            f.seek(0)
            self.assertEqual(
                self.resolve(detail_resolvers.FileSizeResolver, f.name),
                display_as
            )
