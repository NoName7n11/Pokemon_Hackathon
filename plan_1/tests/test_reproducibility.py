from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401

from plan1.reproducibility import canonical_json_hash, derive_seed, sha256_directory, sha256_file


class ReproducibilityTests(unittest.TestCase):
    def test_file_and_directory_hashes_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.txt").write_text("alpha", encoding="ascii")
            (root / "nested").mkdir()
            (root / "nested" / "b.txt").write_text("beta", encoding="ascii")
            self.assertEqual(sha256_file(root / "a.txt"), sha256_file(root / "a.txt"))
            first = sha256_directory(root)
            (root / "nested" / "b.txt").write_text("changed", encoding="ascii")
            self.assertNotEqual(first, sha256_directory(root))

    def test_canonical_hash_ignores_mapping_order(self) -> None:
        self.assertEqual(canonical_json_hash({"a": 1, "b": 2}), canonical_json_hash({"b": 2, "a": 1}))

    def test_derived_seeds_are_stable_and_distinct(self) -> None:
        self.assertEqual(derive_seed(7, "worker", 2), derive_seed(7, "worker", 2))
        self.assertNotEqual(derive_seed(7, "worker", 2), derive_seed(7, "worker", 3))


if __name__ == "__main__":
    unittest.main()
