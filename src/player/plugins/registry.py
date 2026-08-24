"""Durable enablement, permission consent and discovery state."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .installer import MANIFEST_NAME
from .manifest import PluginManifest, PluginPermission


@dataclass(frozen=True)
class InstalledPlugin:
    manifest: PluginManifest
    path: Path
    enabled: bool
    granted_permissions: frozenset[PluginPermission]


class PluginRegistry:
    def __init__(self, plugins_dir: str | Path):
        self.plugins_dir = Path(plugins_dir)
        self.state_path = self.plugins_dir / "registry.json"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

    def _state(self) -> dict:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def discover(self) -> list[InstalledPlugin]:
        state = self._state()
        result = []
        for manifest_path in sorted(self.plugins_dir.glob(f"*/{MANIFEST_NAME}")):
            try:
                manifest = PluginManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            item_state = state.get(manifest.id, {})
            granted = frozenset(
                permission for permission in manifest.permissions
                if permission.value in item_state.get("granted_permissions", [])
            )
            # An update that adds a capability is disabled until the user sees
            # and approves the new complete permission set.
            enabled = bool(item_state.get("enabled")) and granted == manifest.permissions
            result.append(InstalledPlugin(manifest, manifest_path.parent, enabled, granted))
        return result

    def update(self, plugin_id: str, *, enabled: bool, granted_permissions) -> None:
        state = self._state()
        state[plugin_id] = {
            "enabled": bool(enabled),
            "granted_permissions": sorted(
                item.value if isinstance(item, PluginPermission) else str(item) for item in granted_permissions
            ),
        }
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)

    def remove(self, plugin_id):
        state = self._state()
        state.pop(str(plugin_id), None)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)
