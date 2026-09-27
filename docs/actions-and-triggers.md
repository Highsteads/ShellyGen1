---
title: Actions and triggers
nav_order: 5
---

# Actions and triggers

## Switching a relay

A Shelly relay answers Indigo's standard **Turn On**, **Turn Off** and **Toggle**, wherever you use them — a control page, a schedule, a trigger or an action group. **Send Status Request** asks the Shelly for its state there and then, rather than waiting for the next check.

If the plugin cannot reach the Shelly, the command is tried once more, and if that fails too, the Event Log says the command was not delivered.

## Pulse Relay

**Pulse Relay** switches a relay on and switches it off again after the number of seconds you choose. The Shelly does the timing itself, so the relay still switches off on time even if Indigo is busy or the network drops for a moment.

It is what most garage door openers need — they want a short press of their button, not a switch left on.

To use it, add an action and choose **Device Actions → Pulse Relay**, pick the relay, and set **Seconds**. Two seconds suits most openers. You can use anything from half a second to an hour.

As soon as the relay switches off again, Indigo shows it off.

If you made a Pulse Relay action with a version before 1.6, open it once and click **OK**, so Indigo stores the number of seconds. Until you do, it pulses for two seconds, as it always did.

## Switched Outside Indigo

This trigger runs when a relay switches and Indigo did not switch it — someone used the wall switch or the Shelly app, the relay's own timer ran out, or it came back on after a power cut.

To use it, create a new trigger, set its type to **Shelly Gen 1 → Switched Outside Indigo**, and choose a relay, or **Any Relay**. Then add whatever you want to happen.

For example, if someone switches the garage lights on at the wall, you could have Indigo switch them off again after half an hour.

The relay's **Last Switched By** state tells you what switched it, if your action needs to know.
