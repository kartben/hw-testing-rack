"""Released boards (tools/released.py): a board revision that went to a fab keeps the fabrication files it was sent
with.  Changing a board that still carries a released revision fails here, with the way out: a new revision.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import released  # noqa: E402


class Released(unittest.TestCase):
    def test_released_revisions_are_frozen(self):
        found = released.findings()
        self.assertEqual(found, [], "\n".join(found))

    def test_list_is_well_formed(self):
        rels = json.loads(released.LIST.read_text(encoding="utf-8"))["releases"]
        self.assertTrue(rels)
        seen = set()
        for rel in rels:
            with self.subTest(board=rel["board"], rev=rel["rev"]):
                self.assertNotIn((rel["board"], rel["rev"]), seen, "listed twice")
                seen.add((rel["board"], rel["rev"]))
                self.assertTrue((ROOT / "electronics" / rel["board"] / "design.py").exists())
                self.assertRegex(rel["date"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertEqual(set(rel["files"]), {f.format(b=rel["board"]) for f in released.FILES})
                for sha in rel["files"].values():
                    self.assertRegex(sha, r"^[0-9a-f]{64}$")

    def test_line_ends_do_not_count_in_text_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.csv", Path(tmp) / "b.csv"
            a.write_bytes(b"R1,10k\nR2,1k\n")
            b.write_bytes(b"R1,10k\r\nR2,1k\r\n")
            self.assertEqual(released.digest(a), released.digest(b))


if __name__ == "__main__":
    unittest.main()
