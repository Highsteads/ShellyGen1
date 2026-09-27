---
title: How it works
nav_order: 4
---

# How it works

You do not need to know any of this to use the plugin. It is here for anyone who likes to know what is going on.

## Checking every 30 seconds

Every 30 seconds the plugin asks each Shelly how it is — whether a relay is on or off, or what voltage a UNI is reading — and brings Indigo up to date. If a Shelly does not answer, the plugin tries once more half a second later, because these older Shellys sometimes miss a question when they are busy.

A Shelly that misses one or two checks is not reported. Only after three missed checks in a row, about a minute and a half, is it shown as unreachable, because a Wi-Fi hiccup of a few seconds is common and is not a fault.

## Being told straight away

Waiting up to 30 seconds is fine for a voltage, but not for a light someone has just switched on at the wall. So each relay is set up to tell Indigo the moment it switches.

Every Gen 1 Shelly has a list of web addresses it will call when something happens to it — in the Shelly's own settings these are called **Actions**. When you add a relay, the plugin adds its own address to the relay's **switched on** and **switched off** actions. From then on, the relay calls Indigo the instant it switches, and Indigo shows the change within a second.

A few things are worth knowing about this:

- **Your own addresses are kept.** If you have put other addresses in those actions for something else, the plugin adds its own beside them and leaves yours alone. A Shelly action holds up to five addresses, and if one is full the plugin makes room and says in the log which address it removed.
- **Actions you have switched off are left off.** If one of those actions is switched off in the Shelly and holds someone else's addresses, the plugin does not turn it back on. It says so once in the log instead.
- **Only the relay itself is believed.** The plugin only accepts a call from the relay's own network address, so nothing else on the network can pretend to be your relay.
- **The 30-second checks carry on.** They are the backstop if a call ever goes astray.
- **It checks every six hours** that the relay's actions still point at Indigo, and puts them back if something has changed them.

If you switch this off in the plugin's settings, the plugin takes its address back out of every relay, and the relays are checked every 30 seconds as before.

## Knowing which Shelly is which

Your router hands out network addresses, and now and then it hands a Shelly a different one — after a power cut, say. If Indigo simply trusted the address, it could end up talking to the wrong Shelly, switching your porch light when you meant the garage.

So the plugin knows each Shelly by its **MAC address** — a number every network device is made with and never changes, a bit like a serial number. Each time it checks a Shelly, the Shelly reports that number, and the plugin makes sure it matches.

- **The first time**, the plugin records the number and says so in the Event Log.
- **If a different Shelly answers at that address**, nothing from it is recorded and no command is sent to it. The device shows **wrong device**, the log explains, and the plugin looks for the right Shelly on your network. If it finds it at a new address, it updates the device by itself and carries on.
- **If a Shelly simply stops answering**, the plugin also looks for it in case it has moved — unless it is marked **Often Unpowered**, because a Shelly in a car that has driven off has not moved, it is just not there.
- **It never moves a device onto an address another of your Shelly devices already uses.**
- **If you change a device's address yourself** in its settings, the plugin forgets the old number and learns the new Shelly's, because a new address means a different Shelly.
- **If you replace a Shelly with a new one** at the same address, the device shows **wrong device**, because the new one has a different number. Choose **Plugins → Shelly Gen 1 → Accept Replaced Shellys** and the plugin takes the new Shelly as the right one.

## Who switched it

Every time a relay switches, the Shelly records what switched it — its wall switch, its own timer, the Shelly app, starting up after a power cut, or a command over the network. The plugin turns that into the **Last Switched By** state, and knows which network commands came from Indigo because it sent them.

It only changes when the relay actually switches, so it still tells you who switched it last, however long ago that was.

## What goes in the log

The Indigo Event Log only shows things you might need to act on: a Shelly that stops answering and comes back, a wrong device, a setting that could not be made, and each relay pulse, because a pulse usually means a garage door has moved. Every on and off command is written to the plugin's own log file instead, so the Event Log does not fill up with them. The [Settings](settings.md) page shows how to have them in the Event Log as well.
