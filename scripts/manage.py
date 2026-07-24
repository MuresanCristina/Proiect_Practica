import sqlite3
import subprocess
import os

DB_PATH = "/home/muresan-cristina/proiect-pxe/inventory/vms.db"
SSH_KEY = "/home/muresan-cristina/.ssh/pxe_key"

VBOX_HOST_IP = "192.168.56.1"
VBOX_HOST_USER = "cristina"
VBOX_HOST_SSH_KEY = "/home/muresan-cristina/.ssh/vbox_host_key"
VBOX_HOST_MANAGE_PATH = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"


def run_on_vbox_host(vbox_args):
    quoted_args = " ".join(f'"{a}"' for a in vbox_args)
    remote_cmd = f'"{VBOX_HOST_MANAGE_PATH}" {quoted_args}'
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=8",
        "-i", VBOX_HOST_SSH_KEY,
        f"{VBOX_HOST_USER}@{VBOX_HOST_IP}",
        remote_cmd,
    ]
    return subprocess.run(cmd, check=True, timeout=30, capture_output=True, text=True)


def get_running_vbox_names():
    try:
        result = run_on_vbox_host(["list", "runningvms"])
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None

    running = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith('"') and '"' in line[1:]:
            name = line.split('"')[1]
            running.add(name)
    return running


def sync_statuses(rows):
    running = get_running_vbox_names()
    if running is None:
        print("[!] Nu am putut verifica starea reala a masinilor pe host (conexiune SSH esuata).")
        return rows

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    updated_rows = []
    for row in rows:
        machine_id, hostname, ip, mac, status, vbox_name = row
        if vbox_name:
            real_status = "Active" if vbox_name in running else "Inactive"
            if real_status != status:
                cursor.execute("UPDATE machines SET status=? WHERE mac=?", (real_status, mac))
                status = real_status
        updated_rows.append((machine_id, hostname, ip, mac, status, vbox_name))
    conn.commit()
    conn.close()
    return updated_rows


def fetch_machines():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, hostname, ip, mac, status, vbox_name FROM machines")
    rows = cursor.fetchall()
    conn.close()
    return rows


def print_machines(rows):
    print("\n" + "=" * 60)
    print("           INVENTAR CENTRALIZAT & POWER MANAGEMENT")
    print("=" * 60)
    print(f"{'ID':<4} | {'HOSTNAME':<25} | {'MAC':<17} | {'STATUS':<10}")
    print("-" * 60)
    for row in rows:
        print(f"{row[0]:<4} | {row[1]:<25} | {row[3]:<17} | {row[4]:<10}")
    print("-" * 60)


def shutdown_machine(ip, mac, hostname, vbox_name=None):
    print(f"\n[ACTION] Trimit comanda de oprire catre {hostname} (MAC: {mac})...")
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=3",
        "-i", SSH_KEY,
        f"student@{ip}",
        "sudo -n shutdown -h now",
    ]
    try:
        subprocess.run(cmd, check=True, timeout=5)
        print("[SUCCESS] Mașina a primit comanda de oprire curată prin SSH.")
        return "Inactive"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("[!] SSH-ul a eșuat (mașina nu răspunde sau este deja oprită). Folosesc VirtualBox...")
        if vbox_name:
            try:
                run_on_vbox_host(["controlvm", vbox_name, "poweroff"])
                print("[SUCCESS] Mașina a fost oprită forțat prin VirtualBox.")
                return "Inactive"
            except Exception as e:
                print(f"[EROARE] Nu am putut opri mașina prin VirtualBox: {e}")
        else:
            print("[EROARE] Mașina nu are un 'vbox_name' setat pentru oprire forțată.")
    return None


def start_machine(hostname, vbox_name):
    if not vbox_name:
        print(f"\n[EROARE] Mașina {hostname} nu are un 'vbox_name' setat în baza de date.")
        print("         Ruleaza VBoxManage list vms pe host si actualizeaza coloana vbox_name cu numele exact.")
        return None
    print(f"\n[ACTION] Pornesc mașina virtuală {hostname} (VBox: {vbox_name}) pe host-ul Windows...")
    try:
        run_on_vbox_host(["startvm", vbox_name, "--type", "headless"])
        print("[SUCCESS] Mașina virtuală a fost pornită cu succes.")
        return "Active"
    except subprocess.CalledProcessError as e:
        print(f"[EROARE] VBoxManage a eșuat pe host: {e.stderr.strip() if e.stderr else e}")
    except subprocess.TimeoutExpired:
        print("[EROARE] Timeout la conectarea către host-ul Windows.")
    except FileNotFoundError:
        print("[EROARE] Comanda 'ssh' nu a fost găsită pe acest sistem.")
    return None


def restart_machine(ip, mac, hostname, vbox_name):
    print(f"\n[ACTION] Repornesc mașina {hostname} (VBox: {vbox_name})...")
    
    shutdown_result = shutdown_machine(ip, mac, hostname, vbox_name)
    if shutdown_result is None:
        print("[EROARE] Oprirea a eșuat complet, nu pot continua pornirea.")
        return None
    
    import time
    time.sleep(2)

    return start_machine(hostname, vbox_name)


def change_status(ip, mac, action, hostname, vbox_name=None):
    if action == "shutdown":
        new_status = shutdown_machine(ip, mac, hostname, vbox_name)
    elif action == "start":
        new_status = start_machine(hostname, vbox_name)
    elif action == "restart":
        new_status = restart_machine(ip, mac, hostname, vbox_name)
    else:
        return

    if new_status is None:
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE machines SET status=? WHERE mac=?", (new_status, mac))
    conn.commit()
    conn.close()

    sync_script = "/home/muresan-cristina/proiect-pxe/scripts/inventory_db.py"
    if os.path.exists(sync_script):
        subprocess.run(["python3", sync_script, hostname, ip, mac, "Unknown"], check=False)

    print(f"[SYNC] Starea mașinii {hostname} (MAC: {mac}) a fost actualizată la: {new_status}\n")


if __name__ == "__main__":
    while True:
        rows = fetch_machines()
        rows = sync_statuses(rows)
        print_machines(rows)
        print("\nMeniu de Control (se folosește adresa MAC):")
        print("1. Oprește o mașină după MAC (Shutdown via SSH / VBox)")
        print("2. Pornește o mașină după MAC (VirtualBox Power On)")
        print("3. Repornește o mașină după MAC (Shutdown + Power On)")
        print("4. Ieșire")

        choice = input("\nAlege o opțiune (1/2/3/4): ").strip()
        if choice in ("1", "2", "3"):
            mac_input = input("Introdu adresa MAC a mașinii (ex: 08:00:27:...): ").strip()
            target_row = next((r for r in rows if r[3].lower() == mac_input.lower()), None)
            if target_row:
                action = {"1": "shutdown", "2": "start", "3": "restart"}[choice]
                change_status(target_row[2], target_row[3], action, target_row[1], target_row[5])
            else:
                print("\n[!] Adresa MAC introdusă nu a fost găsită în inventar.")
        elif choice == "4":
            print("\nIeșire din meniul de management. La revedere!")
            break
        else:
            print("\n[!] Opțiune invalidă. Te rog să alegi 1, 2, 3 sau 4.")
