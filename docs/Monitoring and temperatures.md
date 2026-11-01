# Monitoring and temperatures

Beszel watches your server and tells you when something is really wrong. It shows processor use, memory, how full each drive is, every app's use, and the temperature of the processor. It is optional: turn on **Beszel** in the list of extras.

## What the setup does for you

1. It starts two small apps: the page you open (the hub) and a helper that measures this machine (the agent).
2. It adds this server to the hub, so there is nothing to connect by hand.
3. It adds a tile with live numbers to your Homepage.
4. It sizes everything to your machine, as the next section shows.
5. It sets up alerts that only ring for real trouble.

Sign in with the email `admin@beszel.local` and the password you chose for the setup. If that password is shorter than 8 characters, a longer one is made from it, and the last screen shows it.

## It adapts to your hardware

| What it looks at | What it does with it |
|---|---|
| Memory of the machine | Small caps for the monitor on a small machine: 256 MB for the hub and 96 MB for the helper at 4 GB or less, up to 512 MB and 192 MB above 16 GB. |
| Number of cores | A machine with 2 cores or fewer gives the hub a quarter of a core, others half. |
| Your media drives | Each drive is watched, so you see how full every one is, not only the system drive. |
| Temperature sensors | If the processor reports a temperature, a temperature alert is added. If not (a virtual machine, Windows and Mac), there is none. |
| The processor's own limit | The temperature alert is set 8 degrees under the limit the chip reports, at most 95. |

Windows and Mac run Docker inside a hidden virtual machine, so there the monitor sees that machine and not the real chip. Temperatures and the drive list only work on Linux. On a Proxmox setup, put the helper on the Proxmox host to see the real temperature (see below).

## When you are pinged

Alerts only fire when a number stays bad for a while, so a short spike never rings:

| Alert | Fires when | For how long |
|---|---|---|
| Status | The server stops answering | 5 minutes |
| CPU | Above 90% | 10 minutes |
| Memory | Above 90% | 10 minutes |
| Disk | Above 90% | 10 minutes |
| Temperature | 8 degrees under the chip's limit (92 C for a chip that stops at 100 C) | 10 minutes |

To get them on your phone, open Beszel, then Settings, then Notifications, and add a Discord, Telegram, Slack or email address. Do not add an alert at a number your machine reaches on a normal day: a laptop that idles at 80 C and has a 80 C alert will ping every few minutes all day. If you get pings you do not care about, raise that number, do not mute everything.

## If it runs hot

An idle server above 75 C is a cooling problem, not a software problem. Check these in order:

1. **Look at the load.** If the processor is nearly idle and the temperature is still high, no setting will fix it.
2. **Clean the fan and the metal fins.** Dust blocks them. Blow it out with compressed air.
3. **Replace the thermal paste** if the machine is more than three years old. It dries out.
4. **Give it air.** A hard surface, space around it, and not inside a cupboard.
5. **Lower the power** as a last step. It lowers the heat, and the speed of your apps with it.

### Thermal guard (Linux, optional)

A small program that lowers the processor's power and speed when it runs hot, and puts them back when it has cooled. It works out the sensor, the chip's limit and the power it may use by itself:

| Level | Starts at | Power | Speed |
|---|---|---|---|
| 1 | limit minus 15 C | 65% | 100% |
| 2 | limit minus 10 C | 45% | 60% |
| 3 | limit minus 5 C | 30% | 30% |

It goes back one level after cooling 7 degrees under the one that started it. Install it as root on the machine that runs hot (on a Proxmox setup, on the Proxmox host, not in the container):

```bash
sudo bash "extras/Monitoring/Install thermal guard.sh"
```

It checks for a sensor first and tells you if there is none. Watch it with `journalctl -u thermal-guard -f`. Stopping it puts the normal settings back.

## The helper on a Proxmox host

The helper inside the stack sees the container. To see the real chip, install the Beszel agent on the Proxmox host as well, then add the host in the hub with its address. Beszel's own page for the agent has the one-line install. Turn on the sensors with `sensors-detect` if `sensors` shows nothing.

## Changing things later

Everything can be changed in Beszel itself: the alerts, who is notified, which systems are shown. The setup never overwrites your changes when you run it again; it only adds what is missing.
