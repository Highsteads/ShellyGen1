---
title: When something goes wrong
nav_order: 8
---

# When something goes wrong

Each section starts with what you see, then what it means and what to do.

## A device shows "unreachable"

The Shelly has not answered three checks in a row.

- Check it has power, and that its Wi-Fi light shows it is connected.
- Check its address in the Shelly app matches the one in the Indigo device.
- If it is often switched off on purpose, tick **Often Unpowered** in the device's settings. It will still show unreachable when away, but the log will not treat it as a fault.

When it answers again, the red clears by itself and the log says it is back.

## A device shows "wrong device"

A different Shelly is answering at this device's address. Nothing from it is recorded and no command is sent to it, so the wrong Shelly cannot be switched by mistake.

- If your router has moved the Shelly to a new address, the plugin looks for it and updates the device itself — give it a minute.
- If you have replaced the Shelly with a new one, choose **Plugins → Shelly Gen 1 → Accept Replaced Shellys**.
- If you copied a device and gave the copy the same address as the original, give the copy its own Shelly's address.

## Switching at the wall takes up to 30 seconds to show

The relay is not telling Indigo straight away.

- Check **Instant Updates from Relays** is ticked in **Plugins → Shelly Gen 1 → Configure**.
- Check **Indigo Server IP** there is the address of the Mac that runs Indigo.
- Look in the Event Log for a line saying the relay **now tells Indigo the moment it switches**, or one saying a setting could not be made.
- If the log says an action is switched off and holds other addresses, open the Shelly's own web page, go to **Actions**, and either clear that action or switch it on.

## The log says "could not listen for push updates on port 8179"

Something else on the Mac is already using that port. Choose another number, such as 8180, in **Listening Port** and click Save. The relays are pointed at the new number by themselves.

## A Pulse Relay action does nothing, or says it is not configured

Open the action and click **OK** once. Actions made before version 1.6 need this so Indigo stores the number of seconds.

## Last Switched By says "another app on the network"

Something other than Indigo sent the Shelly a command over the network — the Shelly's own web page, a script, or another home system. That is the Shelly's own record of what happened.

## Still stuck?

Choose **Plugins → Shelly Gen 1 → Show Plugin Info**, copy the lines it writes to the Event Log, and post them on the [Indigo forum](https://forums.indigodomo.com) with a description of what you see. You can also [raise an issue on GitHub](https://github.com/Highsteads/ShellyGen1/issues).
