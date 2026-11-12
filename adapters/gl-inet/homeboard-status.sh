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
# Per-client counters from the GL firmware; MACs and per-second history stay on the router.
clients=$(ubus call gl-clients list 2>/dev/null | jsonfilter -e '@.clients[*]' 2>/dev/null |
	sed -E 's/"mac": *"[^"]*", *//; s/, *"mac": *"[^"]*"//; s/"(last_rx|last_tx|ipv6)": *\[[^]]*\], *//g; s/, *"(last_rx|last_tx|ipv6)": *\[[^]]*\]//g' |
	awk '{printf "%s%s", (n++?", ":""), $0}')
# Bytes per remote destination since the previous call: per-flow deltas from conntrack (accounting on),
# keeping the last sample in /tmp so only what changed is sent. Upload = original direction, download = reply.
ct=$(awk -v prev=/tmp/homeboard-ct.prev -v now="$(date +%s)" '
	function private(ip) { return ip ~ /^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|127\.|169\.254\.|22[4-9]\.|23[0-9]\.|fe80:|ff|fd|fc|::1)/ }
	BEGIN {
		while ((getline line < prev) > 0) { split(line, f, " "); if (f[1] == "T") t0 = f[2]; else { pu[f[1]] = f[2]; pd[f[1]] = f[3] } }
		close(prev)
	}
	{
		n = 0; proto = $3
		for (i = 1; i <= NF; i++) {
			split($i, kv, "=")
			if (kv[1] == "src" && !s) s = kv[2]; else if (kv[1] == "dst" && !d) d = kv[2]
			else if (kv[1] == "sport" && !sp) sp = kv[2]; else if (kv[1] == "dport" && !dp) dp = kv[2]
			else if (kv[1] == "bytes") { n++; if (n == 1) up = kv[2]; else down = kv[2] }
		}
		if (private(s) && !private(d)) {
			k = proto "|" s "|" sp "|" d "|" dp
			du = (k in pu && up >= pu[k]) ? up - pu[k] : up
			dd = (k in pd && down >= pd[k]) ? down - pd[k] : down
			if (t0) { tu[d] += du; td[d] += dd }
			cur[k] = up " " down
		}
		s = d = sp = dp = ""
	}
	END {
		print "T " now > prev
		for (k in cur) print k " " cur[k] > prev
		printf "\"seconds\": %d, \"dst\": {", (t0 ? now - t0 : 0)
		for (ip in tu) if (tu[ip] + td[ip] > 0) printf "%s\"%s\": [%d, %d]", (m++ ? ", " : ""), ip, tu[ip], td[ip]
		printf "}"
	}' /proc/net/nf_conntrack 2>/dev/null)

cat <<EOF
{"time": $(date +%s), "fiber_ok": $(json_bool reach "$FIBER_DEV"), "five_g_ok": $(json_bool reach "$MODEM_DEV"),
 "routes": [$routes], "wan_uptime": ${uptime:-null},
 "counters": {$(counters "$FIBER_DEV"), $(counters "$MODEM_DEV")},
 "modem": ${signal:-null}, "wg_handshakes": [$handshakes], "leases": [$leases], "assoc": {$assoc},
 "clients": [$clients], "ct": {$ct}}
EOF
