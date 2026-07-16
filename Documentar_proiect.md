
## I. Configurarea mediului și a serviciilor

### Arhitectura mediului de test

Pentru testare am folosit două mașini virtuale în VirtualBox, legate printr-o rețea de tip Host-Only:

* **Serverul de automatizare** — o VM cu Ubuntu, cu IP static `192.168.56.10`, pe interfața `enp0s8` (interfața Host-Only din VirtualBox).
* **Client-Test** — o VM goală, fără sistem de operare instalat, setată să boot-eze prin rețea (PXE).

Pe partea de servicii, am ales să combin DHCP-ul și TFTP-ul într-un singur pachet, `dnsmasq`, ca să nu mai gestionez două configurări separate, iar pentru livrarea imaginii ISO (care e prea mare pentru TFTP) am folosit Nginx.

### Pasul 1: DHCP și TFTP cu dnsmasq

Am instalat dnsmasq:

```bash
sudo apt update
sudo apt install dnsmasq -y
```

și am creat folderul unde urmau să stea fișierele de boot:

```bash
sudo mkdir -p /srv/tftp/pxelinux.cfg
```

Configurarea propriu-zisă am făcut-o în `/etc/dnsmasq.conf` (`sudo nano /etc/dnsmasq.conf`). Câteva lucruri pe care le-am setat și de ce:

- `interface=enp0s8` — ca dnsmasq să asculte doar pe interfața Host-Only, nu pe toate interfețele de rețea ale VM-ului (interfața am aflat-o cu `ip a`).
- `bind-interfaces` — ca să se lege strict de interfața aia și să nu intre în conflict cu alte servicii DHCP din rețea.
- `dhcp-range=192.168.56.20,192.168.56.250,255.255.255.0,12h` — plaja de IP-uri pe care le poate aloca automat clienților, valabile 12 ore.
- `dhcp-boot=pxelinux.0` — le spune clienților ce fișier să ceară de la TFTP ca să pornească procesul de boot PXE.
- `enable-tftp` și `tftp-root=/srv/tftp` — pornesc TFTP-ul integrat din dnsmasq și îi spun din ce folder să servească fișierele (kernel, initrd, meniuri PXE).

După ce am salvat configurația, am repornit serviciul:

```bash
sudo systemctl restart dnsmasq
```

### Pasul 2: Nginx pentru livrarea imaginii prin HTTP

TFTP e prea lent pentru un fișier de câțiva GB, așa că imaginea de instalare o servesc prin HTTP, cu Nginx.

```bash
sudo apt install nginx -y
sudo mkdir -p /var/www/html/ubuntu
sudo systemctl start nginx
sudo systemctl enable nginx
```

### Pasul 3: Punerea ISO-ului la locul lui

Am adus imaginea Ubuntu Server 26.04 de pe un stick USB direct pe Desktop-ul serverului. Înainte să o pun definitiv, am șters ce mai rămăsese din testele anterioare, ca să nu am confuzii între versiuni:

```bash
sudo rm -rf /var/www/html/ubuntu/*
sudo mv ~/Desktop/ubuntu-26.04-live-server-amd64.iso /var/www/html/ubuntu/
```

Am dat și drepturi de citire pe fișier, ca orice client din rețea să poată să-l descarce fără să dea peste vreo eroare de permisiuni:

```bash
sudo chmod 644 /var/www/html/ubuntu/ubuntu-26.04-live-server-amd64.iso
sudo systemctl restart nginx
```

###  Pasul 4: Configurarea Meniului de Boot PXE

Am configurat meniul PXE în fișierul `default` din `/srv/tftp/pxelinux.cfg/default` astfel încât clientul care boot-ează prin rețea să primească instrucțiunile corecte de descărcare a ISO-ului prin HTTP (`url=http://192.168.56.10/ubuntu/ubuntu-26.04-live-server-amd64.iso`) și parametrul esențial de rulare live (`boot=casper`).

---

## II. Probleme întâmpinate și cum le-am rezolvat
 
Pe parcursul configurării nu mi-a mers nimic din prima, ceea ce probabil e normal la un sistem cu atâtea componente care depind una de alta (DHCP, TFTP, HTTP, kernel, initrd). Mai jos descriu cele trei probleme majore prin care am trecut, în ordinea în care au apărut.
 
### 1. Eroarea „Unable to find a live file system" / /dev/sr0
 
Prima dată când am pornit clientul de test, boot-ul prin rețea mergea până la un punct, apoi ecranul se umplea cu mesaje repetate că nu poate deschide `/dev/sr0` și că nu găsește niciun mediu care să conțină un sistem de fișiere live.
 
La început am crezut că problema e la TFTP sau la configurarea PXE-ului, dar de fapt kernel-ul și initrd-ul se încărcau corect — problema era că sistemul de instalare (`casper`) căuta un CD fizic din care să pornească, iar eu nu-i dădusem de unde să ia efectiv sistemul de fișiere.
 
Am încercat inițial să servesc doar fișierul `filesystem.squashfs`, scos direct din interiorul ISO-ului, prin parametrul `url=` din configurația PXE, gândindu-mă că așa evit să transfer tot ISO-ul degeaba. Nu a mers — am aflat (după ce am căutat mai mult) că `casper` are nevoie explicit de calea către imaginea `.iso` completă, nu doar către fișierul squashfs din interiorul ei; altfel nu reușește să o monteze corect ca sistem de fișiere live.
 
Am corectat linia `APPEND` din `/srv/tftp/pxelinux.cfg/default` ca să indice către ISO-ul complet, pus pe serverul Nginx, și am adăugat și parametrul `boot=casper`, care lipsea.
 
### 2. Descărcarea se oprea la ~26% cu eroarea „short write: No space left on device"
 
După ce am rezolvat problema de mai sus, boot-ul a mers mai departe și a început efectiv să descarce ISO-ul prin HTTP. Doar că la un moment dat, undeva pe la 743 MB din cei aproape 2.7 GB, procesul se oprea brusc și cădea într-un shell de BusyBox/initramfs, cu eroarea că nu mai e spațiu pe disk.
 
Explicația e că, în acest mod de boot (live, fără disk local), tot ce se descarcă merge direct în memoria RAM a mașinii — practic un RAM disk. VM-ul meu de test avea alocată foarte puțină memorie, așa că se umplea înainte să termine descărcarea.
 
Am oprit VM-ul, i-am mărit memoria RAM din setările VirtualBox (am ajuns la 10 GB, deși probabil minimul funcțional e undeva pe la 4 GB), și la următoarea încercare descărcarea a mers până la capăt, 100%.
 
### 3. Aceeași eroare de „live file system", dar după ce ISO-ul se descărcase complet
 
Aici a fost cea mai enervantă problemă, pentru că părea că am rezolvat totul — ISO-ul se descărca integral, 2.7 GB, fără erori — și totuși la final tot apărea mesajul că nu găsește sistemul de fișiere live, exact ca la prima problemă.
 
Motivul, de data asta, era altul: fișierele `vmlinuz` și `initrd` pe care le pusesem în folderul TFTP proveneau dintr-o versiune de Ubuntu diferită de cea din ISO-ul pe care îl descărcam efectiv (Ubuntu 26.04). Practic kernel-ul cu care pornea clientul nu se mai potrivea cu sistemul de fișiere din ISO, așa că, deși descărcarea reușea, montarea eșua.
 
Soluția e să montez ISO-ul direct pe server și să copiez de-acolo exact versiunile de `vmlinuz` și `initrd` care corespund lui — nu să folosesc fișiere rămase de la o încercare anterioară cu altă versiune de Ubuntu. (Acest pas urmează să-l fac.)
