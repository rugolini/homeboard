#!/bin/sh
# Prints the router status homeboard reads. Install as a forced command so the dashboard key can run only this:
#   command="/usr/bin/homeboard-status.sh",no-port-forwarding,no-pty ssh-ed25519 AAAA... homeboard
# Tested on GL.iNet GL-X3000 (OpenWrt 21, kmwan). FIBER_DEV / MODEM_DEV override the uplink interfaces.

FIBER_DEV=${FIBER_DEV:-pppoe-wan}
MODEM_DEV=${MODEM_DEV:-rmnet_mhi0}

reach() {
	ping -I "$1" -c1 -W2 1.1.1.1 >/dev/null 2>&1 || ping -I "$1" -c1 -W2 8.8.8.8 >/dev/null 2>&1
}

json_bool() { if "$@"; then echo true; else echo false; fi; }

counters() {
	if [ -d "/sys/class/net/$1" ]; then
		printf '"%s": [%s, %s]' "$1" "$(cat /sys/class/net/$1/statistics/rx_bytes)" "$(cat /sys/class/net/$1/statistics/tx_bytes)"
	else
		printf '"%s": [0, 0]' "$1"
	fi
}

routes=$(ip route show default | awk '{dev=""; m=0; for (i=1;i<=NF;i++){if($i=="dev")dev=$(i+1); if($i=="metric")m=$(i+1)} if(dev!="") printf "%s{\"dev\": \"%s\", \"metric\": %d}", (n++?", ":""), dev, m}')
handshakes=$(wg show all latest-handshakes 2>/dev/null | awk '{printf "%s%s", (n++?", ":""), $3}')
leases=$(awk '{printf "%s\"%s\"", (n++?", ":""), $4}' /tmp/dhcp.leases 2>/dev/null)
assoc=""
for w in $(iwinfo 2>/dev/null | awk '/ESSID/{print $1}'); do
	assoc="$assoc${assoc:+, }\"$w\": $(iwinfo "$w" assoclist 2>/dev/null | grep -c dBm)"
done
signal=$(ubus call modem.signal get_signals '{"time":1}' 2>/dev/null | jsonfilter -e '@.signals[0]' 2>/dev/null)
uptime=$(ifstatus wan 2>/dev/null | jsonfilter -e '@.uptime' 2>/dev/null)

cat <<EOF
{"time": $(date +%s), "fiber_ok": $(json_bool reach "$FIBER_DEV"), "five_g_ok": $(json_bool reach "$MODEM_DEV"),
 "routes": [$routes], "wan_uptime": ${uptime:-null},
 "counters": {$(counters "$FIBER_DEV"), $(counters "$MODEM_DEV")},
 "modem": ${signal:-null}, "wg_handshakes": [$handshakes], "leases": [$leases], "assoc": {$assoc}}
EOF
