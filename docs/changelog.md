---
title: Version history
nav_order: 9
---

# Version history

The newest version is at the top.

## 1.6.1 — 27 September 2026

Fixes from an independent review of 1.6.0.

- **A copied device no longer ends up controlling the original's Shelly.** Giving a device a new address clears the Shelly it was tied to, two devices of the same kind cannot share an address, and the search for a lost Shelly never moves a device onto another device's address.
- **Last Switched By holds.** It only changes when the relay switches, and a switch made by Indigo shows as Indigo.
- **A replaced Shelly can be accepted** with **Plugins → Shelly Gen 1 → Accept Replaced Shellys**. Before, a new Shelly at the same address was refused for good.
- **Changes to the instant-update settings take effect as soon as you click Save,** and switching instant updates off takes the plugin's address back out of every relay, leaving anyone else's.
- **An action you switched off in a Shelly stays off,** and a full action says in the log which address it removed.
- **A switch at the wall can no longer be undone by an older reading** arriving a moment later, and a disabled device ignores calls from its relay.

## 1.6.0 — 27 September 2026

- **Relays tell Indigo the moment they switch,** so a change at the wall or in the Shelly app shows within a second instead of within 30 seconds.
- **Each Shelly is known by the number it was made with,** so a Shelly given a new address by the router is found again, and a different Shelly at the same address is never switched by mistake.
- **Last Switched By** shows who switched each relay, and a new **Switched Outside Indigo** trigger runs when anything but Indigo switches it.
- **Pulse Relay has a length in seconds.** Actions made before this version pulse for two seconds until you open them and click OK.

## 1.5.3 — 27 September 2026

- The plugin keeps checking your Shellys even if one of them causes an error. Before, one error could stop all checking until the plugin was restarted.
- A Shelly that is away no longer holds up Indigo when the plugin starts.
- **Send Status Request** works on a relay. It used to do nothing.
- After a pulse, Indigo shows the relay off again as soon as it switches off, rather than up to 30 seconds later.
- The device settings insist on a real network address, and a device without one says so once, not every 30 seconds.
- A Shelly is only called unreachable after three missed checks in a row. One flaky garage light had logged five warnings in 25 minutes, each time answering again 30 seconds later.
- Every on and off goes to the plugin's own log, with a setting to show them in the Event Log as well.
- **Last Update** shows the date as well as the time.

## 1.5.2 — 23 September 2026

A voltage reading is saved as one row in SQL Logger's history, not two. Before, the time of each reading was saved as a separate row every 30 seconds. The voltage history is exactly as before.

## 1.5.1 — 11 September 2026

The plugin carries a note of where its code lives on GitHub, the same way other Indigo plugins do. Nothing else changed.

## 1.5.0 — 15 August 2026

New **Often Unpowered** setting for a Shelly that is away or switched off much of the time, such as one in a car. Its absence is logged as an ordinary note rather than a warning, and it still shows as unreachable in the device list.

## 1.4.3 — 8 August 2026

The **About** item in the Plugins menu opens this project's page. It went nowhere before.

## 1.4.2 — 21 July 2026

Log lines no longer come out with the time printed twice, and a setting saved as the word "false" is read as off.

## 1.4.1 — 21 July 2026

Warnings and errors appear in the Event Log as warnings and errors. Before, they all appeared as ordinary lines.

## 1.3 — 29 May 2026

A Shelly that misses one check gets a second chance before it is called unreachable, and a Shelly that stays away is logged once when it goes and once when it comes back, rather than on every check.

## 1.1 — 23 May 2026

Every log line starts with the time to the thousandth of a second, with a menu item to turn that off.

Earlier versions are not recorded.
