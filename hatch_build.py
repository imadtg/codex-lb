from __future__ import annotations

import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Build the dashboard before Hatch assembles a wheel."""

    def initialize(self, version: str, build_data: dict[str, object]) -> None:
        root = Path(self.root)
        frontend = root / "frontend"
        static = root / "app" / "static"

        subprocess.run(["bun", "install", "--frozen-lockfile"], cwd=frontend, check=True)
        subprocess.run(["bun", "run", "build"], cwd=frontend, check=True)

        index = static / "index.html"
        assets = static / "assets"
        has_javascript = any(assets.glob("*.js"))
        has_stylesheet = any(assets.glob("*.css"))
        if not index.is_file() or not has_javascript or not has_stylesheet:
            raise RuntimeError(
                "frontend build did not produce app/static/index.html plus JavaScript and CSS assets"
            )
