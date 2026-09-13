import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import deepread
import star
from store import get_paper, init_db


class ReadingWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "papers.db"
        self.pdfs = self.root / "papers"
        self.config = {
            "storage": {"db_path": str(self.db)},
            "paperwise": {"papers_dir": str(self.pdfs)},
        }
        init_db(self.db)
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "INSERT INTO papers (arxiv_id, title, score, pushed_at) VALUES (?, ?, ?, ?)",
                ("2609.04921", "Example Paper", 9, "2026-09-08"),
            )

    def run_star(self, *args):
        with patch.object(sys, "argv", ["star.py", *args]), \
                patch.object(star, "load_config", return_value=self.config), \
                contextlib.redirect_stdout(io.StringIO()):
            star.main()

    def test_star_defaults_to_bookmark_only(self):
        with patch.object(star, "download_pdf") as download:
            self.run_star("2609.04921")
        download.assert_not_called()
        self.assertEqual(get_paper(self.db, "2609.04921")["starred"], 1)
        self.assertFalse(self.pdfs.exists())

    def test_download_is_opt_in_and_ids_are_deduplicated(self):
        with patch.object(star, "download_pdf") as download:
            self.run_star("--download", "2609.04921v2", "2609.04921")
        download.assert_called_once_with("2609.04921", "Example Paper", self.pdfs)

    def test_interactive_selection_does_not_download(self):
        with patch("builtins.input", return_value="1"), \
                patch.object(star, "download_pdf") as download:
            self.run_star()
        download.assert_not_called()
        self.assertEqual(get_paper(self.db, "2609.04921")["starred"], 1)

    def test_download_failure_preserves_bookmark(self):
        with patch.object(star, "download_pdf", side_effect=OSError("offline")):
            self.run_star("--download", "2609.04921")
        self.assertEqual(get_paper(self.db, "2609.04921")["starred"], 1)

    def test_deepread_uses_arxiv_even_with_local_pdf(self):
        self.pdfs.mkdir()
        (self.pdfs / "2609_04921_Example_Paper.pdf").write_bytes(b"%PDF-1.4")
        with patch.object(deepread.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertTrue(deepread.deep_read_one("rh", self.root, "2609.04921"))
        run.assert_called_once_with(
            ["rh", "read", "--arxiv", "2609.04921"], cwd=self.root
        )

    def test_deepread_returns_failure(self):
        with patch.object(deepread.subprocess, "run") as run:
            run.return_value.returncode = 1
            self.assertFalse(deepread.deep_read_one("rh", self.root, "2609.04921"))

    def test_batch_marks_only_successful_reads(self):
        self.run_star("2609.04921")
        for succeeded in (False, True):
            with self.subTest(succeeded=succeeded), \
                    patch.object(sys, "argv", ["deepread.py"]), \
                    patch.object(deepread, "load_config", return_value=self.config), \
                    patch.object(deepread, "_resolve_paperwise_repo", return_value=self.root), \
                    patch.object(deepread, "_resolve_rh_bin", return_value="rh"), \
                    patch.object(deepread, "deep_read_one", return_value=succeeded) as read, \
                    contextlib.redirect_stdout(io.StringIO()):
                deepread.main()
                read.assert_called_once_with("rh", self.root, "2609.04921")
                self.assertEqual(
                    get_paper(self.db, "2609.04921")["deep_read_at"] is not None,
                    succeeded,
                )


if __name__ == "__main__":
    unittest.main()