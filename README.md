# Shelly Gen 1

**Indigo home automation plugin.**

Indigo plugin for older Shelly Gen 1 devices — relay and UNI ADC control over local HTTP. It is kept separate from ShellyDirect (Gen 2/3/4) so neither has to carry the other's protocol.

**Author:** CliveS & Claude
**Platform:** Indigo 2022.1 or later, macOS (Python 3.10+ bundled with Indigo)

*Developed and tested on Indigo 2025.2 / Python 3.13. Older Indigo releases that meet the minimum API version above should also work — the API floor is what Indigo's plugin loader actually checks.*
**Bundle ID:** `com.clives.indigoplugin.shellyg1`
**Version:** 1.6.1

---

## Features

- Talks to each Shelly straight over the local network with plain HTTP — no cloud account, no MQTT broker, nothing in between
- Relays tell Indigo the moment they switch, and every device is also polled every 30 seconds as a backstop
- Each device is known by its MAC address, so a DHCP change or another Shelly on its old address cannot mix them up
- **Pulse Relay** action — the relay closes and opens again after the number of seconds you choose, on the Shelly's own timer, so a garage-door opener still gets its momentary contact even if Indigo is busy
- **Last Switched By** state and a **Switched Outside Indigo** trigger
- One quick retry, and three missed checks in a row, before a device is called unreachable; a device that has gone away is logged once on the way down and once on the way back rather than on every poll, so a flaky ESP8266 cannot flood the event log
- The Indigo error state clears itself when the device answers again
- Millisecond log timestamps, with a menu item to turn the prefix off

## Device types

| Indigo device type | Shelly hardware | What you get |
|--------------------|-----------------|--------------|
| **Shelly Relay (Gen 1)** (`shellyRelay`) | Shelly 1 and other Gen 1 relays | On, off and toggle from the standard Indigo controls, the Pulse Relay action, instant updates, and who last switched it |
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

**v1.6.1** — **Fixes from an independent review of 1.6.0.**
- **A copied device no longer goes back to the original's Shelly.** Giving a device a new address in its dialog now clears the Shelly it was tied to, two devices of the same kind cannot share an address, and the search for a lost device never moves it onto another device's address.
- **Last Switched By holds.** It is only updated when the relay actually switches, and it said "another app" half a minute after every command from Indigo before.
- **A replaced Shelly can be accepted** from Plugins -> Shelly Gen 1 -> Accept Replaced Shellys. Before, a new unit at the same address was refused for good.
- **Push settings apply straight away,** with no reload, and switching push off takes the plugin's addresses back off the relays while keeping anyone else's.
- **Actions you switched off in the Shelly are left alone,** and a full action says which address it dropped.
- **A switch at the wall can no longer be overwritten by an older reading** arriving a moment later, and a disabled device ignores pushes.

**v1.6.0** — **New features from the review.**
- **Instant updates from relays.** Each relay is set to tell Indigo the moment it switches, so a change at the wall switch or in the Shelly app shows straight away instead of within 30 seconds. The plugin adds its own address to the relay's on and off actions and keeps any others you have set there. A push is only believed if it comes from that relay's own address. Set the Indigo Server IP in the plugin settings, or INDIGO_SERVER_IP in IndigoSecrets.py.
- **Each device is known by its MAC address.** If another Shelly takes a device's address, the plugin records nothing from it and sends it no commands, says so once, and looks for the right device on the network. If it finds it at a new address it updates the device itself. A device marked Often Unpowered is never searched for just for being away.
- **Last Switched By.** Each relay has a new state saying who last switched it: Indigo, the switch wired to it, the Shelly app, its own timer, or the device starting up after a power cut. A new **Switched Outside Indigo** trigger fires when anything but Indigo changes it.
- **Pulse Relay has a length.** Set how many seconds in the action. If you made a Pulse Relay step with an earlier version, open it and click OK once so Indigo stores the new setting; until then it pulses for 2 seconds as before.

**v1.5.3** — **A full review, and the fixes that came out of it.**
- **Polling keeps going whatever happens.** One unexpected error used to stop all polling until the plugin was restarted.
- **A device that is away no longer holds up start-up.** The first check now runs in the background.
- **Send Status Request works on a relay.** It used to do nothing.
- **After a pulse, Indigo shows the relay off again as soon as it opens,** rather than up to 30 seconds later.
- **The device dialog insists on a real IP address,** and a device without one says so once instead of every 30 seconds.
- **A device is only called unreachable after three missed checks in a row,** about a minute and a half. A single missed check used to raise a warning, and one flaky garage light raised five in 25 minutes, each back 30 seconds later.
- **Each on and off goes to the plugin's own log,** with a tick box in the settings to show them in the Indigo Event Log as well. Warnings, errors and relay pulses always appear there.
- **Last Update shows the date as well as the time,** so a reading taken days ago no longer looks current.

**v1.5.2** — **A voltage reading is now one history row, not two.** Every 30 seconds the UNI voltage monitor saved its voltage and the time of the reading as two separate updates, so SQL Logger kept two rows for each reading, one of them holding nothing but the time. The reading now goes in as a single update, and the plugin tells SQL Logger to skip the time altogether. The voltage history is exactly as before, anything you already told SQL Logger to skip is kept, and existing history is untouched.

**v1.5.1** — **The bundle now carries the standard GitHub record.** Indigo plugins can carry a small note inside the bundle saying where their source lives on GitHub, spelt the way the Indigo Domotics and community plugins spell it. This one now has it, pointing at this repository. Nothing else changed.

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
