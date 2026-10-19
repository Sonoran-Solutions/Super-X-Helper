"""Locally qualified write policy; discovery alone never authorizes writes."""

# Entries are added only after live set/read-back/restore evidence is recorded in
# docs/LIVE_INTEGRATION_HANDOFF.md. Both entries below are authorized ONLY through
# their maintained owners (power-profiles-daemon, GNOME Settings Daemon), never sysfs.
LOCALLY_VALIDATED_WRITES: frozenset[str] = frozenset(
    {"performance.epp", "display.brightness"}
)

# Capabilities written through an owner adapter; the raw sysfs backend must not
# inherit authorization for them.
OWNER_ROUTED_WRITES: frozenset[str] = frozenset(
    {"performance.epp", "display.brightness"}
)
