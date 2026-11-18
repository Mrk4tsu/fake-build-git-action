import io
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ci"))
import fetch_source


class SourceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.archive = self.root / "source.tar.gz"

    def make_archive(self, extra=()):
        files = [(f"NRO-sha/{name}", b"fixture") for name in fetch_source.REQUIRED_FILES]
        files.extend(extra)
        with tarfile.open(self.archive, "w:gz") as archive:
            for name, content in files:
                member = tarfile.TarInfo(name)
                if isinstance(content, tarfile.TarInfo):
                    member = content
                else:
                    member.size = len(content)
                archive.addfile(member, io.BytesIO(content) if isinstance(content, bytes) else None)

    def test_only_unity_inputs_are_extracted(self):
        self.make_archive([
            ("NRO-sha/.github/workflows/remote.yml", b"untrusted workflow"),
            ("NRO-sha/ci/cleanup.py", b"untrusted build tool"),
            ("NRO-sha/.git/config", b"private git metadata"),
            ("NRO-sha/user.keystore", b"private signing key"),
        ])
        fetch_source.extract_unity_source(self.archive, self.workspace)
        self.assertEqual({p.name for p in self.workspace.iterdir()}, fetch_source.SOURCE_FOLDERS)
        for name in fetch_source.REQUIRED_FILES:
            self.assertEqual((self.workspace / name).read_bytes(), b"fixture")

    def test_parent_traversal_is_rejected_before_writing(self):
        self.make_archive([("NRO-sha/Assets/../../escaped.txt", b"outside")])
        with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
            fetch_source.extract_unity_source(self.archive, self.workspace)
        self.assertEqual(list(self.workspace.iterdir()), [])
        self.assertFalse((self.root / "escaped.txt").exists())

    def test_archive_link_is_rejected(self):
        link = tarfile.TarInfo("NRO-sha/Assets/external")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../ci"
        self.make_archive([(link.name, link)])
        with self.assertRaisesRegex(ValueError, "Links and special files"):
            fetch_source.extract_unity_source(self.archive, self.workspace)
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_existing_source_is_preserved(self):
        self.make_archive()
        (self.workspace / "Assets").mkdir()
        sentinel = self.workspace / "Assets" / "sentinel.txt"
        sentinel.write_text("existing work", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            fetch_source.extract_unity_source(self.archive, self.workspace)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing work")

    def test_lfs_pointer_is_not_silently_built(self):
        self.make_archive([("NRO-sha/Assets/texture.png", b"version https://git-lfs.github.com/spec/v1\n")])
        with self.assertRaisesRegex(ValueError, "Git LFS pointers"):
            fetch_source.extract_unity_source(self.archive, self.workspace)

    def test_missing_export_method_file_is_rejected(self):
        with tarfile.open(self.archive, "w:gz"):
            pass
        with self.assertRaisesRegex(ValueError, "missing Unity settings"):
            fetch_source.extract_unity_source(self.archive, self.workspace)

    def test_download_pins_sha_and_treats_ref_as_data(self):
        self.make_archive()
        archive_bytes = self.archive.read_bytes()
        sha = "a" * 40

        def fake_api(arguments, **kwargs):
            if "--jq" in arguments:
                return subprocess.CompletedProcess(arguments, 0, stdout=sha + "\n")
            kwargs["stdout"].write(archive_bytes)
            return subprocess.CompletedProcess(arguments, 0)

        with patch.object(fetch_source.subprocess, "run", side_effect=fake_api) as api:
            result = fetch_source.download_source(self.workspace, self.root, "feature/ios;$(echo no)")
        self.assertEqual(result, sha)
        self.assertIn("feature%2Fios%3B%24%28echo%20no%29", api.call_args_list[0].args[0][2])
        self.assertEqual(api.call_args_list[1].args[0][2], f"repos/Mrk4tsu/NRO/tarball/{sha}")
        self.assertEqual(list(self.root.glob("nro-snapshot-*")), [])

    def test_missing_token_fails_without_network(self):
        with patch.dict(os.environ, {"GH_TOKEN": ""}), patch.object(fetch_source.subprocess, "run") as api:
            with self.assertRaisesRegex(ValueError, "NRO_READ_TOKEN"):
                fetch_source.main()
            api.assert_not_called()

    def test_cleanup_keeps_build_tools_and_other_files(self):
        for directory in ("Assets", "Packages", "ProjectSettings", "build", "output", "ci", ".git"):
            path = self.workspace / directory
            path.mkdir()
            (path / "sentinel").write_bytes(b"fixture")
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(self.workspace)}):
            runpy.run_path(str(Path(fetch_source.__file__).with_name("cleanup.py")))
        self.assertEqual({p.name for p in self.workspace.iterdir()}, {"ci", ".git"})


if __name__ == "__main__":
    unittest.main()
