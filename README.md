# Shelly Gen 1 for Indigo

**Switch and watch the older Shelly devices from Indigo, straight over your home network.**

**Version:** 1.7.0 | **Author:** CliveS & Claude | **Needs:** Indigo 2022.1 or later

**[Read the full guide](https://highsteads.github.io/ShellyGen1/)** — setting up, what everything means, and what to do when something goes wrong.

---

## What it does

This plugin lets [Indigo](https://www.indigodomo.com) control the Shelly devices Shelly now calls **Gen 1**. It talks to each one directly over your home network, so there is no Shelly account involved and nothing goes out to the internet.

- **Switches Shelly relays** on and off from Indigo, a control page, a schedule or a trigger, the same as any other Indigo device.
- **Shows the change within a second** when someone uses the wall switch or the Shelly app, because each relay tells Indigo the moment it switches.
- **Tells you who switched it** — Indigo, the wall switch, the Shelly app, the relay's own timer, or the relay starting up after a power cut — and can run a trigger when anything other than Indigo switches it.
- **Pulses a relay** on for the number of seconds you choose and off again, which is what most garage door openers need. The Shelly does the timing, so it switches off on time even if Indigo is busy.
- **Reads the voltage on a Shelly UNI** every 30 seconds, with the date and time of the reading. I use it to watch the car's 12 volt battery.
- **Knows each Shelly by the number it was made with,** so if your router gives a Shelly a new address the plugin finds it again, and it never switches the wrong one.
- **Keeps the log tidy.** A Shelly has to miss three checks in a row before it is reported, and one that is often switched off, like a Shelly in a car, can be marked so its absence is not treated as a fault.

## Which Shellys it works with

| In Indigo | Your Shelly |
|---|---|
| **Shelly Relay (Gen 1)** | A Shelly 1, or any other Gen 1 Shelly with a relay |
| **Shelly UNI ADC (Gen 1)** | The voltage input on a Shelly UNI |

For the newer Plus, Pro, Gen 3 and Gen 4 Shellys, use my other plugin, [Shelly Direct](https://github.com/Highsteads/ShellyDirect).

## Installing

1. Go to the [Releases page](https://github.com/Highsteads/ShellyGen1/releases/latest) and download `ShellyGen1.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `ShellyGen1.indigoPlugin`
3. Double-click `ShellyGen1.indigoPlugin` — Indigo will install it automatically

## Setting it up

1. Open **Plugins → Shelly Gen 1 → Configure**, fill in **Indigo Server IP** with the network address of the Mac that runs Indigo, and click **Save**. The relays use it to tell Indigo when they switch.
2. Create a **New Device**, choose **Shelly Gen 1** and the model, and type in the Shelly's network address — the four numbers, such as `192.168.1.20`, that the Shelly app shows.
3. Switch the relay at the wall or in the Shelly app, and Indigo should show the change within a second.

The [full guide](https://highsteads.github.io/ShellyGen1/) goes through each step, explains every setting, and covers what to do if something does not work.

## What's new

**v1.7.0** — A Shelly that has stopped answering stays marked **unreachable** until the plugin has heard from it properly again. Switching it at the wall, or from Indigo, used to clear the mark, so anything watching for failed devices could miss it. A different Shelly found at a device's address goes back to showing **wrong device** after a spell of not answering, rather than **unreachable**.

**v1.6.1** — Fixes from an independent review of 1.6.0.
- A copied device no longer ends up controlling the original's Shelly.
- **Last Switched By** only changes when the relay switches, and a switch made by Indigo shows as Indigo.
- **Plugins → Shelly Gen 1 → Accept Replaced Shellys** takes a new Shelly fitted at the same address as the right one.
- Changes to the instant-update settings take effect as soon as you click Save.
- An action you switched off in a Shelly stays off.

Every version is listed in the [version history](https://highsteads.github.io/ShellyGen1/changelog.html).

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
