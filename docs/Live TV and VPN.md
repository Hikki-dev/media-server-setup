# Live TV and NordVPN

## What NordVPN adds

Some free channels, like UK children's channels and many US channels, refuse to play outside their own country. With NordVPN the setup tries those channels through a UK connection and a US connection. It keeps the ones that work and checks again every day. Only those channels use the VPN. Everything else plays normally.

You need a NordVPN service login. This is not your normal NordVPN login. You find it in your NordVPN account page, under the manual setup section. Channels through the VPN start a few seconds later.

## In the setup

On the Live TV step, turn on NordVPN and paste the service username and password. Your login is saved in a private file on your own computer and is never put in any other file.

## If you already have a server running

Open the folder called NordVPN inside Extras. Run the file Start NordVPN there once, type your service login when asked, and it starts the two connections for you.

## If a channel stops working

1. Check that both NordVPN connections show as healthy in Docker Desktop.
2. If one is unhealthy, restart it. It will pick another NordVPN server.
3. Some channels only work for part of the day, or only when a match is on.
