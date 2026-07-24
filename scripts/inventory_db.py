import sqlite3
import sys
import os

DB_PATH = "/home/muresan-cristina/proiect-pxe/inventory/vms.db"
CSV_PATH = "/home/muresan-cristina/proiect-pxe/inventory/vm.csv"
INI_PATH = "/home/muresan-cristina/proiect-pxe/ansible/inventory.ini"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(INI_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS machines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hostname TEXT,
                    ip TEXT,
                    mac TEXT UNIQUE,
                    os TEXT,
                    status TEXT)''')
    conn.commit()
    conn.close()

def get_hostname_from_dnsmasq(mac):
    mac = mac.strip().lower()
    lease_paths = ["/var/lib/misc/dnsmasq.leases", "/var/lib/dnsmasq/dnsmasq.leases"]
    
    for path in lease_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            lease_mac = parts[1].lower()
                            lease_host = parts[3]
                            if lease_mac == mac and lease_host and lease_host != "*":
                                return lease_host
            except Exception as e:
                print(f"[ERORE] Nu s-a putut citi fișierul de lease-uri: {e}")
                
    return None

def update_outputs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT hostname, ip, mac, os, status FROM machines")
    
    with open(CSV_PATH, "w") as f:
        f.write("hostname,ip,mac,os,status\n")
        for row in c.fetchall():
            if row[0] and "*" not in row[0]:
                f.write(f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]}\n")
            
    c.execute("SELECT hostname, ip FROM machines WHERE status='Active'")
    rows = c.fetchall()
    
    with open(INI_PATH, "w") as f:
        f.write("[clienti]\n")
        for hostname, ip in rows:
            if hostname and hostname != "server-pxe" and "muresan-cristina" not in hostname and hostname != "Unknown" and "*" not in hostname:
                user = "profesor" if "profesor" in hostname else "student"
                f.write(f"{hostname} ansible_host={ip} ansible_user={user}\n")
                
    conn.close()
    print("[SYNC] Fișierele vm.csv și inventory.ini au fost actualizate curat!")

def register_machine(hostname, ip, mac, os_name="Unknown"):
    mac = mac.strip().lower()
    
    dynamic_host = get_hostname_from_dnsmasq(mac)
    
    if dynamic_host and dynamic_host != "Unknown" and "*" not in dynamic_host:
        hostname = dynamic_host
    elif not hostname or hostname == "Unknown" or "*" not in hostname:
        hostname = f"client-{ip.replace('.', '-')}"
        
    if hostname:
        hostname = hostname.replace("\n", "").replace("\r", "").strip()
        
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO machines (hostname, ip, mac, os, status)
                 VALUES (?, ?, ?, ?, 'Active')
                 ON CONFLICT(mac) DO UPDATE SET
                 hostname=CASE WHEN excluded.hostname = 'Unknown' OR excluded.hostname LIKE '%*%' THEN machines.hostname ELSE excluded.hostname END,
                 ip=excluded.ip, 
                 status='Active' ''',
              (hostname, ip, mac, os_name))
    conn.commit()
    print(f"[STATUS] {hostname} ({ip}) înregistrată/actualizată, MAC={mac}")
    conn.close()
    update_outputs()

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        h_name = sys.argv[1]
        h_ip = sys.argv[2]
        h_mac = sys.argv[3]
        h_os = sys.argv[4] if len(sys.argv) > 4 else "Unknown"
        register_machine(h_name, h_ip, h_mac, h_os)
    else:
        init_db()
        update_outputs()
