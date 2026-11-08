# System D-Bus boundary (SX-CORE-005)

The unprivileged GTK process uses `ServiceClient`. When the system bus reports
`org.sonoran.SuperXHelper1` owned, the app selects `SessionServiceClient`: system
snapshots come from `DBusServiceClient`, and the two desktop-owner records are
replaced with records from the local service. The window subtitle displays the
selected mode. Selection happens at application startup.

```text
GTK → serial apply/read-back worker → session router
                                      ├─ performance.epp → local SuperXService → ppd (system bus)
                                      ├─ display.brightness → local SuperXService → GSD (session bus)
                                      └─ other capabilities → system D-Bus → superx-helperd → SuperXService
```

Both qualified writes remain in the user's process. power-profiles-daemon owns
EPP on the system bus and applies its own access policy. GNOME Settings Daemon
owns brightness on the user's session bus; a root system service cannot use that
session owner. The daemon never opens a session bus, rejects both owner-routed
writes even if requested directly, and constructs its service with
`LOCALLY_VALIDATED_WRITES - OWNER_ROUTED_WRITES` (currently empty). Its platform
backend therefore has no authorized writes. Its snapshots can read ppd but do
not grant write authority. No changes to the production qualification policy are
part of this boundary.

Apply and snapshot read-back run on one worker, preserving write order. Completion
and error toasts are delivered with `GLib.idle_add`; widgets render observed state
from the new snapshot rather than assuming the requested value was applied.
Manual refresh and initial snapshot loading retain the synchronous client API.
Refresh failures show a toast and retain the previous snapshot; on initial failure,
pages render an empty snapshot. A successful write remains successful if its
subsequent snapshot fetch fails; a separate toast reports that refresh failure.
The router currently collects a full local snapshot to obtain its two owner
records, reusing the existing facade rather than duplicating capability logic.

## API and authorization

Name/interface: `org.sonoran.SuperXHelper1`; object: `/org/sonoran/SuperXHelper1`.

| Method | Input | Output |
| --- | --- | --- |
| `GetSnapshot` | none | snapshot JSON string |
| `SetCapability` | capability ID string, value JSON string | OperationResult JSON string |

Serialization uses `transport.py` and contract dataclasses. Mutation failures
return an unsuccessful `OperationResult`; unexpected service failures return a
generic D-Bus error without backend paths. There is no command/path verb, raw
hardware access, configurable action name, network listener, or diagnostics
export method. Snapshots use the existing cheap UI telemetry, excluding SMART,
journal collection and unique storage serials/Bluetooth addresses.

The system bus policy grants name ownership only to root. Its default policy
allows callers to send exactly these two interface methods at this fixed path.
`GetSnapshot` exposes unauthenticated read-only data. Write authorization is
polkit's job, together with the mandatory facade gate; bus access grants no
hardware write. Unknown IDs, IDs without an explicit privileged action/type rule,
malformed/oversized JSON, invalid types/ranges, and desktop-owner writes fail
before polkit. JSON is capped at 4096 UTF-8 bytes; bool cannot stand in for int;
NaN, Infinity and overflow to infinity are rejected. Owner-specific range/options
and backend safety/read-back validation remain authoritative.

For a production-authorized privileged ID, polkit checks a fixed action from
`CAPABILITY_ACTIONS` with a `system-bus-name` subject containing the bus-supplied
unique sender. The caller cannot supply an identity or action. There are fixed
performance and cooling actions; active users default to
`auth_admin_keep`, inactive/other users to `no`. Interactive authorization has a
120-second timeout and runs asynchronously, so snapshots remain available during
a prompt; denial, cancellation and authority errors fail closed.
`SuperXService.set_capability` checks authorization again before backend dispatch.
Currently no privileged ID reaches polkit because none is qualified.

Trust boundaries include untrusted local D-Bus clients and disappearing owners.
The UI is not an authorization boundary. A compromised root process is outside
this boundary's threat model. Authentication caching is controlled by polkit.
The system unit restricts filesystem writes, device access and networking while
leaving sysfs readable. It intentionally has no writable sysfs exception today.

## Install (operator runs as root)

These are reviewable manual deployment instructions, not commands run by tests
or the implementation task. Use the distro Python/PyGObject stack and install the
reviewed Python package through the normal packaging workflow first. Ensure
`superx-helperd` is root-owned and resolves to the reviewed package in a
root-owned location; never point the unit at a user-writable checkout or venv.
The unit assumes `/usr/bin/superx-helperd`, where a distro package would put it.
There is no distro package yet; a pip install into the system Python lands the
entry point at `/usr/local/bin/superx-helperd` instead, and without an override
the unit fails with `status=203/EXEC` and restart-loops (observed 2026-11-08).
`contrib/systemd/superx-helperd-usr-local.conf` is the drop-in for that case.
Do not run the GUI as root.

From the reviewed source tree (the commands use paths relative to the
repository root), in a root shell:

```sh
pip install --break-system-packages --no-deps .
install -D -o root -g root -m 0644 contrib/dbus/org.sonoran.SuperXHelper1.conf /etc/dbus-1/system.d/org.sonoran.SuperXHelper1.conf
install -D -o root -g root -m 0644 contrib/polkit/org.sonoran.SuperXHelper.policy /usr/share/polkit-1/actions/org.sonoran.SuperXHelper.policy
install -D -o root -g root -m 0644 contrib/systemd/superx-helperd.service /etc/systemd/system/superx-helperd.service
install -D -o root -g root -m 0644 contrib/systemd/superx-helperd-usr-local.conf /etc/systemd/system/superx-helperd.service.d/exec.conf
systemctl reload dbus.service
systemctl daemon-reload
systemctl enable --now superx-helperd.service
systemctl status superx-helperd.service
```

`--no-deps` keeps the distro PyGObject and PyYAML; the package itself is pure
Python. Re-run the `pip install` step after pulling a new revision, since the
daemon runs the installed copy, not the checkout.

polkit watches its actions directory. The unit owns the bus name directly; no
D-Bus auto-activation file is installed. Launch the app as the ordinary console
user and check the subtitle, which should read `System D-Bus + session owners`.
A read-only check from that user's session is:

```sh
gdbus call --system --dest org.sonoran.SuperXHelper1 --object-path /org/sonoran/SuperXHelper1 --method org.sonoran.SuperXHelper1.GetSnapshot
```

Do not test deployment by setting hardware values. Install/systemd/bus-policy
enforcement and polkit-agent interaction require a separate opt-in deployment
review; unit tests use fake connections and do not establish live validation.

## Absence, loss and uninstall

If the system bus is unavailable or the name has no owner at startup, selection
returns `LocalServiceClient` and the subtitle says `Local session`. It retains
only the existing qualified owner writes. Calls do not auto-start the daemon.
After D-Bus selection, daemon loss produces failures; it never retries privileged
writes locally. Session-owner writes still route locally; if a subsequent system
snapshot fails, the UI reports refresh failure and keeps the previous snapshot.
If either desktop owner disappears, its existing service adapter refuses writes
without falling back to sysfs. Restart the app to select a changed service mode.

To uninstall the boundary, in a root shell:

```sh
systemctl disable --now superx-helperd.service
rm -r /etc/systemd/system/superx-helperd.service.d
rm /etc/systemd/system/superx-helperd.service
rm /etc/dbus-1/system.d/org.sonoran.SuperXHelper1.conf
rm /usr/share/polkit-1/actions/org.sonoran.SuperXHelper.policy
systemctl daemon-reload
systemctl reload dbus.service
```

Remove any operator-created unit override separately. Remove the Python package
with its package manager if desired; user profiles/data need no deletion.

## Adding a future privileged capability

1. Complete local qualification with before/read-back/restore evidence and update
   the production policy entry through its own review. Discovery is insufficient.
2. Add an exact capability ID → fixed polkit action mapping and strict JSON
   type/range validation. Add an action to the policy XML if its family is new;
   never derive action strings from caller input. Desktop-owned IDs stay local.
3. Implement facade/backend safety and read-back checks, with tests for unknown,
   unqualified, invalid, denied/unavailable polkit and backend failure paths, plus
   success against fake hardware and routing/main-loop delivery regressions.
4. Review the unit sandbox and grant only the specific writable paths/capabilities
   required by the qualified backend. Do not broadly expose sysfs or devices.

No upstream source was copied; this uses the project's existing Gio owner and
transport patterns.
