#!/bin/bash
ACTION="$1"
MAC="$2"
IP="$3"
HOSTNAME="${4:-Unknown}"

DB_PATH="/home/muresan-cristina/proiect-pxe/inventory/vms.db"
LOG_FILE="/home/muresan-cristina/proiect-pxe/scripts/dhcp_register.log"
PYTHON_SCRIPT="/home/muresan-cristina/proiect-pxe/scripts/inventory_db.py"

echo "$(date '+%Y-%m-%d %H:%M:%S') ACTION=$ACTION MAC=$MAC IP=$IP HOSTNAME=$HOSTNAME" >> "$LOG_FILE"

if [ "$ACTION" == "del" ]; then
    if [ -n "$MAC" ]; then
        sqlite3 "$DB_PATH" "UPDATE machines SET status='Inactive' WHERE mac='$MAC';"
        python3 "$PYTHON_SCRIPT"
    fi
    exit 0
fi

if [ "$ACTION" != "add" ] && [ "$ACTION" != "old" ]; then
    exit 0
fi

if [ -z "$MAC" ] || [ -z "$IP" ]; then
    exit 0
fi

python3 "$PYTHON_SCRIPT" "$HOSTNAME" "$IP" "$MAC" "Unknown"
exit 0
