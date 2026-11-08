"""Sanitized declarative intent; only qualified capabilities can be applied.

Selection is persisted separately and never replayed automatically on startup.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import TYPE_CHECKING, Any

import yaml

from superx_helper.contracts import CapabilitySnapshot

if TYPE_CHECKING:
    from superx_helper.client import ServiceClient

LOG = logging.getLogger(__name__)
EPP_VALUES = ("power-saver", "balanced", "performance")
FIELDS = {
    "epp": "performance.epp",
    "brightness": "display.brightness",
    "internal_fan_mode": "cooling.internal_fan",
    "power_target_w": "performance.power_target",
}
_APPLY_LOCK = threading.Lock()


def _text(value: Any, label: str, limit: int) -> None:
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or not all(c.isalnum() or c in " _.,:!?'-()" for c in value)
            or ".." in value
            or re.search(r"\b(?:sudo|bash|sh|exec|curl|wget|chmod|chown|rm|python3?|systemctl|reboot|shutdown|echo|printf|touch|mkfs|mount|umount|nvme|bluetoothctl|gdbus)\b", value, re.I)):
        raise ValueError(f"{label} must be plain text, without paths or commands")


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    epp: str | None = None
    brightness: int | None = None
    internal_fan_mode: str | None = None
    power_target_w: int | None = None
    requires: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text(self.name, "name", 80)
        _text(self.description, "description", 500)
        if self.epp is not None and self.epp not in EPP_VALUES:
            raise ValueError("epp must be a power-profiles-daemon profile name")
        if self.brightness is not None and (type(self.brightness) is not int or not 5 <= self.brightness <= 100):
            raise ValueError("brightness must be an integer from 5 to 100")
        if self.internal_fan_mode is not None and self.internal_fan_mode not in ("auto", "manual", "quiet", "balanced", "performance"):
            raise ValueError("invalid internal_fan_mode")
        # ponytail: schema-only ceiling of 1000 W; any future writer needs qualified limits.
        if self.power_target_w is not None and (type(self.power_target_w) is not int or not 1 <= self.power_target_w <= 1000):
            raise ValueError("power_target_w must be an integer from 1 to 1000")
        if type(self.requires) is not dict or any(k != "frost_bay_health" or v != "healthy" for k, v in self.requires.items()):
            raise ValueError("only frost_bay_health: healthy is a recognized requirement")
        object.__setattr__(self, "requires", dict(self.requires))

    @classmethod
    def from_dict(cls, data: Any) -> Profile:
        if type(data) is not dict or set(data) - set(cls.__dataclass_fields__):
            raise ValueError("profile must be a mapping with recognized keys")
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError("invalid profile fields") from exc


DEFAULT_PROFILES = (
    Profile("Quiet", "Intent: favor power saving.", epp="power-saver"),
    Profile("Balanced", "Intent: balanced everyday operation.", epp="balanced"),
    Profile("Performance", "Intent: performance is power-increasing and has not been exercised live.", epp="performance"),
    Profile("Liquid Performance", "Intent: blocked until Frost Bay health and fallback are qualified.",
            epp="performance", requires={"frost_bay_health": "healthy"}),
)


def _path(filename: str) -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "superx-helper" / filename


def _atomic_save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            name = stream.name
            yaml.safe_dump(data, stream, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name is not None and os.path.exists(name):
            os.unlink(name)


def _validated_profiles(data: Any) -> list[Profile]:
    if type(data) is not list or not data:
        raise ValueError("profiles must be a nonempty list")
    profiles = [Profile.from_dict(item) for item in data]
    if len({p.name for p in profiles}) != len(profiles):
        raise ValueError("profile names must be unique")
    return profiles


def load_profiles() -> list[Profile]:
    try:
        with _path("profiles.yaml").open(encoding="utf-8") as stream:
            return _validated_profiles(yaml.safe_load(stream))
    except FileNotFoundError:
        return [Profile.from_dict(asdict(p)) for p in DEFAULT_PROFILES]
    except (OSError, ValueError, yaml.YAMLError) as exc:
        LOG.warning("Cannot load profiles; using built-in defaults: %s", exc)
        return [Profile.from_dict(asdict(p)) for p in DEFAULT_PROFILES]


def save_profiles(profiles: list[Profile]) -> None:
    data = [asdict(p) for p in profiles]
    _validated_profiles(data)
    _atomic_save(_path("profiles.yaml"), data)


def save_selected_profile(name: str) -> None:
    _text(name, "selected profile", 80)
    _atomic_save(_path("profile-state.yaml"), {"selected": name})


def load_selected_profile() -> str | None:
    try:
        with _path("profile-state.yaml").open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
        if type(data) is not dict or set(data) != {"selected"}:
            raise ValueError("invalid selection state")
        _text(data["selected"], "selected profile", 80)
        return data["selected"]
    except FileNotFoundError:
        return None
    except (OSError, ValueError, yaml.YAMLError) as exc:
        LOG.warning("Cannot load profile selection: %s", exc)
        return None


@dataclass
class ProfileStepResult:
    field: str
    capability_id: str
    requested_value: Any
    status: str = "skipped"
    reason: str = ""
    previous_value: Any = None
    rollback_status: str | None = None
    rollback_reason: str = ""


@dataclass
class ProfileApplyResult:
    steps: list[ProfileStepResult]
    success: bool = False
    rollback_attempted: bool = False
    rollback_succeeded: bool | None = None
    error_message: str | None = None


def _value_reason(snapshot: CapabilitySnapshot, cid: str, value: Any) -> str:
    record = snapshot.by_id(cid)
    if record is None:
        return "Capability record missing"
    if not record.can_write:
        return record.reason_unavailable or "Capability is not writable on this host"
    if cid == FIELDS["epp"]:
        if type(value) is not str or value not in EPP_VALUES or value not in record.allowed_values:
            return "Power profile is not advertised by this host"
    elif type(value) is not int or not 5 <= value <= 100:
        return "Brightness must be an integer from 5 to 100"
    if record.minimum is not None and isinstance(value, int) and value < record.minimum:
        return "Value is below the host minimum"
    if record.maximum is not None and isinstance(value, int) and value > record.maximum:
        return "Value is above the host maximum"
    return ""


def profile_steps(profile: Profile, snapshot: CapabilitySnapshot) -> list[ProfileStepResult]:
    """Shared preview/apply gate. Future fields stay inert even if advertised writable."""
    profile = Profile.from_dict(asdict(profile))
    steps = []
    for name, cid in FIELDS.items():
        value = getattr(profile, name)
        if value is None:
            continue
        if profile.requires:
            reason = "Frost Bay health is not qualified; healthy state and safe fallback are unavailable"
        elif name in ("internal_fan_mode", "power_target_w"):
            reason = "Declared future field; production control is not qualified"
        else:
            reason = _value_reason(snapshot, cid, value)
            if not reason:
                restore_reason = _value_reason(snapshot, cid, snapshot.by_id(cid).observed_value)
                if restore_reason:
                    reason = "Cannot capture restorable observed state: " + restore_reason
        steps.append(ProfileStepResult(name, cid, value, "skipped" if reason else "ready", reason))
    return steps


def _write_verified(client: ServiceClient, cid: str, value: Any) -> None:
    reason = _value_reason(client.get_snapshot(), cid, value)
    if reason:
        raise RuntimeError(reason)
    outcome = client.set_capability(cid, value)
    if not outcome.success or outcome.dry_run:
        raise RuntimeError(outcome.error_message or "Write did not succeed")
    record = client.get_snapshot().by_id(cid)
    if record is None or type(record.observed_value) is not type(value) or record.observed_value != value:
        raise RuntimeError("Fresh read-back does not match request")


def apply_profile(client: ServiceClient, profile: Profile) -> ProfileApplyResult:
    # ponytail: serializes profile transactions in this process only; other writers need service arbitration.
    with _APPLY_LOCK:
        result = ProfileApplyResult([])
        attempted = []
        try:
            result.steps = profile_steps(profile, client.get_snapshot())
            for step in result.steps:
                if step.status == "skipped":
                    continue
                snapshot = client.get_snapshot()
                reason = _value_reason(snapshot, step.capability_id, step.requested_value)
                if reason:
                    step.status, step.reason = "skipped", reason
                    continue
                step.previous_value = snapshot.by_id(step.capability_id).observed_value
                reason = _value_reason(snapshot, step.capability_id, step.previous_value)
                if reason:
                    step.status, step.reason = "skipped", "Cannot capture restorable observed state: " + reason
                    continue
                # Include the attempted step: a failed owner call may already have changed state.
                attempted.append(step)
                step.status = "failed"
                try:
                    _write_verified(client, step.capability_id, step.requested_value)
                except Exception as exc:
                    step.reason = str(exc)
                    raise
                step.status = "applied"
            result.success = any(s.status == "applied" for s in result.steps)
        except Exception as exc:
            result.error_message = str(exc)
            for step in result.steps:
                if step.status == "ready":
                    step.status, step.reason = "skipped", "Aborted after an earlier failure"
            result.rollback_attempted = bool(attempted)
            for step in reversed(attempted):
                try:
                    _write_verified(client, step.capability_id, step.previous_value)
                    step.rollback_status = "restored"
                except Exception as rollback_exc:
                    step.rollback_status = "failed"
                    step.rollback_reason = str(rollback_exc)
            if attempted:
                result.rollback_succeeded = all(s.rollback_status == "restored" for s in attempted)
        return result
