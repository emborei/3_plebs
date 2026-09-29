"""Install vgamepad without its interactive, privileged ViGEmBus installer.

The upstream 0.1.0 setup.py launches msiexec while pip prepares wheel metadata
on Windows. That is unsuitable for an unattended portable-app build. The app
ships the Python bindings and client DLLs; the user installs the driver once,
explicitly, as documented in README-FIRST.txt.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

VERSION = "0.1.0"
INSTALLER_BLOCK = """    # Prompt installation of the ViGEmBus driver (blocking call)
    if sys.argv[1] != 'egg_info' and sys.argv[1] != 'sdist':
        if not vigem_installed:
            subprocess.call(['msiexec', '/i', '%s' % str(pathMsi)], shell=True)
"""


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="survivors-buddy-vgamepad-") as temp:
        root = Path(temp)
        downloads = root / "download"
        downloads.mkdir()
        subprocess.run(
            [
                sys.executable, "-m", "pip", "download", "--no-deps",
                "--no-binary=:all:", "--dest", str(downloads),
                f"vgamepad=={VERSION}",
            ],
            check=True,
        )
        archives = list(downloads.glob(f"vgamepad-{VERSION}.*"))
        if len(archives) != 1 or not tarfile.is_tarfile(archives[0]):
            raise RuntimeError(f"Expected one vgamepad {VERSION} source archive.")

        source_root = root / "source"
        source_root.mkdir()
        with tarfile.open(archives[0], "r:gz") as archive:
            resolved_root = source_root.resolve()
            for member in archive.getmembers():
                if member.issym() or member.islnk():
                    raise RuntimeError(f"Unexpected link in vgamepad source archive: {member.name}")
                destination = (source_root / member.name).resolve()
                if os.path.commonpath((str(resolved_root), str(destination))) != str(resolved_root):
                    raise RuntimeError(f"Unsafe path in vgamepad source archive: {member.name}")
            archive.extractall(source_root)

        projects = list(source_root.glob(f"vgamepad-{VERSION}"))
        if len(projects) != 1:
            raise RuntimeError("Could not locate the extracted vgamepad source directory.")
        project = projects[0]
        setup_py = project / "setup.py"
        source = setup_py.read_text(encoding="utf-8")
        if source.count(INSTALLER_BLOCK) != 1:
            raise RuntimeError("The expected upstream ViGEmBus installer block changed; refusing an unsafe patch.")
        setup_py.write_text(source.replace(INSTALLER_BLOCK, ""), encoding="utf-8")

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", str(project)],
            check=True,
        )


if __name__ == "__main__":
    main()
