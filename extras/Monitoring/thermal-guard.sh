#!/bin/bash
# thermal-guard.sh - lowers the CPU's power and speed when it runs hot, and puts them back once it has cooled.
# Made for a machine with weak cooling (a laptop or small PC used as a server). It works out everything from the
# hardware it runs on: where the temperature is read, what the chip's own limit is, and how much power it may use.
#
#   steps (limit = the chip's own critical temperature, 100 C when it does not say):
#     level 1 at limit-15 C   power 65%   speed 100%
#     level 2 at limit-10 C   power 45%   speed 60%
#     level 3 at limit-5 C    power 30%   speed 30%
#   it goes back one level after cooling 7 C under the temperature that started that level.
#
# Needs root. Any of the values below can be set from outside; the tests use that to run without hardware.
#   TEMP_FILE  a file holding the temperature in thousandths of a degree
#   LIMIT_C    the chip's critical temperature in degrees
#   RAPL       the Intel power-limit folder (leave empty on AMD or ARM: only the speed is lowered)
#   CPUFREQ    a glob of scaling_max_freq files
#   INTERVAL   seconds between readings   ONCE=1 reads once and stops
set -u

find_temp() {
  local z h n
  for z in /sys/class/thermal/thermal_zone*; do
    case "$(cat "$z/type" 2>/dev/null)" in x86_pkg_temp|cpu-thermal|cpu_thermal|soc_thermal) echo "$z/temp"; return;; esac
  done
  for h in /sys/class/hwmon/hwmon*; do
    n=$(cat "$h/name" 2>/dev/null)
    case "$n" in coretemp|k10temp|zenpower|cpu_thermal) echo "$h/temp1_input"; return;; esac
  done
}

find_limit() {  # critical temperature in whole degrees, from the chip itself
  local h v
  for h in /sys/class/hwmon/hwmon*; do
    case "$(cat "$h/name" 2>/dev/null)" in coretemp|k10temp|zenpower|cpu_thermal)
      for v in "$h/temp1_crit" "$h/temp1_max"; do
        [ -r "$v" ] && [ "$(cat "$v")" -gt 1000 ] && { echo $(( $(cat "$v") / 1000 )); return; }
      done;;
    esac
  done
  echo 100
}

TEMP_FILE=${TEMP_FILE:-$(find_temp)}
LIMIT_C=${LIMIT_C:-$(find_limit)}
RAPL=${RAPL-$([ -d /sys/class/powercap/intel-rapl/intel-rapl:0 ] && echo /sys/class/powercap/intel-rapl/intel-rapl:0)}
CPUFREQ=${CPUFREQ:-/sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq}
INTERVAL=${INTERVAL:-10}

[ -r "${TEMP_FILE:-}" ] || { echo "thermal-guard: no CPU temperature sensor found, nothing to guard" >&2; exit 1; }
FREQS=($CPUFREQ)
[ -n "$RAPL" ] || [ -e "${FREQS[0]}" ] || { echo "thermal-guard: can neither limit power nor speed on this machine" >&2; exit 1; }

# remember the normal settings so level 0 puts back exactly what the machine had
PL1=0; PL2=0
if [ -n "$RAPL" ]; then PL1=$(cat "$RAPL/constraint_0_power_limit_uw"); PL2=$(cat "$RAPL/constraint_1_power_limit_uw"); fi
WFILES=(); WORIG=()
for f in "${FREQS[@]}"; do [ -w "$f" ] && { WFILES+=("$f"); WORIG+=("$(cat "$f")"); }; done

#        power%  speed%  starts at
PCT_P=(100 65 45 30)
PCT_F=(100 100 60 30)
START=(0 $((LIMIT_C - 15)) $((LIMIT_C - 10)) $((LIMIT_C - 5)))

level=0
t=0
apply() {
  local i
  if [ -n "$RAPL" ]; then
    echo $(( PL1 * ${PCT_P[$1]} / 100 )) > "$RAPL/constraint_0_power_limit_uw"
    echo $(( PL2 * ${PCT_P[$1]} / 100 )) > "$RAPL/constraint_1_power_limit_uw"
  fi
  for i in "${!WFILES[@]}"; do echo $(( ${WORIG[$i]} * ${PCT_F[$1]} / 100 )) > "${WFILES[$i]}"; done
  logger -t thermal-guard "level $1 (temp ${t} C, limit ${LIMIT_C} C): power ${PCT_P[$1]}% speed ${PCT_F[$1]}%" 2>/dev/null
  echo "level $1 (temp ${t} C): power ${PCT_P[$1]}% speed ${PCT_F[$1]}%"
}

trap 'level=0; apply 0; exit 0' TERM INT   # stopping the guard puts the normal settings back

while :; do
  t=$(( $(cat "$TEMP_FILE") / 1000 ))
  want=$level
  for l in 3 2 1; do                       # go up at once to the highest level the temperature calls for
    if [ "$t" -ge "${START[$l]}" ] && [ "$l" -gt "$want" ]; then want=$l; break; fi
  done
  if [ "$want" = "$level" ] && [ "$level" -gt 0 ] && [ "$t" -lt $(( ${START[$level]} - 7 )) ]; then want=$((level - 1)); fi
  if [ "$want" != "$level" ]; then level=$want; apply "$level"; fi
  [ -n "${ONCE:-}" ] && break
  sleep "$INTERVAL"
done
