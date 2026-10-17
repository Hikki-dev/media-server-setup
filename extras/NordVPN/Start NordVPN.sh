#!/bin/bash
# Asks for your NordVPN service login (in your Nord account: NordVPN, then Manual setup, then Service credentials),
# saves it where only you can read it, starts the UK and US connections and checks that they connect.
set -u
cd "$(dirname "$0")" || { echo "The folder is missing"; exit 1; }
read -r -p "NordVPN service username: " U
read -r -s -p "NordVPN service password (hidden): " P; echo
[ -n "$U" ] && [ -n "$P" ] || { echo "Both are needed."; exit 1; }
umask 077
printf "OPENVPN_USER='%s'\nOPENVPN_PASSWORD='%s'\n" "$U" "$P" > nord.env
rm -f nord.ok
echo "Starting the VPN connections. The first time it downloads the server list, about a minute."
docker compose up -d >/dev/null 2>&1 || { echo "Docker could not start the connections"; exit 1; }
for i in $(seq 1 30); do
  sleep 6
  out=$(docker exec regional python3 -c "import urllib.request,json;print(json.dumps(json.loads(urllib.request.urlopen('http://localhost:9120/vpn/status',timeout=40).read())['exits']))" 2>/dev/null)
  echo "$out" | grep -q '"uk": {"ip"' && echo "$out" | grep -q '"us": {"ip"' && { echo "Connected: $out"; touch nord.ok; echo "Done. Tell Claude it is connected."; exit 0; }
done
echo "Not connected yet. Last status: $out"
echo "Open Docker Desktop and look at the logs of gluetun uk. A wrong username or password shows as a login error."
exit 1
