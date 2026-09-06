# Frost Bay — Linux Protocol Research

## Objective

Implement safe Linux discovery, telemetry, and control for the ONEXPLAYER Frost Bay external liquid cooler used with the liquid-cooled Super X.

The research target is the **Bluetooth software-control path**. ONEXPLAYER documents that the cooling tubes themselves do not transmit control data and that OneXConsole communicates with Frost Bay over Bluetooth.

## Current status

**Research not started on local hardware.**

### Confirmed from public documentation

- Frost Bay software control is Bluetooth-based.
- Bluetooth must remain enabled for normal OneXConsole communication.
- No USB data/driver path is required through the coolant connection.
- The liquid-cooled Super X supports a higher advertised platform power envelope when used with Frost Bay than the standard configuration.

### Community observations worth verifying locally

Community reports mention Bluetooth identities resembling `CoolingSystem_ONCE1`, Frost Bay connection state in OneXConsole, and cooler telemetry/control behavior. Treat all such details as **HYPOTHESIS/LIKELY** until reproduced on the actual hardware.

## Research questions

### Identity/discovery

- What exact Bluetooth name does this Frost Bay advertise?
- LE, Classic, or dual-mode?
- Public or random address type?
- Does OneXConsole rely on name, service UUID, manufacturer data, or another identity mechanism?
- Does the device require pairing/bonding, or only a GATT connection?

### GATT map

For every service/characteristic, record:

| Service UUID | Characteristic UUID | Properties | Observed role | Confidence |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | HYPOTHESIS |

### Telemetry

Potential fields to investigate without assuming they exist:

- connection/health state;
- coolant/ambient temperature;
- pump speed or commanded level;
- radiator fan speed or commanded level;
- flow/flow-health indication;
- fault/warning flags;
- firmware/device version.

### Controls

Potential controls to investigate only after evidence identifies them:

- mode selection;
- pump level;
- radiator fan level;
- automatic/manual behavior.

Do not assume raw percentages or units until confirmed.

### System interaction

- Does Super X firmware independently detect physical coolant connection?
- Does OneXConsole merely expose the 120 W profile, or does cooler telemetry participate in the decision?
- What happens to platform power when Frost Bay disconnects while a high-power profile is active?
- Is there any firmware-level safety fallback independent of the app?

## Phase A — Passive Linux discovery

Recommended initial commands/tools:

```bash
bluetoothctl show
bluetoothctl devices
bluetoothctl scan on
```

Then use an appropriate BlueZ/GATT browser to enumerate the target device without issuing writes.

Capture:

- advertised name;
- address type;
- RSSI only if useful;
- service UUIDs;
- manufacturer/service data;
- GATT services;
- characteristics;
- descriptors;
- read/write/notify properties.

### Experiment log

No local experiments recorded yet.

---

## Phase B — Read/notification observation

Subscribe only to characteristics advertised as readable/notifiable.

Record changes while performing **external, already-supported actions** that do not require unknown Linux writes, such as:

- Frost Bay powered off/on;
- connecting/disconnecting coolant loop if safe and per manufacturer procedure;
- known-good OneXConsole mode changes in a controlled Windows reference environment if available.

Map changing fields before attempting Linux control.

---

## Phase C — Static OneXConsole inspection

Inspect publicly distributed vendor software for protocol evidence without redistributing proprietary code.

Search for:

- `CoolingSystem` / Frost Bay names;
- Bluetooth/GATT UUID strings;
- characteristic names;
- byte constants;
- packet encoder/decoder functions;
- telemetry labels;
- command enums;
- range checks;
- reconnect and timeout logic;
- power-profile gating logic.

Document symbols/strings/behavior rather than copying substantial proprietary code.

---

## Phase D — Controlled known-good traffic capture

Only if prior phases do not sufficiently establish the protocol.

Use Windows/OneXConsole as an oracle and change one safe setting at a time.

Example matrix:

| Experiment | Before | After | BLE difference | Result |
|---|---|---|---|---|
| Mode change | TBD | TBD | TBD | — |
| Safe fan step | TBD | TBD | TBD | — |
| Safe pump step | TBD | TBD | TBD | — |

Avoid maximum/minimum extremes as first controls.

---

## Phase E — First Linux write

Gate before any write:

- [ ] exact target device identity confirmed;
- [ ] exact service/characteristic confirmed;
- [ ] command semantics understood;
- [ ] payload encoding understood;
- [ ] safe range known;
- [ ] expected effect known;
- [ ] prior state recorded;
- [ ] rollback/restoration action prepared;
- [ ] user is physically present at the device.

The first command should be benign, reversible, and visibly/telemetrically verifiable.

---

## Production protocol notes

Once fields become confirmed, define them here before moving them into code.

Example format:

```text
Characteristic: <UUID>
Role: telemetry notifications
Packet length: <n>
Byte 0: <meaning>
...
Evidence: EXP-...
Confidence: CONFIRMED
```

## Safety invariant

A disconnected, stale, unknown, or faulted Frost Bay state is **not equivalent to healthy**.

Any future liquid-only performance policy must require a recent positively validated health state and must define a safe fallback on communication loss.