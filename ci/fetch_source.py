"""Download a pinned NRO snapshot and keep only Unity's three input folders."""

import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import quote


REPOSITORY = "Mrk4tsu/NRO"
SOURCE_FOLDERS = {"Assets", "Packages", "ProjectSettings"}
REQUIRED_FILES = (
    "Assets/Editor/IosCiBuild.cs",
    "Packages/manifest.json",
    "ProjectSettings/ProjectVersion.txt",
)


def extract_unity_source(archive_path, workspace):
    workspace = Path(workspace).resolve()
    if any((workspace / name).exists() for name in SOURCE_FOLDERS):
        raise ValueError("Source folders already exist; refusing to overwrite them.")

    with tarfile.open(archive_path, "r:gz") as archive:
        # Strip the GitHub-generated top-level folder. Never extract remote
        # workflows, build tools, Git configuration, or unrelated root files.
        selected = []
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if len(path.parts) < 2 or path.parts[1] not in SOURCE_FOLDERS:
                continue
            if path.is_absolute() or ".." in path.parts or "\\" in member.name:
                raise ValueError("Unsafe archive path.")
            if not (member.isdir() or member.isfile()):
                raise ValueError("Links and special files are not supported in Unity source.")
            selected.append((member, workspace.joinpath(*path.parts[1:])))

        for member, destination in selected:
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target)
            destination.chmod(member.mode & 0o777)
            if member.size < 1024 and destination.read_bytes().startswith(
                b"version https://git-lfs.github.com/spec/v1"
            ):
                raise ValueError("Archive contains Git LFS pointers; enable LFS files in source archives.")

    if not all((workspace / name).is_file() for name in REQUIRED_FILES):
        raise ValueError("Snapshot is missing Unity settings, packages, or IosCiBuild.Export.")


def download_source(workspace, runner_temp, source_ref):
    endpoint = f"repos/{REPOSITORY}"
    # Pass the ref as one URL component and use an argument list, never a shell.
    commit = subprocess.run(
        ["gh", "api", f"{endpoint}/commits/{quote(source_ref, safe='')}", "--jq", ".sha"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("GitHub returned an invalid commit SHA.")

    with tempfile.TemporaryDirectory(prefix="nro-snapshot-", dir=runner_temp) as temporary:
        archive_path = Path(temporary) / "source.tar.gz"
        with archive_path.open("wb") as archive:
            subprocess.run(
                ["gh", "api", f"{endpoint}/tarball/{commit}"],
                check=True,
                stdout=archive,
                stderr=subprocess.PIPE,
                timeout=600,
            )
        extract_unity_source(archive_path, workspace)
    return commit


def main():
    if not os.environ.get("GH_TOKEN"):
        raise ValueError("Add NRO_READ_TOKEN to BuildGithub Actions secrets (NRO Contents: read).")
    source_ref = os.environ.get("SOURCE_REF", "").strip()
    if not source_ref:
        raise ValueError("source_ref must contain a branch, tag, or commit SHA.")

    commit = download_source(
        os.environ["GITHUB_WORKSPACE"], os.environ["RUNNER_TEMP"], source_ref
    )
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"sha={commit}\n")
    print(f"Unity source ready at commit {commit}; no NRO Git history was cloned.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        # API errors can contain private response data; do not echo raw responses.
        print("::error::Could not download NRO. Check NRO_READ_TOKEN access and source_ref.")
        sys.exit(1)
    except (ValueError, OSError, KeyError, tarfile.TarError, subprocess.TimeoutExpired) as error:
        print(f"::error::{error}")
        sys.exit(1)
