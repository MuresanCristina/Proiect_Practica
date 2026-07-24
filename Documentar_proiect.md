# Documentație proiect  
## Infrastructură PXE, inventar centralizat și power management

## 1. Scopul proiectului

Scopul proiectului este construirea unei infrastructuri automatizate pentru:

- instalarea sistemelor de operare prin rețea, folosind **PXE**;
- atribuirea automată a adreselor IP prin **DHCP**;
- livrarea fișierelor de boot prin **TFTP**;
- livrarea imaginii ISO prin **HTTP**;
- înregistrarea automată a clienților într-o bază de date SQLite;
- generarea inventarului pentru Ansible;
- pornirea, oprirea și repornirea mașinilor virtuale pe baza adresei MAC.

Soluția a fost implementată într-un mediu VirtualBox, cu un server Ubuntu și mai multe mașini virtuale client.

---

## 2. Arhitectura mediului de test

### 2.1. Host-ul fizic

VirtualBox rulează pe un sistem Windows. Acesta găzduiește serverul de automatizare și mașinile virtuale client.

Pentru operațiile de power management, serverul Ubuntu transmite comenzi către host-ul Windows prin SSH, iar pe Windows este executat `VBoxManage.exe`.

### 2.2. Serverul de automatizare

Serverul este o mașină virtuală Ubuntu cu următoarele caracteristici:

- adresă IP statică: `192.168.56.10`;
- interfață Host-Only: `enp0s8`;
- servicii principale:
  - `dnsmasq` pentru DHCP și TFTP;
  - `nginx` pentru livrarea imaginii ISO prin HTTP;
  - SQLite pentru inventarul centralizat;
  - scripturi Python și Bash pentru sincronizare și management;
  - Ansible pentru configurarea ulterioară a clienților.

### 2.3. Clienții PXE

Au fost folosite două mașini virtuale client:

- `Client-Test`;
- `Client-Test-2`.

Inițial, acestea nu aveau un sistem de operare instalat și au fost configurate să pornească direct prin rețea, folosind PXE.

### 2.4. Rețeaua

Toate mașinile sunt conectate într-o rețea VirtualBox de tip **Host-Only**, pentru a izola mediul de test de rețeaua Wi-Fi și de infrastructura externă.

Fluxul principal este:

```text
Client PXE
   |
   | DHCP + TFTP
   v
Server Ubuntu / dnsmasq
   |
   | HTTP
   v
Nginx / imagine ISO
```

Pentru power management:

```text
Server Ubuntu
   |
   | SSH cu autentificare pe bază de cheie
   v
Host Windows
   |
   | VBoxManage.exe
   v
Mașini virtuale VirtualBox
```

---

# I. Configurarea serviciilor PXE

## 3. DHCP și TFTP cu dnsmasq

Am ales `dnsmasq` deoarece oferă într-un singur serviciu atât funcționalitate DHCP, cât și TFTP.

Instalarea s-a realizat astfel:

```bash
sudo apt update
sudo apt install dnsmasq -y
sudo mkdir -p /srv/tftp/pxelinux.cfg
```

Configurarea principală a fost realizată în:

```text
/etc/dnsmasq.conf
```

Exemplu de configurare:

```ini
interface=enp0s8
bind-interfaces

dhcp-range=192.168.56.20,192.168.56.250,255.255.255.0,12h
dhcp-boot=pxelinux.0

enable-tftp
tftp-root=/srv/tftp
```

Semnificația directivelor:

- `interface=enp0s8` — limitează serviciul la interfața Host-Only;
- `bind-interfaces` — obligă dnsmasq să se lege strict de interfața indicată;
- `dhcp-range` — definește plaja de adrese IP atribuite clienților;
- `dhcp-boot=pxelinux.0` — indică fișierul inițial de boot PXE;
- `enable-tftp` — activează serverul TFTP integrat;
- `tftp-root=/srv/tftp` — stabilește directorul din care sunt servite fișierele de boot.

După modificarea configurației:

```bash
sudo systemctl restart dnsmasq
sudo systemctl status dnsmasq
```

---

## 4. Nginx pentru livrarea imaginii ISO

TFTP este potrivit pentru fișierele mici necesare pornirii, precum `pxelinux.0`, `vmlinuz` și `initrd`, dar este ineficient pentru transferul unei imagini ISO de câțiva gigabytes.

Din acest motiv, imaginea de instalare este livrată prin HTTP folosind Nginx.

Instalare și configurare:

```bash
sudo apt install nginx -y
sudo mkdir -p /var/www/html/ubuntu
sudo systemctl start nginx
sudo systemctl enable nginx
```

Imaginea ISO a fost copiată în directorul web:

```bash
sudo rm -rf /var/www/html/ubuntu/*
sudo mv ~/Desktop/ubuntu-26.04-live-server-amd64.iso /var/www/html/ubuntu/
sudo chmod 644 /var/www/html/ubuntu/ubuntu-26.04-live-server-amd64.iso
sudo systemctl restart nginx
```

Imaginea devine disponibilă în rețea la adresa:

```text
http://192.168.56.10/ubuntu/ubuntu-26.04-live-server-amd64.iso
```

---

## 5. Fișierele de boot și meniul PXE

Fișierele `vmlinuz` și `initrd` trebuie să provină din aceeași imagine ISO care este livrată prin HTTP.

Montarea imaginii:

```bash
sudo mkdir -p /mnt/ubuntu-iso
sudo mount -o loop /var/www/html/ubuntu/ubuntu-26.04-live-server-amd64.iso /mnt/ubuntu-iso
```

Copierea fișierelor corespunzătoare în TFTP:

```bash
sudo cp /mnt/ubuntu-iso/casper/vmlinuz /srv/tftp/
sudo cp /mnt/ubuntu-iso/casper/initrd /srv/tftp/
```

Meniul PXE a fost configurat în:

```text
/srv/tftp/pxelinux.cfg/default
```

Exemplu:

```cfg
DEFAULT install
PROMPT 0
TIMEOUT 50

LABEL install
    KERNEL vmlinuz
    INITRD initrd
    APPEND boot=casper ip=dhcp url=http://192.168.56.10/ubuntu/ubuntu-26.04-live-server-amd64.iso
```

Parametrii importanți sunt:

- `boot=casper` — pornește mediul live Ubuntu;
- `ip=dhcp` — solicită configurarea automată a rețelei;
- `url=...iso` — indică imaginea ISO completă servită de Nginx.

---

# II. Inventarul centralizat și managementul mașinilor

## 6. Baza de date SQLite

Inventarul mașinilor este păstrat în:

```text
/home/muresan-cristina/proiect-pxe/inventory/vms.db
```

Baza de date conține, pentru fiecare mașină:

- hostname;
- adresă IP;
- adresă MAC;
- sistem de operare;
- status;
- numele mașinii din VirtualBox, acolo unde este necesar.

Adresa MAC este utilizată ca identificator stabil, deoarece adresa IP se poate schimba după reînnoirea lease-ului DHCP.

---

## 7. Înregistrarea automată a clienților

Scriptul `dhcp_register.sh` este apelat de dnsmasq la evenimente precum:

- `add` — un lease nou;
- `old` — reînnoirea unui lease;
- `del` — eliminarea unui lease.

Scriptul transmite către `inventory_db.py`:

- hostname-ul;
- adresa IP;
- adresa MAC;
- tipul evenimentului.

Fișierele utilizate sunt:

```text
/home/muresan-cristina/proiect-pxe/scripts/dhcp_register.sh
/home/muresan-cristina/proiect-pxe/scripts/inventory_db.py
```

În configurația dnsmasq este definit hook-ul:

```ini
dhcp-script=/home/muresan-cristina/proiect-pxe/scripts/dhcp_register.sh
```

---

## 8. Scriptul `inventory_db.py`

Rolurile principale ale scriptului sunt:

1. citește lease-urile dnsmasq;
2. identifică mașinile după MAC;
3. actualizează hostname-ul și IP-ul în SQLite;
4. păstrează asocierea corectă dintre MAC și mașină;
5. generează automat fișierul CSV;
6. generează inventarul Ansible;
7. sincronizează starea mașinilor.

Fișierul CSV generat este:

```text
/home/muresan-cristina/proiect-pxe/inventory/vm.csv
```

Inventarul Ansible este:

```text
/home/muresan-cristina/proiect-pxe/ansible/inventory.ini
```

Exemplu de intrare Ansible:

```ini
[clienti]
ubuntu-client-profesor ansible_host=192.168.56.50 ansible_user=profesor
ubuntu-client ansible_host=192.168.56.51 ansible_user=student
```

---

## 9. Meniul interactiv de management

Scriptul `manage.py` afișează inventarul centralizat și permite administrarea mașinilor după adresa MAC.

Operațiile implementate sunt:

- oprire controlată prin SSH;
- pornire prin VirtualBox;
- repornire;
- actualizarea statusului;
- sincronizarea bazei de date și a fișierelor de inventar.

Identificarea după MAC reduce riscul de a executa o comandă asupra altei mașini atunci când adresa IP se schimbă.

---

## 10. Power management prin host-ul Windows

Deoarece VirtualBox rulează pe Windows, serverul Ubuntu nu controlează direct hypervisorul.

Soluția implementată este:

1. serverul Ubuntu se conectează prin SSH la host-ul Windows;
2. autentificarea se realizează cu cheia `vbox_host_key`;
3. pe Windows este executat `VBoxManage.exe`;
4. mașina este identificată prin numele său VirtualBox;
5. operația de pornire, oprire sau repornire este executată pe host.

Exemplu conceptual:

```text
Ubuntu Server
    -> SSH
Windows Host
    -> VBoxManage.exe startvm "Client-Test" --type headless
VirtualBox VM
```

Această separare este necesară deoarece controlul stării unei mașini virtuale aparține hypervisorului de pe host, nu sistemului de operare invitat.

---

# III. Probleme întâmpinate și soluții

## 11. Eroarea „Unable to find a live file system” și accesarea `/dev/sr0`

La prima pornire PXE, kernelul și initrd-ul erau încărcate corect, dar mediul `casper` încerca să găsească un suport optic local, reprezentat prin `/dev/sr0`.

Inițial a fost servit doar fișierul:

```text
filesystem.squashfs
```

Această abordare nu a funcționat, deoarece procesul de boot avea nevoie de imaginea ISO completă pentru a o monta și pentru a găsi structura completă a mediului live.

Soluția a fost:

- servirea imaginii `.iso` complete prin HTTP;
- adăugarea parametrului `boot=casper`;
- indicarea corectă a URL-ului imaginii în linia `APPEND`.

---

## 12. Eroarea „short write: No space left on device”

Descărcarea imaginii se oprea la aproximativ 743 MB, iar sistemul intra în BusyBox/initramfs.

Cauza era faptul că imaginea descărcată era stocată temporar într-un filesystem din RAM. Memoria alocată clientului era insuficientă pentru imaginea ISO și pentru procesele de boot.

Soluția a fost creșterea memoriei RAM a clientului la 10 GB.

După această modificare, descărcarea imaginii a ajuns la 100%.

---

## 13. Incompatibilitatea dintre kernel, initrd și imaginea ISO

Chiar după descărcarea completă a imaginii, mediul live nu putea fi montat.

Cauza a fost folosirea unor fișiere `vmlinuz` și `initrd` provenite dintr-o versiune diferită de Ubuntu.

Soluția a fost montarea imaginii ISO folosite efectiv și copierea fișierelor corespunzătoare direct din directorul `casper`.

> Kernelul, initrd-ul și filesystem-ul live trebuie să provină din aceeași versiune a imaginii de instalare.

---

## 14. Probleme SSH și permisiuni pentru oprirea mașinilor

Comanda de oprire:

```bash
sudo shutdown -h now
```

solicita inițial autentificare sau parolă pentru `sudo`, ceea ce împiedica automatizarea.

Soluțiile aplicate au fost:

- generarea unei chei SSH;
- copierea cheii publice pe clienți cu `ssh-copy-id`;
- configurarea unei reguli `NOPASSWD` în `sudoers` pentru comenzile necesare;
- utilizarea autentificării pe bază de cheie în scripturi.

În acest mod, oprirea se poate realiza fără intervenție manuală.

---

## 15. Eroarea „Remote Host Identification Has Changed”

La recrearea mașinilor virtuale, cheia SSH a sistemului client se modifica, dar serverul păstra vechea amprentă în `known_hosts`.

SSH interpreta situația ca pe un posibil atac de tip Man-in-the-Middle.

Intrarea veche a fost eliminată astfel:

```bash
ssh-keygen -R 192.168.56.X
```

După eliminare, noua amprentă a putut fi acceptată.

---

## 16. Asocierea greșită dintre MAC și mașina VirtualBox

La un moment dat, o adresă MAC introdusă în meniul de management controla altă mașină.

Cauza a fost asocierea inversată dintre:

- adresa MAC;
- hostname;
- numele mașinii din VirtualBox.

În baza de date, câmpurile corespunzătoare mașinilor `student` și `profesor` erau inversate.

Soluția a fost corectarea manuală a înregistrărilor printr-o comandă `UPDATE` în SQLite și stabilirea MAC-ului ca identificator principal.

---

## 17. Statusuri vechi în `vm.csv` și `inventory.ini`

Fișierele generate puteau păstra informații vechi dacă baza de date nu era sincronizată după pornirea sau oprirea unei mașini.

Soluția a constat în:

- interogarea stării reale a mașinilor înainte de afișarea inventarului;
- actualizarea bazei de date după MAC;
- regenerarea automată a fișierelor `vm.csv` și `inventory.ini`;
- separarea dintre identitatea permanentă a mașinii și starea sa temporară.

În forma finală:

- MAC-ul identifică mașina;
- lease-ul DHCP actualizează IP-ul;
- VirtualBox indică starea reală a VM-ului;
- SQLite păstrează inventarul central;
- CSV și Ansible sunt generate din baza de date.

---

## 18. Schimbarea repetată a adreselor IP

În timpul testelor, același MAC a primit succesiv mai multe adrese IP.

Această situație poate apărea atunci când:

- există mai multe servere DHCP active;
- serviciul DHCP din VirtualBox nu este dezactivat;
- lease-urile sunt foarte scurte;
- există suprapuneri între rezervările statice și pool-ul dinamic.

Pentru stabilizarea adreselor, se pot configura rezervări DHCP:

```ini
dhcp-host=08:00:27:4a:b0:ee,ubuntu-client-profesor,192.168.56.50,infinite
dhcp-host=08:00:27:cf:13:62,ubuntu-client,192.168.56.51,infinite
```

Pool-ul dinamic trebuie să evite aceste adrese:

```ini
dhcp-range=192.168.56.100,192.168.56.200,255.255.255.0,12h
```

---

# IV. Verificarea infrastructurii

## 19. Verificarea serviciilor

```bash
sudo systemctl status dnsmasq
sudo systemctl status nginx
```

Verificarea porturilor:

```bash
sudo ss -lunp | grep -E ':67|:69'
sudo ss -ltnp | grep ':80'
```

---

## 20. Verificarea lease-urilor DHCP

```bash
cat /var/lib/misc/dnsmasq.leases
```

sau:

```bash
cat /var/lib/dnsmasq/dnsmasq.leases
```

---

## 21. Verificarea bazei de date

```bash
sqlite3 /home/muresan-cristina/proiect-pxe/inventory/vms.db \
"SELECT id, hostname, ip, mac, os, status FROM machines;"
```

---

## 22. Verificarea fișierelor generate

```bash
cat /home/muresan-cristina/proiect-pxe/inventory/vm.csv
```

```bash
cat /home/muresan-cristina/proiect-pxe/ansible/inventory.ini
```

---

## 23. Verificarea conectivității Ansible

```bash
ansible all \
-i /home/muresan-cristina/proiect-pxe/ansible/inventory.ini \
-m ping
```

---

# V. Concluzii

Proiectul combină mai multe componente într-un flux automatizat:

- `dnsmasq` realizează atribuirea IP-urilor și boot-ul inițial;
- TFTP livrează fișierele necesare pornirii;
- Nginx livrează imaginea ISO;
- SQLite păstrează inventarul centralizat;
- scripturile Bash și Python sincronizează informațiile;
- Ansible utilizează inventarul generat;
- SSH și `VBoxManage.exe` permit controlul mașinilor virtuale de pe host-ul Windows.

Principala dificultate a fost coordonarea componentelor care folosesc surse diferite de informație: DHCP pentru IP, VirtualBox pentru starea VM-urilor, SSH pentru administrarea sistemului de operare și SQLite pentru inventarul central.

În forma finală, adresa MAC funcționează ca identificator stabil, iar toate celelalte informații sunt actualizate în jurul acesteia. Această abordare permite automatizarea deployment-ului, reducerea intervenției manuale și administrarea coerentă a infrastructurii de test.
