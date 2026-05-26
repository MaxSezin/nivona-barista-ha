надо доб# Hardware Compatibility List

> Living document. Confirmed by the maintainer (✅), the community (👥), or
> known-broken (❌). If you have a working — or broken — combo not listed
> below, please open a bug report (the template asks for adapter type + model)
> and we'll keep this table fresh.

There are **two BLE transport topologies** to choose from. Read the
[README's BLE topology section](README.md#ble-topology--strongly-prefer-an-esphome-proxy)
before opening a bug report — the dev / test coverage gap matters.

---

## 1. BLE transport (host → machine)

### 1.1 ESPHome BLE proxy 🟢 **recommended**

A second-hand or $10 new ESP32 board flashed with ESPHome's
[`bluetooth_proxy`](https://esphome.io/projects/?type=bluetooth) component sits
near the coffee machine and bridges its BLE traffic over Wi-Fi to Home
Assistant's `bluetooth` integration. This is the **primary tested path** in
this repository — the maintainer's development setup, the BLE-proxy `pair=True`
delegation, and the protocol-level retry logic all live and die against this
topology day-to-day.

| Board | Chipset | Status | Tested by | Notes |
|---|---|---|---|---|
| **Seeed XIAO ESP32-C6** | ESP32-C6 (BLE 5.3, Wi-Fi 6) | ✅ primary | dzerik (continuous) | Repo ships [`esphome/ble-proxy-xiao-c6.yaml`](esphome/ble-proxy-xiao-c6.yaml). Recommended starting point. Power via USB-C; place within ~5 m of the machine. |
| **Generic ESP32-WROOM-32** | ESP32 (BLE 4.2) | 👥 community-confirmed | community via ESPHome docs | Works with the stock `bluetooth_proxy` example. Watch power: cheap clones can brown out under sustained advertising bursts. |
| **ESP32-S3 DevKitC** | ESP32-S3 (BLE 5.0) | 👥 expected to work | — | Same SDK as XIAO ESP32-C6; same ESPHome config shape. Untested by maintainer but no known protocol caveat. |
| **M5Stack ATOM Lite** | ESP32-PICO-D4 (BLE 4.2) | 👥 expected to work | — | Inexpensive, integrated power supply; common for fixed-install BLE proxies. |

**Why this topology is preferred for triage:**

- `pair=True` from `bleak-retry-connector` delegates to the ESP32's
  Bluedroid/NimBLE stack, which sidesteps every BlueZ pairing quirk
  (`No agent available`, `Authentication failed`, `bluetoothd` SEGFAULTs in
  headless Linux setups).
- The proxy's BLE state is recoverable through a single OTA reflash, never
  through fighting D-Bus.
- Repeatable across operating systems — HA OS, Container, Supervised, Core,
  bare metal — because the BLE stack runs on the ESP, not the host.

#### Required / used by this integration

Stock `bluetooth_proxy` covers the happy path, but
[`esphome/ble-proxy-xiao-c6.yaml`](esphome/ble-proxy-xiao-c6.yaml) ships
**four integration-specific extras** that the `melitta_barista` code path
explicitly calls. Bring-your-own YAML works only if you mirror them — the
template is the source of truth:

| Knob | Required by | Why |
|---|---|---|
| `bluetooth_proxy: { active: true }` | every brew + handshake | Stock ESPHome defaults to passive ad relay only. We need GATT writes (recipe HJ frames, freestyle brew, settings) — these flow through `active: true`. Without it the handshake never even starts. |
| `esp32_ble: { max_connections: 4 }` + `bluetooth_proxy: { connection_slots: 3 }` | every connection | The default 3-slot pool is too tight once `esp32_ble_tracker` + `bluetooth_proxy` register their components — the compiler warns explicitly. One slot per machine you want to drive concurrently, plus headroom for the scanner. |
| Custom `api.actions: clear_ble_bonds` | "Hard Repair" / `force_pair_full` repair flow (`__init__.py:_handle_force_repair`) | When the ESP keeps a stale LTK and rejects fresh SMP with `auth fail reason=82`, the integration calls `esphome.<proxy>_clear_ble_bonds` to wipe `esp_ble_get_bond_device_list` from NVS. The action body runs four lines of `esp_ble_remove_bond_device(...)` — there is no stock equivalent. Without this action the Hard Repair path degrades to a clearly-worded error ("Add the `clear_ble_bonds` action to your ESPHome YAML…") and the user must reflash the proxy manually. |
| Custom `api.actions: disconnect_ble_peer` | same repair flow, when a slot is stuck `ESTABLISHED` | After certain `auth fail reason=82` paths the connection slot holds a half-closed link and the GAP layer ignores fresh connect requests. The integration calls `esphome.<proxy>_disconnect_ble_peer { peer_mac: ... }` to force `esp_ble_gap_disconnect` so the next pair attempt opens a fresh SMP exchange. Without it the slot stays wedged until proxy reboot. |
| `esphome: { min_version: 2025.8.0 }` | the two `api.actions:` blocks above | The top-level `api.actions:` schema is 2025.8+. Older ESPHome ignores the block silently — pinning the minimum fails the compile early instead. |

The integration falls back gracefully when an action is missing
(`hass.services.has_service` check + an explicit error message naming the
exact YAML snippet to add — see `__init__.py:_handle_force_repair`), so a
stock-config `bluetooth_proxy` still **works for daily use**. The lossy
degradation is confined to the recovery flows: stuck-bond / stuck-slot
incidents then need a manual proxy reboot instead of a service call from
HA's Repairs dialog.

The XIAO C6 yaml additionally toggles antenna-switch GPIOs (FM8625H IC on
GPIO3 + GPIO14) and a status LED on GPIO15. These are board-specific to the
Seeed XIAO ESP32-C6 and harmless to omit on other boards.

### 1.2 Local Bluetooth adapter ⚠️ supported, less-tested

Built-in BLE on the Home Assistant host (a Raspberry Pi's onboard adapter, a
USB dongle, a workstation chipset). Goes through BlueZ + a D-Bus `Agent1`
that this integration registers automatically (`ble_agent.py`'s
`_NoInputOutputAgent` for "Just Works" pairing).

This topology **works**, but the integration's pair / reconnect path under
BlueZ has fewer combined test-hours than the proxy path because the
maintainer's dev setup doesn't use it. Edge cases reported through GitHub
issues are typically here.

| Adapter | Chipset | Status | Notes |
|---|---|---|---|
| **Raspberry Pi 4 / 5 onboard BLE** | Cypress / Infineon CYW43455 (Pi 4) / CYW43455 (Pi 5) | 👥 community-confirmed | Works after the routine `bluetoothctl` setup. Pi's antenna design varies — keep the machine within line of sight if range is a problem. |
| **Intel Wireless 7265 / 8260 / 8265 / AX200 / AX201 / AX210** | Intel | 👥 community-confirmed | Standard Linux BlueZ path. Reliable. |
| **CSR8510 USB dongle** | CSR / Qualcomm | 👥 community-confirmed | The classic $5 BLE dongle. Verified through unrelated HA integrations; assumed-good here. |
| **TP-Link UB500 / UB400** | RTL8761B | 👥 community-confirmed | Needs `rtl_bt_*` firmware on Debian-style distros. Otherwise drop-in. |
| **Built-in BLE on `homeassistant.local` HA OS** | varies (host hardware) | 👥 case-by-case | Most failures here come down to `bluetoothd` cache or stale pairing — see the troubleshooting notes below and in #14. |

#### Known headless-Linux quirks (from #14)

- Stale BlueZ cache for a previously-discovered machine can survive across
  factory-reset + re-add. Cleanup: `bluetoothctl disconnect <MAC>` then
  `bluetoothctl remove <MAC>`, then add the integration again with the
  machine in pair mode.
- `bluetoothd` can SEGFAULT on certain pairing-cancel paths if no D-Bus
  agent is registered when the request arrives. The integration's
  `_NoInputOutputAgent` covers this; if you see a fresh report, the
  agent-registration path may need to be extended to cover continuous
  reconnects too (tracked in #14 part 2).

### 1.3 BlueZ on Docker / VPS without a desktop session

Same as 1.2 but specifically headless. The D-Bus pairing agent in the
integration is what unblocks this — there's no Blueman / gnome-bluetooth
helper to fall back on. If something breaks here, please include
`bluetoothctl show` output in the bug report.

---

## 2. Coffee machines

Authoritative table is in the
[README's "Supported brands and models" section](README.md#supported-brands-and-models).
Quick reference for triage:

| Brand | Family | Recipe writes | Recipe reads | Auto-brew via Sommelier | Notes |
|---|---|---|---|---|---|
| **Melitta** | Barista T Smart | ✅ | ✅ | ✅ | Single-hopper. Stable. |
| **Melitta** | Barista TS Smart | ✅ | ✅ | ✅ | Dual-hopper. Stable. |
| **Nivona** | NICR 6xx | ❌ | ❌ | ❌ (print-only) | Sommelier panel still works as a recipe notebook. |
| **Nivona** | NICR 7xx (756–789) | ❌ | ❌ | ❌ (print-only) | Includes NICR 779 — regex fix in v0.74.2 (#14). |
| **Nivona** | NICR 79x | ❌ | ❌ | ❌ (print-only) | — |
| **Nivona** | NICR 9xx | ❌ | ❌ | ❌ (print-only) | Fluid amounts written as ml × 10 — handled internally. |
| **Nivona** | NICR 1030 / 1040 | ❌ | ❌ | ❌ (print-only) | — |
| **Nivona** | NIVO 8xxx | ❌ | ❌ | ❌ (print-only) | Different brew opcode (`0x04` vs `0x0B`) — handled. |

"Auto-brew via Sommelier" is gated on the family's `supports_recipe_writes`
flag. All Nivona families decline because the integration cannot write a
custom freestyle recipe to the machine's recipe table. The Sommelier UI
still generates recipes, lets you rate / favorite / save them as presets,
and shows the steps to brew manually via the machine's own selector — only
the "Start brewing" button is disabled. See
[CHANGELOG 0.73.0](CHANGELOG.md) for the brand-honesty gate.

---

## 3. Contributing to this list

If your hardware combination isn't listed:

1. File a bug report (works ✅ or doesn't ❌) via
   [the issue template](https://github.com/dzerik/melitta-barista-ha/issues/new?template=bug_report.yml).
2. The template asks for **BLE adapter chipset / model** — fill it in.
3. The maintainer adds an HCL.md row in the next release.

If you can reproduce a fresh BlueZ / D-Bus quirk specifically against
section 1.2 — please include `bluetoothctl show`, `bluetoothctl info <MAC>`,
and the `melitta_barista` debug log around the failed connection. Those
three artifacts are what we need to upgrade an entry from 👥 to ✅ or move
it to ❌.
