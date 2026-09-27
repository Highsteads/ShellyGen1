---
title: Settings
nav_order: 6
---

# Settings

## The plugin's settings

Open these with **Plugins → Shelly Gen 1 → Configure**. They apply to every Shelly.

| Setting | What it does |
|---|---|
| **Instant Updates from Relays** | Ticked, each relay tells Indigo the moment it switches. Unticked, the plugin takes its address back out of every relay and relies on the 30-second checks. It is ticked to start with, and a change takes effect as soon as you click Save. |
| **Indigo Server IP** | The network address of the Mac that runs Indigo, such as `192.168.1.5`. The relays call this address when they switch. Without it the relays still work, they just are not instant. |
| **Listening Port** | The port number on that Mac that the relays call, 8179 to start with. Only change it if something else on the Mac already uses 8179. My Shelly Direct plugin uses 8178, so the two can run together. |
| **Debug Logging** | Adds a line to the Event Log for every reading the plugin takes. Only useful when chasing a problem, as it adds a lot of lines. |
| **Show Device Activity in the Indigo Event Log** | Every on and off command is always written to the plugin's own log file. Tick this to see them in the Indigo Event Log as well. Warnings, errors and relay pulses always appear there whatever this is set to. |

### Keeping the server address in one file

If you run several of my plugins, you can keep the Indigo server's address in one shared file instead of typing it into each plugin. The file is called `IndigoSecrets.py` and lives in `/Library/Application Support/Perceptive Automation/`. A blank copy, `IndigoSecrets_example.py`, comes inside the plugin — copy it to that folder, rename it `IndigoSecrets.py`, and fill in the line `INDIGO_SERVER_IP = "192.168.1.5"` with your own address.

When the file has the address, it is used, whatever the Configure box says. This plugin needs nothing else from the file.

## Each device's settings

Open these by double-clicking a Shelly device in Indigo.

| Setting | What it does |
|---|---|
| **IP Address** | The Shelly's network address. It must be a real address, and no other Shelly device of the same kind can use it. If you change it, the plugin learns the new Shelly's identity, as [How it works](how-it-works.md) explains. |
| **Often Unpowered** | Tick this for a Shelly that is away or switched off much of the time — in a car, or on a plug that is switched off at the wall. When it does not answer, the Event Log says so as an ordinary note rather than a warning, and the plugin does not go looking for it on the network. It still shows as unreachable in the device list, so anything that watches for failed devices can still see it. |
