#!/system/bin/sh
MODDIR=${0%/*}
D=/data/adb/gpt-vless
while [ "$(getprop sys.boot_completed)" != "1" ]; do
 [ -f "$MODDIR/disable" ] && exit 0
 [ -f "$MODDIR/remove" ] && exit 0
 sleep 3
done
while [ -f "$D/ready" ] && [ ! -f "$D/manual-stop" ] && [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; do
 /system/bin/env -u LD_LIBRARY_PATH /data/data/com.termux/files/usr/bin/python "$D/failover.py" >>"$D/boot.log" 2>&1 &
 SUP_PID=$!
 while kill -0 "$SUP_PID" 2>/dev/null; do
  if [ -f "$D/manual-stop" ] || [ -f "$MODDIR/disable" ] || [ -f "$MODDIR/remove" ]; then
   kill -TERM "$SUP_PID" 2>/dev/null
   wait "$SUP_PID"
   exit 0
  fi
  sleep 2
 done
 wait "$SUP_PID"
 sleep 4
done
