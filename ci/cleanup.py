"""Remove only fixed build paths inside the GitHub-hosted workspace."""

import os
from pathlib import Path
import shutil


workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
for name in (
    "Assets", "Packages", "ProjectSettings", "Library", "Temp", "Obj",
    "Logs", "UserSettings", "MemoryCaptures", "artifacts", "build", "output",
):
    target = workspace / name
    if target.is_symlink():
        target.unlink()
    elif target.exists():
        if target.resolve().parent != workspace:
            raise ValueError("Refusing to remove a path outside the build workspace.")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
