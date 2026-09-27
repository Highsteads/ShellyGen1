---
title: Getting started
nav_order: 2
---

# Getting started

This takes about five minutes, and you only do it once.

## What you need

- Indigo 2022.1 or later, on a Mac that is on the same home network as your Shellys.
- One or more Shelly Gen 1 devices already joined to your Wi-Fi, which you do with the Shelly app or the Shelly's own web page when you first unbox it.
- The **network address** of each Shelly. This is the set of four numbers separated by dots, such as `192.168.1.20`, that the Shelly app shows under the device's settings. Your router's list of connected devices shows it too.

It helps a great deal to ask your router to keep giving each Shelly the same address, which most routers call a **reserved address** or **DHCP reservation**. The plugin copes if an address changes, but it copes faster if it never does.

## 1. Install the plugin

1. Go to the [Releases page](https://github.com/Highsteads/ShellyGen1/releases/latest) and download `ShellyGen1.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `ShellyGen1.indigoPlugin`
3. Double-click `ShellyGen1.indigoPlugin` — Indigo will install it automatically

Indigo asks whether to enable the plugin. Say yes.

## 2. Tell the plugin where Indigo is

Open **Plugins → Shelly Gen 1 → Configure**.

The one thing to fill in is **Indigo Server IP** — the network address of the Mac that runs Indigo. Your relays use it to tell Indigo the moment they switch. You can find it in **System Settings → Network** on that Mac, or in your router's list of devices.

Leave everything else as it is to start with, and click **Save**. Every setting is explained on the [Settings](settings.md) page.

## 3. Add a Shelly

1. In Indigo, choose **New Device**.
2. Set **Type** to **Shelly Gen 1**, then pick the model:
   - **Shelly Relay (Gen 1)** for a Shelly 1 or another relay
   - **Shelly UNI ADC (Gen 1)** for a Shelly UNI whose voltage input you want to read
3. Type the Shelly's network address into **IP Address**.
4. Tick **Often Unpowered** only if the Shelly is away or switched off much of the time, like one in a car. The [Settings](settings.md) page explains what it changes.
5. Click **Save**.

## 4. Check it works

Within a few seconds the new device shows its state in Indigo's device list — on or off for a relay, a voltage for a UNI. The Indigo Event Log has a line saying the plugin has recorded the Shelly's identity, and for a relay another saying it now tells Indigo the moment it switches.

Now switch the relay with its wall switch or the Shelly app. Indigo should show the change within a second.

If nothing appears, the [When something goes wrong](troubleshooting.md) page goes through the usual causes.
