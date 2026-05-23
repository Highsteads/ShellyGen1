# Shelly Gen 1

**Indigo home automation plugin.**

Indigo plugin for Shelly Gen 1 legacy devices — basic relay and UNI ADC support over local HTTP, kept separate from ShellyDirect (Gen 2/3/4) for clarity

**Author:** CliveS & Claude Sonnet 4.6
**Platform:** Indigo 2022.1 or later, macOS (Python 3.10+ bundled with Indigo)

*Developed and tested on Indigo 2025.2 / Python 3.13. Older Indigo releases that meet the minimum API version above should also work — the API floor is what Indigo's plugin loader actually checks.*
**Bundle ID:** `com.clives.indigoplugin.shellyg1`
**Version:** 1.0

---

## Installation

1. Go to the [Releases page](https://github.com/Highsteads/ShellyGen1/releases) and download `ShellyGen1.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `ShellyGen1.indigoPlugin`
3. Double-click `ShellyGen1.indigoPlugin` — Indigo will install it automatically
4. In Indigo: **Plugins → Manage Plugins → Enable** Shelly Gen 1
5. Open **Plugins → Shelly Gen 1 → Configure** and fill in any required fields

---

## Credentials — `IndigoSecrets.py` vs `IndigoSecrets_example.py`

This plugin (along with all CliveS Indigo plugins) reads sensitive values from
a shared master credentials file at:

`/Library/Application Support/Perceptive Automation/IndigoSecrets.py`

| File | Purpose | Real data? | Committed to GitHub? |
|------|---------|------------|----------------------|
| `IndigoSecrets.py` | Working file the plugin reads at runtime. Keep a backup in a password manager. | YES | **NO** — listed in `.gitignore` |
| `IndigoSecrets_example.py` | Template only — empty placeholders. Shipped in the plugin bundle. | NO | YES |

If you do not have `IndigoSecrets.py`, copy `IndigoSecrets_example.py` from
the plugin bundle to that location and fill in your values. Or skip
`IndigoSecrets.py` entirely and enter values via the plugin's configuration
dialog — `IndigoSecrets.py` wins over the dialog when both are set.

If a required value is set in NEITHER source the plugin logs an ERROR
pointing the user to either fill in the matching field or add the key to
`IndigoSecrets.py`.

---

## Logging

Every log line is prefixed with a millisecond timestamp `[HH:MM:SS.mmm]` so
events can be correlated tightly with other CliveS plugins (Device Activity
Monitor uses the same convention).

To turn the prefix off (or back on) at any time:

**Plugins → Shelly Gen 1 → Toggle Timestamps in Log (on/off)**

The setting is stored in `pluginPrefs` (`timestampEnabled`) and persists across
restarts. Defaults to ON.

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

---

## License

GPL-3.0 — see plugin source files for details.
