---
title: Your devices
nav_order: 3
---

# Your devices

Each Shelly you add becomes one Indigo device. This page explains what each one shows.

## Shelly Relay (Gen 1)

For a Shelly 1, or any other Gen 1 Shelly with a relay that switches something on and off.

You control it with Indigo's usual **Turn On**, **Turn Off** and **Toggle**, from the device list, a control page, a schedule, a trigger or an action group.

What it shows in Indigo:

| Shown as | What it means |
|---|---|
| **On / Off** | Whether the relay is on or off right now. It changes the moment the relay switches, however it was switched. |
| **Last Switched By** | Who or what switched it last: **Indigo**, **the switch wired to the device**, **the Shelly app**, **the device's own timer**, **the device starting up** (after a power cut), or **another app on the network** (anything else that sent it a command). If the Shelly ever reports something the plugin does not know, it is shown in quotes, as the Shelly gave it. |

## Shelly UNI ADC (Gen 1)

For a Shelly UNI, reading the voltage on its analogue input. I use one to watch the 12 volt battery in the car, so I know when it is getting low.

What it shows in Indigo:

| Shown as | What it means |
|---|---|
| **Voltage** | The voltage the UNI measured, to two decimal places. This is what the device list shows. |
| **Last Update** | The date and time of the last reading, such as `27-09-2026 09:15:04`. If the Shelly is away — the car is out, say — this tells you how old the voltage is. |

The UNI's voltage is read every 30 seconds. SQL Logger keeps a history of the voltage but not of the Last Update time, which would only fill the history with a row every 30 seconds for no benefit.

## When a Shelly cannot be reached

If a Shelly misses three checks in a row, about a minute and a half, the device shows **unreachable** in red in the device list, and the Event Log has one line saying so. When it answers again the red clears and the log says it is back.

If the device is marked **Often Unpowered**, the same thing happens, but the log line is an ordinary note rather than a warning — it is still shown as unreachable, so anything that watches for failed devices still sees it.

If a different Shelly is answering at the device's address, the device shows **wrong device** in red. The [How it works](how-it-works.md) page explains why, and what happens next.
