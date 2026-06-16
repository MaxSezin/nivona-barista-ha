# Nivona NICR for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/MaxSezin/nivona-barista-ha?style=flat-square&include_prereleases)](https://github.com/MaxSezin/nivona-barista-ha/releases)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat-square)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/HA-2024.1%2B-blue?style=flat-square)](https://www.home-assistant.io/)
[![BLE](https://img.shields.io/badge/BLE-Bluetooth_LE-blue?style=flat-square)](#)
[![Translations](https://img.shields.io/badge/translations-29_languages-blueviolet?style=flat-square)](#localization)

A custom Home Assistant integration for controlling **Nivona NICR 6xx / 7xx / 79x / 9xx / 1030 / 1040** and **NIVO 8xxx** coffee machines over Bluetooth Low Energy (BLE). Monitor machine status, select and brew recipes, adjust per-brew parameters (strength, coffee amount, water amount, temperature, milk amount), and trigger maintenance — all from your Home Assistant dashboard.

> Based on the reverse-engineered Eugster/EFLibrary BLE protocol. The original multi-brand codebase is [dzerik/melitta-barista-ha](https://github.com/dzerik/melitta-barista-ha); this fork strips out Melitta-specific code and ships three bug fixes for Nivona users.

---

## Supported models

| Family | Representative models | MyCoffee slots | Strength levels | Notes |
|---|---|:---:|:---:|---|
| **600** | NICR 660 / 670 / 675 / 680 | 1 | 3 | — |
| **700** | NICR 756 / 758 / 759 / 768 / 769 / 778 / 779 / 788 / 789 | 4 | 3 | aroma balance |
| **79x** | NICR 790–797, 799 | 4 | 5 | aroma balance |
| **900** | NICR 920 / 930 | 4 | 5 | fluid ml×10 quirk |
| **900-light** | NICR 960 / 965 / 970 | 4 | 3 | — |
| **1030** / **1040** | NICR 1030 / 1040 | 4 | 5 | — |
| **8000** | NIVO 8101 / 8103 / 8107 | 4 | 5 | different brew opcode |

The machine is auto-detected from the BLE advertisement (`NIVONA-*` name prefix) and confirmed via the handshake protocol.

---

## Features

- **Real-time status monitoring** — machine state (Ready, Brewing, Cleaning, Descaling, Off), sub-process, progress percentage, required user actions via BLE push notifications
- **Recipe selection and brew** — pick from the family's built-in recipe list and brew with one tap
- **Brew parameter overrides** — sliders for strength, coffee amount, water amount, temperature, and milk amount; overrides are applied as a temp-recipe only when you actually change a value
- **Reset overrides** — dedicated button that clears all override sliders back to machine defaults so you can verify factory amounts
- **MyCoffee slot sensors** — read-only sensors exposing the per-slot amounts for each MyCoffee preset
- **Machine settings control** — water hardness, brew temperature, auto-off timer, energy saving, rinsing toggle
- **Maintenance operations** — easy clean, intensive clean, descaling, filter insert/replace/remove, evaporating, power off
- **Cancel in-flight brew** — one-click cancel during any running process
- **Confirm machine prompts** — dedicated button + binary sensor for flush/move-cup prompts with optional auto-confirm
- **Clock sync** — automatic or manual sync of the machine RTC to HA local time
- **AI Coffee Sommelier (alpha)** — in-HA admin panel with recipe generation via any HA conversation agent (OpenAI / Anthropic / Gemini / Ollama)
- **Encrypted BLE protocol** — full Eugster/EFLibrary stack (AES customer-key bootstrap + RC4 stream cipher, HU handshake with Nivona-specific verifier table)
- **29 languages** — full localization for all European and Slavic languages
- **ESPHome BLE proxy support** — recommended transport for stable long-running operation

## Bug fixes vs upstream

| # | Bug | Fix |
|---|-----|-----|
| 1 | Americano always brewed 40 mL instead of the configured amount | When any override is active, all slider values are now written to the temp-recipe, not just the ones the user explicitly touched |
| 2 | No water amount slider existed | Added a `Brew Water Amount` number entity (0–240 mL, step 5) |
| 3 | No way to clear override sliders once set | Added `Reset Brew Overrides` button that fires HA events to reset all sliders and their `user_set` flags |

---

## Supported recipes per family

| Family | Recipes |
|---|---|
| **600** | Espresso, Coffee, Americano, Cappuccino, Frothy Milk, Hot Water |
| **700** | Espresso, Cream, Lungo, Americano, Cappuccino, Latte Macchiato, Milk, Hot Water |
| **79x** | Espresso, Coffee, Americano, Cappuccino, Latte Macchiato, Milk, Hot Water |
| **900** / **900-light** | Espresso, Coffee, Americano, Cappuccino, Caffè Latte, Latte Macchiato, Hot Milk, Hot Water |
| **1030** | Espresso, Coffee, Americano, Cappuccino, Caffè Latte, Latte Macchiato, Hot Water, Warm Milk, Hot Milk, Frothy Milk |
| **1040** | Espresso, Coffee, Americano, Cappuccino, Caffè Latte, Latte Macchiato, Hot Water, Warm Milk, Frothy Milk |
| **8000** | Espresso, Coffee, Americano, Cappuccino, Caffè Latte, Latte Macchiato, Milk, Hot Water |

Nivona firmware does not expose recipe-editing opcodes — recipe list is fixed per family.

---

## BLE topology — strongly prefer an ESPHome proxy

> 🟢 **The recommended BLE transport is an [ESPHome `bluetooth_proxy`](https://esphome.io/projects/?type=bluetooth) on a $10 ESP32 board placed near the machine.** The ESP's BLE stack handles `pair=True` natively, sidestepping every BlueZ quirk (D-Bus `Agent1`, `Authentication failed`, headless-Linux `bluetoothd` crashes) that a host-side BLE adapter can run into.

A bare local Bluetooth adapter (Pi onboard BLE, USB dongle, host chipset) also works but is less stable on long-running setups.

The repo ships a ready-to-flash ESPHome config at [`esphome/ble-proxy-xiao-c6.yaml`](esphome/ble-proxy-xiao-c6.yaml) for the **Seeed XIAO ESP32-C6**.

### Running HA in a Docker container?

Three prerequisites are often missed:

1. **Install `bluez` on the host:**
   ```bash
   sudo apt update && sudo apt install -y bluez
   sudo systemctl enable --now bluetooth
   ```

2. **Mount the D-Bus socket:**
   ```yaml
   volumes:
     - /run/dbus:/run/dbus:ro
   ```

3. **Use `--privileged` and `--net=host`.**

---

## Requirements

- **Home Assistant** 2024.1 or newer
- **BLE transport** — ESPHome BLE proxy *(recommended)* or local Bluetooth adapter
- **Supported machine** — Nivona NICR 6xx / 7xx / 79x / 9xx / 1030 / 1040 or NIVO 8xxx
- **BLE range** — proxy within ~5 m of the machine; local adapter within ~10 m

---

## Installation

### Via HACS

1. Open HACS → **Integrations** → three-dot menu → **Custom repositories**.
2. Add: `https://github.com/MaxSezin/nivona-barista-ha`, category **Integration**.
3. Search for **Nivona NICR** and install.
4. Restart Home Assistant.

### Manual

1. Download or clone this repository.
2. Copy `custom_components/nivona_nicr` into your HA `config/custom_components/` directory.
3. Restart Home Assistant.

---

## Configuration

### Step 1: Enable Bluetooth on the machine

Make sure Bluetooth is enabled on your Nivona (refer to the machine manual).

### Step 2: Add the integration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Nivona NICR**.
3. If BLE discovery found your machine it will appear automatically; otherwise enter the MAC address manually.

### Step 3: Pair the device

BLE bonding is required on first setup only.

1. On the machine, open **Settings → Bluetooth / Connectivity / App connection** and enable **pairing mode** (the BLE icon should blink).
2. Press **Submit** in the HA setup dialog.
3. The integration connects and pairs automatically.

> **Note:** the machine supports only one BLE connection at a time. Disconnect the official Nivona app before pairing.

### Manual pairing via bluetoothctl

```bash
bluetoothctl
remove F1:2C:72:3F:75:ED   # your machine's MAC
scan on
pair F1:2C:72:3F:75:ED
trust F1:2C:72:3F:75:ED
info F1:2C:72:3F:75:ED      # verify: Paired: yes, Bonded: yes, Trusted: yes
exit
```

---

## Entities reference

### Sensors

| Entity | Description |
|--------|-------------|
| State | Machine state: Ready, Brewing, Cleaning, Descaling, Off, … |
| Activity | Sub-process: Grinding, Extracting, Steaming, Dispensing Water, Preparing |
| Progress | Brewing / cleaning progress (%) |
| Action Required | Required user action: Fill Water, Empty Trays, Move Cup to Frother, Flush Required, … |
| Connection | BLE connection status (diagnostic) |
| Firmware | Firmware version (diagnostic) |
| Features | Machine capability bits from HI response (diagnostic, disabled by default) |
| MyCoffee slot N — … | Per-slot amounts for coffee / water / milk / milk foam (read-only, diagnostic) |
| Stat sensors | Per-family capability-driven counters and gauges (beverages, maintenance, %) |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| Awaiting Confirmation | `on` when the machine shows a user-confirmable prompt |

### Select

| Entity | Description |
|--------|-------------|
| Recipe | Brew recipe selector (family-specific list) |
| Brand settings | Per-family setting dropdowns (from machine capabilities) |

### Buttons

| Entity | Description |
|--------|-------------|
| Brew | Brew the selected recipe with current override values |
| Brew My Coffee | Brew from the active MyCoffee slot |
| Cancel | Cancel the currently running operation |
| Confirm Prompt | Acknowledge an active machine prompt (HY) |
| Reset Brew Overrides | Clear all override sliders and reset `user_set` flags — next brew uses machine defaults |
| Factory Reset Settings | Reset all machine-wide settings to factory defaults |
| Factory Reset Recipes | Reset per-recipe customizations to factory defaults |
| Easy Clean | Start easy clean cycle |
| Intensive Clean | Start intensive clean cycle |
| Descaling | Start descaling |
| Filter Insert / Replace / Remove | Water filter operations |
| Evaporating | Steam evaporating cycle |
| Switch Off | Power off the machine |

### Numbers (brew overrides)

| Entity | Range | Default | Description |
|--------|:-----:|:-------:|-------------|
| Brew Strength | 0–4 | 2 | Strength level (0 = very mild, 4 = very strong) |
| Brew Coffee Amount | 0–120 mL | 40 | Coffee amount in mL |
| Brew Water Amount | 0–240 mL | 100 | Water amount in mL |
| Brew Temperature | 0–2 | 1 | Temperature (0 = cold, 1 = normal, 2 = high) |
| Brew Milk Amount | 0–240 mL | 100 | Milk amount in mL |

> Overrides are written to the machine only when at least one slider has been explicitly changed (`user_set = true`). Use **Reset Brew Overrides** to go back to machine defaults.

### Numbers (machine settings)

| Entity | Range | Description |
|--------|:-----:|-------------|
| Water Hardness | 1–4 | Water hardness for descaling schedule |
| Auto Off After | 15–240 min | Idle time before auto power off |

### Switches

| Entity | Description |
|--------|-------------|
| Energy Saving | Enable / disable energy saving mode |
| Rinsing Disabled | Enable / disable automatic rinsing |
| Auto Bean Select | Enable / disable automatic bean blend selection |

### Text

| Entity | Description |
|--------|-------------|
| Profile N Name | User profile names (read/write) |

### Time

| Entity | Description |
|--------|-------------|
| Machine Clock | Read-only; writable via `sync_clock` service or auto-sync |

---

## Services

### `nivona_nicr.sync_clock`

Push HA local time to the machine RTC.

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `entity_id` | string | Yes | Any entity from the target machine |

### `nivona_nicr.confirm_prompt`

Acknowledge an active machine prompt via HY.

| Parameter | Type | Required | Description |
|-----------|------|:--------:|-------------|
| `entity_id` | string | Yes | Any entity from the target machine |

### `nivona_nicr.repair_connection`

Manual one-tap recovery for a wedged BLE pairing. Walks every entry, reloads the ESPHome proxy that owns each scanner.

---

## Options

Configure via **Settings → Devices & Services → Nivona NICR → Configure**.

### Basic

| Parameter | Default | Description |
|-----------|:-------:|-------------|
| Poll interval | 5 s | Status poll frequency |
| Reconnect delay | 5 s | Initial delay before reconnect |
| Reconnect max delay | 300 s | Maximum backoff between reconnects |
| Poll errors before disconnect | 3 | Consecutive errors before forced disconnect |
| Frame timeout | 5 s | BLE command response timeout |
| Auto-confirm soft prompts | off | Auto-send HY for move-cup / flush prompts |

### Advanced

| Parameter | Default | Description |
|-----------|:-------:|-------------|
| BLE connect timeout | 15 s | Timeout for BLE connection |
| Pairing timeout | 30 s | Timeout for BLE pairing during setup |
| Recipe retries | 3 | Retry attempts for recipe operations |
| Initial connect delay | 3 s | Wait before first connection after setup |
| Auto-sync clock | on | Sync clock on reconnect and daily |
| Clock drift threshold | 2 min | Minimum drift before writing clock |
| Daily sync time | 03:17 | Time for daily clock sync |

---

## Automation examples

### Morning brew

```yaml
automation:
  - alias: "Morning Coffee at 7:00"
    trigger:
      - platform: time
        at: "07:00"
    condition:
      - condition: state
        entity_id: sensor.nivona_state
        state: "Ready"
    action:
      - service: button.press
        target:
          entity_id: button.nivona_brew
```

### Notify when coffee is ready

```yaml
automation:
  - alias: "Coffee Ready Notification"
    trigger:
      - platform: state
        entity_id: sensor.nivona_activity
        from: "Extracting"
        to: "None"
    action:
      - service: notify.mobile_app
        data:
          message: "Your coffee is ready!"
```

### Maintenance alert

```yaml
automation:
  - alias: "Coffee Machine Maintenance"
    trigger:
      - platform: state
        entity_id: sensor.nivona_action_required
    condition:
      - condition: not
        conditions:
          - condition: state
            entity_id: sensor.nivona_action_required
            state: "None"
    action:
      - service: notify.mobile_app
        data:
          message: "Nivona needs attention: {{ states('sensor.nivona_action_required') }}"
```

---

## BLE pairing recovery

Symptoms of a wedged pairing: machine shows a red Bluetooth icon, logs show `HU handshake timeout`, ESPHome logs show `auth fail reason=82`.

### 1. Soft repair (automatic)

After 5 consecutive failed connects the reconnect loop automatically reloads the ESPHome proxy ConfigEntry. Manual trigger: **Devices & Services → Nivona NICR → Configure → Repair connection**.

### 2. Force re-pair (hard)

**Configure → Force re-pair**: disconnects client, calls `esphome.<proxy>_clear_ble_bonds`, disconnects the stuck peer, reloads the proxy entry, re-arms reconnect. **Put the machine into pairing mode before pressing Submit.**

### 3. Proxy factory reset

Press the **Factory reset** button on the proxy device card as a last resort. WiFi and OTA password survive (baked into firmware).

---

## Troubleshooting

**Machine not discovered**
- Verify Bluetooth is enabled on the machine.
- Ensure the HA host has a working BLE adapter (`bluetoothctl scan on`).
- Move the adapter or machine closer.

**Connection drops frequently**
- Use an ESPHome BLE proxy near the machine.
- Check logs for BLE errors.

**Enable debug logging**

```yaml
logger:
  default: info
  logs:
    nivona_nicr: debug
```

---

## Architecture

Three-layer abstraction:

1. **BLE transport** — pairing, reconnect, GATT write/notify.
2. **Eugster/EFLibrary core** — frame format `0x53…0x45`, one's-complement checksum, RC4 stream cipher, all opcodes (`HU/HV/HR/HW/HX/HE/HZ/HY/HD/HI`).
3. **Nivona brand profile** — RC4 key `NIV_060616_V10_1*9#3!4$6+4res-?3`, HU verifier table, advertisement regex, per-family capabilities.

---

## Removing the integration

1. **Settings → Devices & Services → Nivona NICR → ⋮ → Delete**
2. If installed via HACS: **HACS → Integrations → Nivona NICR → Uninstall**

---

## Localization

29 languages: English, Russian, Ukrainian, German, Polish, Czech, Slovak, French, Italian, Spanish, Portuguese, Dutch, Swedish, Danish, Norwegian, Finnish, Hungarian, Romanian, Greek, Turkish, Bulgarian, Croatian, Serbian, Slovenian, Bosnian, Macedonian, Estonian, Latvian, Lithuanian.

---

## Disclaimer

This project is an independent, open-source, non-commercial integration. It is **not affiliated with, endorsed by, or connected to Nivona Apparate GmbH, Eugster/Frismag AG**, or any of their subsidiaries.

"Nivona", "NICR", "NIVO", and the Nivona logo are registered trademarks of Nivona Apparate GmbH. All product names and logos are property of their respective owners and are used here solely for identification and interoperability purposes.

See [NOTICE](NOTICE) for full legal details.

---

## Contributing

Contributions are welcome. Open an issue or submit a pull request at [github.com/MaxSezin/nivona-barista-ha](https://github.com/MaxSezin/nivona-barista-ha).

## License

[MIT License](LICENSE)
