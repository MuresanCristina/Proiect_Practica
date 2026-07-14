Titlu Prezentare: Securitatea și Automatizarea Deployment-ului de OS în Cyber Computing 
Slide 1-2: Introducere in securitatea OS
    Idei principale: Securitate + Automatizare in Cyber Computing, Importanta securizarii sistemului de operare inca din faza de instalare, problema configurarilor manuale: existenta unei "ferestre de atac"

Slide 3-4: Evolutia Infrastructurilor & Provocarile actuale
    Idei principale:Tranziția istorică a mediilor unde instalăm sisteme de operare: de la servere fizice (bare-metal) la mașini virtuale în Cloud și noduri descentralizate în Edge Computing.De ce metodele clasice de instalare nu mai pot asigura conformitatea și securitatea la scară largă.

Slide 5-6:Automatizarea prin IaC
    Idei principale:Ce este IaC, Provisioning vs Configurration Management, utilizarea de "Golden Images" si fisiere Cloud-Init

Slide 7-8:SecOps & Securizarea Ciclului de Deployment
    Idei principale: Conceptul de DevSecOps aplicat la OS, etapele pipelinului teoretic

Slide 9-10:Mecanisme de Hardening la Nivel de OS & Secrete
    Idei principale: CIS Hardening sau STIGs, Principiul „Zero Secrete în Cod”: eliminarea parolelor statice și a cheilor SSH scrise în scripturile de deployment; înlocuirea lor cu injectarea dinamică a acreditărilor la boot (ex: HashiCorp Vault).

Slide 11-12:Securitate Hardware: UEFI, Secure Boot și TPM
    Idei principale: Protejarea procesului de pornire împotriva malware-ului de tip bootkit/rootkit prin UEFI Secure Boot, Rolul modulului TPM (Trusted Platform Module) în măsurarea integrității componentelor de boot și stocarea securizată a cheilor criptografice ale sistemului de operare.

Slide 13-14:Arhitecturi Imutabile și Paradigmă Zero Trust
    Idei principale: Infrastructura Imutabilă la nivel de OS: partițiile de sistem sunt montate ca „Read-Only”. Serverele nu mai primesc patch-uri de securitate live; în caz de vulnerabilitate, serverul vechi este distrus și înlocuit instant cu o imagine nouă actualizată. Aplicarea politicilor Zero Trust: limitarea strictă a accesului (Least Privilege) și segregarea privilegiilor administrative.

Slide 15-16: Arhitectura de Referință a unui Pipeline Securizat
    Idei principale: Harta vizuală a fluxului ideal din industrie: cum circulă informația și cum se interconectează teoretic uneltele 

Slide 17-19:Auditarea, Eficiența și Direcții Viitoare
    Idei principale:  Auditarea automată post-deployment: rularea de teste de conformitate prin OpenSCAP și centralizarea log-urilor într-un sistem SIEM. Metricile de succes din industrie: reducerea timpului de deployment de la ore la minute, eliminarea erorilor de configurare umană. Viitorul automatizării: utilizarea AI pentru detectarea anomaliilor de boot în fazele incipiente ale sistemului de operare.


Slide 20-21: Bibliografie & Concluzii
                      
