---
title: Home
nav_order: 1
---

# Shelly Gen 1 for Indigo

This plugin lets [Indigo](https://www.indigodomo.com) switch and watch the older Shelly devices, the ones Shelly now calls **Gen 1**, straight over your home network. There is no Shelly account involved, nothing goes out to the internet, and nothing sits in between — Indigo talks to each Shelly directly.

It looks after two kinds of Shelly:

- **A Shelly relay**, such as the Shelly 1, which switches something on and off — a light, a pump, a garage door opener.
- **A Shelly UNI's voltage input**, which I use to keep an eye on the car's 12 volt battery, but which will read any small voltage you wire to it.

If your Shellys are the newer Plus, Pro, Gen 3 or Gen 4 models, you want my other plugin, [Shelly Direct](https://github.com/Highsteads/ShellyDirect), instead.

## What it does for you

- **Switches your relays** from Indigo, from a control page, from a schedule or from a trigger, the same way you switch any other Indigo device.
- **Shows the change straight away** when someone uses the switch on the wall or the Shelly app, because the relay tells Indigo the moment it switches.
- **Tells you who switched it** — Indigo, the wall switch, the Shelly app, the relay's own timer, or the relay starting up again after a power cut.
- **Pulses a relay** on for a few seconds and off again, which is what most garage door openers need.
- **Reads the UNI's voltage** every 30 seconds, with the date and time of the last reading.
- **Knows each Shelly by the number it was made with**, so if your router gives a Shelly a new address the plugin finds it again, and it never switches the wrong one.
- **Keeps your log tidy** — a Shelly that misses a check or two is not reported as broken, and one that is often switched off, like a plug on a car charger, can be marked so its absence is not treated as a fault.

## Where to go next

| If you want to... | Read |
|---|---|
| Install the plugin and add your first Shelly | [Getting started](getting-started.md) |
| Know what each device shows in Indigo | [Your devices](devices.md) |
| Understand what the plugin is doing behind the scenes | [How it works](how-it-works.md) |
| Switch things from triggers, schedules and action groups | [Actions and triggers](actions-and-triggers.md) |
| Know what every setting does | [Settings](settings.md) |
| Know what each item in the Plugins menu does | [The plugin menu](plugin-menu.md) |
| Sort out a problem | [When something goes wrong](troubleshooting.md) |
| See what changed in each version | [Version history](changelog.md) |

## Download

The latest version is always on the [Releases page](https://github.com/Highsteads/ShellyGen1/releases/latest).
