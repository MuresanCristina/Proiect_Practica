import os
import sqlite3
import subprocess

DB_PATH = '/home/muresan-cristina/proiect-pxe/inventory/vms.db'
SSH_KEY = '/home/muresan-cristina/.ssh/pxe_key'

VBOX_HOST_IP = '192.168.56.1'
VBOX_HOST_USER = 'cristina'
VBOX_HOST_SSH_KEY = '/home/muresan-cristina/.ssh/vbox_host_key'
VBOX_HOST_MANAGE_PATH = r'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
# Calea catre wol_send.ps1 PE HOST-UL WINDOWS (copiaza scriptul acolo, vezi instructiuni)
VBOX_HOST_WOL_SCRIPT = r'C:\Users\cristina\wol_send.ps1'


def run_on_vbox_host(vbox_args):
  quoted_args = ' '.join(f'"{a}"' for a in vbox_args)
  remote_cmd = f'"{VBOX_HOST_MANAGE_PATH}" {quoted_args}'
  cmd = [
      'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=8',
      '-i', VBOX_HOST_SSH_KEY,
      f'{VBOX_HOST_USER}@{VBOX_HOST_IP}',
      remote_cmd,
  ]
  return subprocess.run(cmd, check=True, timeout=30, capture_output=True, text=True)


def get_running_vbox_names():
  try:
    result = run_on_vbox_host(['list', 'runningvms'])
  except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
    return None

  running = set()
  for line in result.stdout.splitlines():
    line = line.strip()
    if line.startswith('"') and '"' in line[1:]:
      running.add(line.split('"')[1])
  return running


def sync_statuses(rows):
  running = get_running_vbox_names()
  if running is None:
    print('[!] Nu am putut verifica starea reala a masinilor pe host (conexiune SSH esuata).')
    return rows

  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  updated_rows = []
  for row in rows:
    machine_id, hostname, ip, mac, status, vbox_name = row
    if vbox_name:
      real_status = 'Active' if vbox_name in running else 'Inactive'
      if real_status != status:
        cursor.execute('UPDATE machines SET status=? WHERE mac=?', (real_status, mac))
        status = real_status
    updated_rows.append((machine_id, hostname, ip, mac, status, vbox_name))
  conn.commit()
  conn.close()
  return updated_rows


def fetch_machines():
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute('SELECT id, hostname, ip, mac, status, vbox_name FROM machines')
  rows = cursor.fetchall()
  conn.close()
  return rows


def print_machines(rows):
  print('\n' + '=' * 75)
  print('            INVENTAR CENTRALIZAT & POWER MANAGEMENT')
  print('=' * 75)
  print(f"{'ID':<4} | {'HOSTNAME':<22} | {'IP':<15} | {'MAC':<17} | {'STATUS':<8}")
  print('-' * 75)
  for row in rows:
    print(f'{row[0]:<4} | {row[1]:<22} | {row[2]:<15} | {row[3]:<17} | {row[4]:<8}')
  print('-' * 75)


import socket

# Broadcast-ul retelei bridged (enp0s8), unde e conectat laptopul fizic prin cablu.
WOL_BROADCAST_IP = '10.0.3.255'
WOL_PORT = 9


def wake_on_lan(macaddress):
  """Trimite un pachet Wake-on-LAN direct din acest VM, pe interfata bridged
  (enp0s8), care e conectata fizic (prin cablu) la aceeasi retea cu laptopul
  tinta. Functioneaza doar daca VM-ul are IP static pe acea interfata si
  laptopul are Wake-on-LAN activat in BIOS/Windows.
  """
  clean_mac = macaddress.replace(':', '').replace('-', '')
  if len(clean_mac) != 12:
    print('[EROARE] Adresa MAC invalida pentru Wake-on-LAN.')
    return False
  try:
    data = bytes.fromhex('FF' * 6 + clean_mac * 16)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(data, (WOL_BROADCAST_IP, WOL_PORT))
    sock.close()
    print(f'[SUCCESS] Pachetul magic Wake-on-LAN a fost trimis catre MAC: {macaddress}')
    return True
  except Exception as e:
    print(f'[EROARE] Nu am putut trimite pachetul WoL: {e}')
    return False


def shutdown_machine(ip, mac, hostname, vbox_name=None):
  print(f'\n[ACTION] Trimit comanda de oprire catre {hostname} (MAC: {mac})...')
  cmd = [
      'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5',
      '-i', SSH_KEY,
      f'student@{ip}',
      'sudo -n shutdown -h now',
  ]
  try:
    subprocess.run(cmd, check=True, timeout=10)
    print('[SUCCESS] Masina a primit comanda de oprire curata prin SSH.')
    return 'Inactive'
  except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
    print('[!] SSH-ul a esuat (masina nu raspunde sau e deja oprita).')
    if vbox_name:
      try:
        run_on_vbox_host(['controlvm', vbox_name, 'poweroff'])
        print('[SUCCESS] Masina a fost oprita fortat prin VirtualBox.')
        return 'Inactive'
      except Exception as e:
        print(f'[EROARE] Nu am putut opri masina prin VirtualBox: {e}')
    else:
      print("[EROARE] Masina fizica nu poate fi oprita de la distanta fara SSH functional.")
  return None


def start_machine(hostname, vbox_name, mac):
  if vbox_name:
    print(f'\n[ACTION] Pornesc masina virtuala {hostname} (VBox: {vbox_name}) pe host-ul Windows...')
    try:
      run_on_vbox_host(['startvm', vbox_name, '--type', 'headless'])
      print('[SUCCESS] Masina virtuala a fost pornita cu succes prin VirtualBox.')
      return 'Active'
    except subprocess.CalledProcessError as e:
      print(f'[EROARE] VBoxManage a esuat pe host: {e.stderr.strip() if e.stderr else e}')
    except subprocess.TimeoutExpired:
      print('[EROARE] Timeout la conectarea catre host-ul Windows.')
    except FileNotFoundError:
      print("[EROARE] Comanda 'ssh' nu a fost gasita pe acest sistem.")
    return None
  else:
    print(f'\n[ACTION] {hostname} este un dispozitiv fizic. Trimit Wake-on-LAN catre MAC: {mac}...')
    return 'Active' if wake_on_lan(mac) else None


def restart_machine(ip, mac, hostname, vbox_name):
  print(f'\n[ACTION] Repornesc masina {hostname}...')
  shutdown_result = shutdown_machine(ip, mac, hostname, vbox_name)
  if shutdown_result is None:
    print('[EROARE] Oprirea a esuat, nu continui cu pornirea.')
    return None

  import time
  time.sleep(3)

  return start_machine(hostname, vbox_name, mac)


def change_status(ip, mac, action, hostname, vbox_name=None):
  if action == 'shutdown':
    new_status = shutdown_machine(ip, mac, hostname, vbox_name)
  elif action == 'start':
    new_status = start_machine(hostname, vbox_name, mac)
  elif action == 'restart':
    new_status = restart_machine(ip, mac, hostname, vbox_name)
  else:
    return

  if new_status is None:
    return

  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute('UPDATE machines SET status=? WHERE mac=?', (new_status, mac))
  conn.commit()
  conn.close()

  sync_script = '/home/muresan-cristina/proiect-pxe/scripts/inventory_db.py'
  if os.path.exists(sync_script):
    subprocess.run(['python3', sync_script, hostname, ip, mac, 'Unknown'], check=False)

  print(f'[SYNC] Starea masinii {hostname} (MAC: {mac}) a fost actualizata la: {new_status}\n')


if __name__ == '__main__':
  while True:
    rows = fetch_machines()
    rows = sync_statuses(rows)
    print_machines(rows)
    print('\nMeniu de Control (se foloseste adresa MAC):')
    print('1. Opreste o masina dupa MAC (Shutdown via SSH / VBox)')
    print('2. Porneste o masina dupa MAC (VirtualBox / Wake-on-LAN)')
    print('3. Reporneste o masina dupa MAC (Shutdown + Power On)')
    print('4. Iesire')

    choice = input('\nAlege o optiune (1/2/3/4): ').strip()
    if choice in ('1', '2', '3'):
      mac_input = input('Introdu adresa MAC a masinii (ex: 08:00:27:...): ').strip()
      target_row = next((r for r in rows if r[3].lower() == mac_input.lower()), None)
      if target_row:
        action = {'1': 'shutdown', '2': 'start', '3': 'restart'}[choice]
        change_status(target_row[2], target_row[3], action, target_row[1], target_row[5])
      else:
        print('\n[!] Adresa MAC introdusa nu a fost gasita in inventar.')
    elif choice == '4':
      print('\nIesire din meniul de management. La revedere!')
      break
    else:
      print('\n[!] Optiune invalida. Te rog sa alegi 1, 2, 3 sau 4.')
