# Shelly Gen 1

**Indigo home automation plugin.**

Indigo plugin for older Shelly Gen 1 devices — relay and UNI ADC control over local HTTP. It is kept separate from ShellyDirect (Gen 2/3/4) so neither has to carry the other's protocol.

**Author:** CliveS & Claude
**Platform:** Indigo 2022.1 or later, macOS (Python 3.10+ bundled with Indigo)

*Developed and tested on Indigo 2025.2 / Python 3.13. Older Indigo releases that meet the minimum API version above should also work — the API floor is what Indigo's plugin loader actually checks.*
**Bundle ID:** `com.clives.indigoplugin.shellyg1`
**Version:** 1.5.0

---

## Features

- Talks to each Shelly straight over the local network with plain HTTP — no cloud account, no MQTT broker, nothing in between
- Polls every device every 30 seconds and keeps its Indigo state in step
- **Pulse Relay (2 seconds)** action — the relay closes and opens again on the Shelly's own timer, so a garage-door opener still gets its momentary contact even if Indigo is busy
- One quick retry before a device is called unreachable, and a device that has gone away is logged once on the way down and once on the way back rather than on every poll, so a flaky ESP8266 cannot flood the event log
- The Indigo error state clears itself when the device answers again
- Millisecond log timestamps, with a menu item to turn the prefix off

## Device types

| Indigo device type | Shelly hardware | What you get |
|--------------------|-----------------|--------------|
| **Shelly Relay (Gen 1)** (`shellyRelay`) | Shelly 1 and other Gen 1 relays | On, off and toggle from the standard Indigo controls, plus the Pulse Relay action |
| **Shelly UNI ADC (Gen 1)** (`shellyUniADC`) | Shelly UNI | The voltage on the UNI's analogue input as the device's display state — a car or leisure battery, say — with the time it was last read |

---

## Installation

1. Go to the [Releases page](https://github.com/Highsteads/ShellyGen1/releases) and download `ShellyGen1.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `ShellyGen1.indigoPlugin`
3. Double-click `ShellyGen1.indigoPlugin` — Indigo will install it automatically
4. In Indigo: **Plugins → Manage Plugins → Enable** Shelly Gen 1
5. Open **Plugins → Shelly Gen 1 → Configure** and fill in any required fields

---

## Credentials — `IndigoSecrets.py` vs `IndigoSecrets_example.py`

This plugin, like every CliveS Indigo plugin, reads sensitive values from one
shared master file:

`/Library/Application Support/Perceptive Automation/IndigoSecrets.py`

| File | Purpose | Real data? | Committed to GitHub? |
|------|---------|------------|----------------------|
| `IndigoSecrets.py` | Working file the plugin reads at runtime. Keep a backup in a password manager. | YES | **NO** — listed in `.gitignore` |
| `IndigoSecrets_example.py` | Template only — empty placeholders. Shipped in the plugin bundle. | NO | YES |

If you don't have `IndigoSecrets.py`, copy `IndigoSecrets_example.py` out of
the plugin bundle into `/Library/Application Support/Perceptive Automation/`,
rename it to `IndigoSecrets.py`, and fill in your values. Or skip the file
altogether and type the values into the plugin's configuration dialog — where
both are set, `IndigoSecrets.py` wins.

If neither source supplies a value the plugin needs, it logs an ERROR naming
the key and telling you to either fill in the matching field or add the key to
`IndigoSecrets.py`.

---

## Logging

Every log line carries a millisecond timestamp `[HH:MM:SS.mmm]`, so you can
line events up precisely against the other CliveS plugins — Device Activity
Monitor uses the same format.

To turn the prefix off, or back on, at any time:

**Plugins → Shelly Gen 1 → Toggle Timestamps in Log (on/off)**

The plugin stores the setting in `pluginPrefs` (`timestampEnabled`) and it
survives a restart. It defaults to ON.

---

## Repository structure

```
README.md                        ← this file (GitHub displays this)
ShellyGen1.indigoPlugin/
├── Contents/
│   ├── Info.plist
│   └── Server Plugin/
│       ├── plugin.py
│       └── ...
└── Contents/Server Plugin/IndigoSecrets_example.py   ← credential template
```

## Changelog

**v1.5.0** — New **Often Unpowered** setting on each device. A car that has driven off, or a plug switched off at the wall, is unreachable as its normal state — but every failed poll was logged as a warning. Tick the box and those become ordinary notes instead.

It quietens the log without hiding the device: it still shows as unreachable in the device list and still carries an error state, so anything watching device health can still see it.

**v1.4.3** — **Added the missing support link.** Every Indigo plugin is meant to carry a web address inside its bundle — it is what the "About" item in the Plugins menu opens. This one had the entry but left it blank, so that menu item went nowhere. It now points at this repository. Nothing else changed.

**v1.4.2** — Refreshed the shared helper the plugin logs through. Three things it fixes here: log lines no longer come out with two timestamps if the filter is installed twice, a log call with a mismatched placeholder keeps its arguments so you can still see what it was trying to say, and a saved setting holding the word "false" is now read as off rather than on.

**v1.4.1** — **Warnings and errors were logging as ordinary information.** The log helper passed the level through as a word where Indigo wanted a number, and a word is quietly ignored. Every warning and error the plugin raised had been appearing as a plain Info line, so the red and amber entries people rely on when something goes wrong never existed. They do now.

**v1.3** — A Shelly that misses one poll gets a second chance before the plugin calls it unreachable, and a device that stays away is logged once on the way down and once on recovery rather than on every poll. A flaky ESP8266 can no longer bury the event log. Error state clears by itself when the device comes back.

**v1.1** — Every log line now carries a millisecond timestamp, matching the other plugins here, with a menu item to turn it off.

Earlier releases are not recorded.

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
