# Private HTTPS addresses

Every app on your server can have its own safe address that works from any of your devices, at home or away, with the padlock in the browser, and without opening anything on your router.

It uses Tailscale. Tailscale makes a private network between your own devices. An address like this one only opens for devices that are signed in to your Tailscale account, or devices you shared the server with:

```
https://your-server.your-network.ts.net:18096
```

The setup turns the port of each app into an address that is easy to remember: the port 8096 becomes 18096, 8989 becomes 18989, and so on.

## What you need

1. Tailscale installed and signed in on the server, and on every device you want to use.
2. HTTPS switched on once for your Tailscale account. In the Tailscale admin page open **DNS** and press **Enable HTTPS**. Nobody can do this for you, it is a setting of your account.

## Turn it on in the setup page

On the Apps and accounts step, switch on **Private HTTPS addresses**. If the tile says Tailscale is not ready, the setup was started without access to it. Install Tailscale on the server, then start the setup again.

The setup then:

1. Gives each of its apps an address and shows them on the final page.
2. Points every link in Homepage at those addresses.
3. Remembers each address, so it never changes.

## Use the tool without the setup page

The tool is one file with no extra programs needed. It works with any Docker containers, not only the ones from this setup.

```
python3 wizard/app/tailscale_https.py                 shows what it would do
python3 wizard/app/tailscale_https.py --apply         creates the missing addresses
python3 wizard/app/tailscale_https.py --apply --homepage /path/to/services.yaml
```

It looks at every container that shows a web page on a port of the server. It checks that the port really answers as a web page, and then gives it an address.

Things that are not web pages, such as file sharing and databases, are never touched.

The browser helper (FlareSolverr) is left out on purpose, because anyone who can reach it can misuse it.

Useful options:

| Option | What it does |
|---|---|
| `--skip name` | Leaves one container out. Separate several with commas. |
| `--extra name=port` | Adds an app that Docker cannot list, such as one on the host network. |
| `--loop 600` | Keeps running and checks again every 10 minutes, so new containers get an address by themselves. |
| `--homepage file` | Changes the links in a Homepage services.yaml. The comments and layout are kept, and a backup copy is saved first. |

## Keep your own list

You can also keep a small script of your own as the main list, so the ports are always the ones you chose. The tool at the end adds anything new. Running it again changes nothing that is already there.

```
#!/bin/bash
S="tailscale serve --bg"
$S --https=18096 http://localhost:8096 >/dev/null    # Jellyfin
$S --https=18989 http://localhost:8989 >/dev/null    # Sonarr
$S --https=10081 http://localhost:81   >/dev/null    # Homepage
# add your own lines here. Never use  tailscale serve reset
python3 /path/to/tailscale_https.py --apply --homepage /path/to/services.yaml
```

Run it from a schedule so it is repaired by itself, for example every 10 minutes.

## It never removes anything

The tool only adds addresses. It never resets the ones you have, so you can run it as often as you like, for example from a schedule:

```
*/10 * * * * python3 /path/to/tailscale_https.py --apply --homepage /path/to/services.yaml
```

It also remembers every address in a small file. If Tailscale is ever reset, running the tool puts them all back exactly as they were.

Do not run `tailscale serve reset` yourself. In a real test it took every address away for a minute.

It also removes entries that only you know about, such as a folder shared under a path, and those cannot be rebuilt automatically.

## Letting friends in

1. In the Tailscale admin page open **Machines**, find the server, and choose **Share**. Send them the link.
2. Then limit what they can reach. A shared machine lets them try every port on it. See the section on shared users in File sharing for an access rule that allows only what you want.

## Problems and fixes

| What happens | What to do |
|---|---|
| The tool says HTTPS is not turned on | Open the Tailscale admin page, then DNS, and press Enable HTTPS. |
| An address does not open | Check that the device is signed in to Tailscale, and that the app itself works on its normal port. |
| A new app has no address | Run the tool again. Containers that are stopped, or that do not answer as a web page, are skipped. |
| You want an app to have no address | Run it with `--skip name`. To remove an address that exists, run `tailscale serve --https=PORT off`, and delete that port from the small file the tool keeps in your home folder. |
| Homepage still shows the old links | Run the tool with `--apply --homepage` and the path of your services.yaml. Tiles need a `container:` line so the tool can tell which app each tile is. |
