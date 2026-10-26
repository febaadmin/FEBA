# FEBA — Limites connues

Ce qui n'a **pas** pu être vérifié dans cet environnement, et pourquoi.
Rien ici n'est présenté comme fonctionnel sans preuve.

---

## 00000. Aperçu des bulletins, logo actif, favicons, onglets de visio (26 octobre 2026)

Cette section prévaut sur les suivantes. Validations faites EN LOCAL
uniquement (piles Docker du poste, plugNmeet v2.5.3 local, Chrome réel).

### 00000.1 Logo
- Les PDF DÉJÀ stockés gardent le logo de leur production. Après une
  activation, `manage.py branding_refresh_documents --academy <CODE>` les
  liste (aperçu), puis `--apply` régénère bulletins, reçus et fiches.
  Les rapports mensuels déjà envoyés ne sont pas réécrits (historiques).
- Diplômes et certificats : le blason est dessiné dans le fond. Tant
  qu'aucun logo n'est activé, le visuel officiel est conservé tel quel ;
  après activation, la zone du blason est recouverte d'un aplat couleur
  papier (la texture fine du fond n'y est pas reproduite) puis le logo
  actif y est apposé.
- Les photographies du site (`campus-*logo*.webp`) montrent la façade de
  l'école : ce ne sont pas des logos et elles ne changent pas.
- Une version de logo ACTIVE ne peut pas être supprimée : activer d'abord
  une autre version.

### 00000.2 Favicons
- FEBA : favicons fournis tant qu'aucun logo n'est activé ; ensuite dérivés
  du logo actif (16, 32, 180 px). FEBA FHA : dérivés de son propre logo.
- Les favicons des onglets déjà ouverts changent au chargement suivant de
  l'identité (≤ 1 min, ou immédiatement sur la page Branding).

### 00000.3 Onglet de visioconférence (client plugNmeet)
- Personnalisation installée par `scripts/plugnmeet_setup.sh` (script
  injecté dans le client, conteneur redémarré). Elle doit être relancée à
  chaque mise à jour du client plugNmeet.
- L'en-tête INTERNE de la réunion garde le nom de la salle (affiché par
  plugNmeet) ; seul l'onglet du navigateur porte l'identité de l'académie.
- Si FEBA est injoignable depuis le navigateur, l'onglet garde le titre de
  plugNmeet ; la réunion fonctionne normalement.

### 00000.4 Aperçu des bulletins
- Rendu à la demande, en mémoire (aucun fichier) : quelques secondes par
  aperçu ; filigrane « APERÇU ».

### 00000.5 Non vérifié
Serveur Hetzner, SMTP et SMS réels (BLOCKED), réunion entre réseaux
distincts et partage d'écran (NOT RUN).

---

## 0000. Commentaires des bulletins et visio multi-académies (26 octobre 2026)

Cette section prévaut sur les suivantes.

### 0000.1 Validé en local uniquement
Les parcours réels (commentaires dans Chrome avec le vrai worker Celery ;
réunion plugNmeet dans l'académie FEBA) ont été exécutés sur des piles
Docker isolées du poste de travail. Rien n'a été vérifié sur Hetzner (accès
SSH refusé) ni en préproduction.

### 0000.2 Commentaires — limites assumées
- 1 200 caractères au maximum par commentaire (au-delà, refus explicite :
  la case partage la largeur du bulletin avec le cachet). Un commentaire
  plus long déjà en base (données anciennes) est imprimé intégralement
  dans un bloc pleine largeur, qui peut passer sur une seconde page.
- Une seule opération groupée à la fois par académie (409 sinon).
- Les opérations groupées exigent le worker Celery ; s'il est arrêté,
  l'opération reste « En file d'attente » jusqu'à son retour (et la file
  Redis indisponible renvoie 503, rien n'est annoncé comme lancé).
- Un bulletin absent n'est créé que sur demande explicite, et jamais pour
  un élève sans aucune note sur la période.
- Les PDF générés avant cette version gardent leur nom ; le premier
  nouvel enregistrement leur donne un nom unique.

### 0000.3 Visio — règles de gestion
- Un enseignant ne modifie, ne supprime et ne ferme que ses salles et
  celles des classes qui lui sont affectées (il pouvait auparavant agir sur
  toute salle de l'académie).
- La visioconférence peut toujours être désactivée explicitement pour une
  académie (`settings.features`) : le contrôle serveur reste actif.
- Retour arrière de la migration `schools.0017` : il restaure les
  désactivations explicites, mais FEBA ne perd la visio que si le code
  précédent est aussi redéployé (la valeur par défaut est dans le code).

### 0000.4 Non vérifié
Partage d'écran, réunion entre réseaux distincts (TURN), charge de
plusieurs classes simultanées, SMTP réel, SMS réel, certificat
Let's Encrypt réel : NOT RUN ou BLOCKED (voir § 000).

---

## 000. Version finale validée (25 octobre 2026) — état de référence

Cette section prévaut sur les suivantes, qui décrivent les versions
précédentes. Statuts : PASS · FAIL · BLOCKED · NOT RUN · SIMULATED.

### 000.1 Accès aux systèmes réels — BLOCKED
- **Hetzner** : SSH refusé sur `root@89.167.63.1` et `root@62.238.38.111`
  avec la seule clé fournie (`feba_jitsi_prod`, « Permission denied
  (publickey) »). Aucune autre clé n'a été essayée. Ni le serveur, ni le
  pare-feu, ni le DNS, ni la base de production n'ont été lus ou modifiés.
  plugNmeet n'est **pas déployé** ; Jitsi reste en place.
- **SMTP Hostinger** (`noreply@globalfeba.com`) : aucun mot de passe
  fourni ; aucun e-mail réel envoyé. L'expéditeur est vérifié dans les
  messages capturés par Mailpit (SIMULATED pour la remise réelle).
- **Twilio** (+1 215 715 5406) : aucun identifiant fourni ; aucun SMS réel
  envoyé. Chaîne vérifiée jusqu'au fournisseur simulé (SIMULATED).

### 000.2 Réunion plugNmeet — comportement après une coupure longue
Mesuré sur une instance plugNmeet v2.5.3 réelle (locale) :
- coupure réseau de **10 s** : le participant reste dans la réunion ;
- coupure de **45 s** : plugNmeet retire le participant au bout d'environ
  35 s (`participant_left`). Le client plugNmeet **ne rejoint pas
  automatiquement** la salle au retour du réseau, même si ses contrôles
  restent affichés. L'élève doit cliquer à nouveau sur « Rejoindre »
  dans FEBA ; ce parcours fonctionne (nouveau jeton à usage unique,
  reconnexion comptée dans les présences). La session FEBA, elle, reste
  ouverte pendant et après la coupure.
Ce comportement appartient à plugNmeet/LiveKit ; il n'est pas corrigeable
dans FEBA sans modifier le client plugNmeet.

Réunion longue (PASS) : 1 enseignant + 2 élèves pendant 65 min sur
l'instance réelle, renouvellement préventif des jetons sans coupure — mais
les trois navigateurs tournaient sur une seule machine (caméra et micro
simulés).

### 000.3 Non vérifié en conditions réelles — NOT RUN
- partage d'écran (le navigateur automatisé ne fournit pas de source
  d'écran) ;
- média entre deux réseaux distincts et TURN derrière un pare-feu filtrant
  (tous les participants étaient sur la même machine) ;
- charge de plusieurs classes simultanées ;
- certificat Let's Encrypt réel (le certificat de la pile de recette est
  auto-signé ; `scripts/tls_bootstrap.sh` n'a pas été exécuté contre
  l'ACME réel) ;
- déploiement sur le serveur de production (interdit par la mission et,
  de toute façon, inaccessible).

### 000.4 Environnement des scénarios e2e
Les scénarios `e2e/*.mjs` utilisent Playwright et un Chromium. Hors du
conteneur prévu, indiquer `CHROMIUM_PATH` (Chrome installé) et les URL de
la pile : `FRONT_URL`/`API_URL`/`MAILPIT_URL` (préinscription, rapports
mensuels), `E2E_BASE_URL`/`E2E_API_URL` (v9 ; l'API doit être de même
origine que le frontend, par exemple via le proxy Vite). Les noms de
variables diffèrent d'un script à l'autre (héritage des versions
successives).

### 000.5 Code mort signalé, non supprimé
`frontend/src/hooks/useWebSocket.js` n'est importé nulle part ; la
section `/ws` de nginx est donc sans effet. Laissé en place (aucun
risque, suppression hors périmètre).

---

## 00. Version « plugNmeet, SMS, expéditeur » (25 octobre 2026)

### 00.1 Serveur Hetzner — BLOCAGE EXTERNE
L'accès SSH à `root@89.167.63.1` a été refusé (clé `feba_jitsi_prod` :
« Permission denied (publickey) »). plugNmeet n'est donc **pas déployé** ;
ni le serveur, ni le pare-feu Hetzner, ni le DNS n'ont été inspectés ou
modifiés. Jitsi est intact. Procédure : `PLUGNMEET_DEPLOYMENT_GUIDE.md`.

### 00.2 plugNmeet — ce qui a été vérifié, ce qui ne l'a pas été
Vérifié contre une instance RÉELLE (v2.5.3, locale, Docker) : API signée,
création/fermeture de réunion, refus de signature, webhooks signés reçus
par FEBA, deux participants dans un navigateur, salle d'attente, notes
partagées synchronisées, chat, tableau blanc, présences et reconnexion.
**Non vérifié** : média réel entre deux postes distincts (caméra et micro
non disponibles dans le navigateur de test ; des pistes publiées par un
autre participant ont cependant été reçues), TURN derrière un réseau
filtrant, charge de plusieurs classes simultanées, sous-groupes et
sondages en conditions réelles, PDF sur le tableau blanc.

### 00.3 Fonctions plugNmeet dépendant d'un service non déployé
Enregistrement, diffusion RTMP, flux entrant, sous-titres/transcription/
traduction/résumés IA, appel téléphonique : **désactivés** et déclarés
comme tels (aucune simulation). Voir la matrice du guide plugNmeet, § 10.

### 00.4 SMS — BLOCAGE EXTERNE
Aucun compte Twilio ni jeton disponible : **aucun SMS réel envoyé**, et le
numéro +1 (215) 715-5406 n'a pas pu être vérifié (propriété, capacité
SMS, autorisation vers le Bénin, enregistrement A2P 10DLC pour les
destinataires américains). Le fonctionnement est démontré par des tests
qui simulent Twilio au niveau HTTP, ce qui ne prouve pas la réception.
Commande à exécuter : `SMS_CONFIGURATION_GUIDE.md` § 7.

### 00.5 SMS — limites assumées
- Consentement explicite requis par défaut : tant que les familles n'ont
  pas accepté (Mon profil), aucun SMS ne part. Décision juridique à
  prendre pour `SMS_REQUIRE_EXPLICIT_CONSENT=False`.
- Fiche d'inscription FHA : aucun consentement SMS n'y est recueilli ; un
  parent sans compte FEBA ne reçoit donc pas de SMS (raison enregistrée).
- Les messages de sécurité (réinitialisation de mot de passe) ne sont
  jamais copiés par SMS (choix de sécurité).
- Pas de vérification du numéro par code envoyé (OTP) : le numéro est
  validé (format, mobile) mais sa possession n'est pas prouvée.
- Twilio n'offre pas de clé d'idempotence : un arrêt du serveur dans les
  millisecondes entre l'acceptation d'une partie et son enregistrement
  peut la faire renvoyer.
- Coût : un SMS en UCS-2 (accents « ê », « ç », tirets « — ») compte
  70 caractères par segment ; une relance détaillée = plusieurs segments.

### 00.6 Expéditeur noreply@globalfeba.com — À TESTER EN ENVIRONNEMENT RÉEL
Le code n'utilise plus `noreply@feba.bj` (tests sur chaque chemin). La
boîte `noreply@globalfeba.com` chez Hostinger, son mot de passe SMTP et
l'activation DKIM n'ont pas pu être vérifiés ; aucun e-mail réel n'a été
envoyé. DNS relevé : SPF Hostinger, DKIM `hostingermail-a`, DMARC `p=none`.

### 00.7 Session pendant les visioconférences
Corrigé et testé (rotation concurrente, onglets multiples, coupure
réseau, renouvellement préventif). Le jeton de renouvellement garde sa
durée serveur (7 jours) : une session inactive plus longtemps se termine,
volontairement.

## 0. Version « audit complet » (octobre 2026) — points ouverts

### 0.1 Jours d'échéance de la grille 2026-2027 — DÉCISION MÉTIER
**BLOCAGE EXTERNE (décision de l'administration).** L'affiche des frais
2026-2027 donne le MOIS de chaque tranche (septembre, novembre, janvier),
pas le jour. `fee_plans/feba_2026_2027.json` retient le dernier jour du
mois ; la date limite des frais d'inscription (30/09/2026) et les mois de
garderie (septembre → juin) sont également des hypothèses. Rien n'est
chargé sans `--apply`, et les relances restent désactivées tant que
`PAYMENT_REMINDERS_ENABLED` n'est pas activé. À confirmer avant mise en
service.

### 0.2 Noms des niveaux en production
**À TESTER EN ENVIRONNEMENT RÉEL.** `load_fee_plan` associe les tarifs aux
niveaux par leur NOM (« CE1 », « Maternelle 1 », « CI »…). La base de
démonstration utilise « CP1 / CP2 » : la commande les signale comme sans
tarif. Lancer la simulation (sans `--apply`) sur la base de production et
lire la liste « Niveaux sans tarif ».

### 0.3 Abonnements aux services optionnels
**LIMITATION CONNUE.** Cantine, transport et garderie ne sont dus que par
les élèves déclarés « abonnés » (onglet Échéanciers → Élèves). Aucune
donnée d'abonnement n'existait auparavant : tant qu'elles ne sont pas
saisies, aucune relance n'est envoyée pour ces services — c'est voulu
(aucune relance injustifiée), mais cela signifie aussi qu'aucun retard de
cantine n'est relancé avant la saisie.

### 0.4 Paiements historiques sans heure
**LIMITATION CONNUE.** L'heure n'a jamais été enregistrée avant cette
version. La migration `payments.0011` reprend l'horodatage de saisie
uniquement quand il tombe le jour même du paiement ; les autres paiements
anciens affichent la date seule avec « heure n.e. ». Aucune heure n'est
inventée.

### 0.5 Livraison réelle des e-mails
**À TESTER EN ENVIRONNEMENT RÉEL / BLOCAGE EXTERNE.** Tous les envois ont
été vérifiés jusqu'au protocole SMTP contre Mailpit (serveur de test
local) : contenu, destinataires, pièces jointes octet pour octet. Aucun
identifiant de fournisseur réel n'était disponible : la remise par un
fournisseur SMTP de production, et les enregistrements SPF/DKIM/DMARC,
n'ont **pas** été testés. Commande à lancer, vers UNE adresse de test
autorisée : `EMAIL_CONFIGURATION_GUIDE.md` § 4.

Même avec un fournisseur réel, FEBA ne peut constater que l'**acceptation**
par le serveur de messagerie (statut « Accepté par le serveur de
messagerie — réception non garantie ») : la réception dans la boîte du
destinataire, le classement en indésirables ou un rebond asynchrone ne
remontent pas jusqu'à l'application (pas de webhook de rebond).

### 0.5 bis Boîte d'envoi et pièces jointes — limites assumées
- **Pas d'antivirus.** Les pièces jointes sont filtrées par extension,
  par signature binaire (un `.exe` renommé en `.pdf` est refusé), par
  taille unitaire et totale ; aucune analyse antivirale n'est faite.
  Brancher ClamAV (ou équivalent) avant d'accepter des fichiers de tiers.
- **Envois antérieurs non archivés.** Les envois journalisés avant la
  migration `notifications.0006` n'ont pas de contenu conservé : la boîte
  d'envoi affiche « Contenu non archivé pour cet envoi historique » et ne
  propose pas de relance (rien à renvoyer fidèlement).
- **Liens sensibles masqués.** Les messages porteurs de jetons
  (réinitialisation de mot de passe, liens signés) sont archivés avec les
  liens remplacés par `[lien de sécurité masqué]` : on peut lire le
  message, pas réutiliser le lien. Une relance de ces messages renvoie la
  version masquée ; il faut redemander un nouveau lien.
- **`localhost` / `127.0.0.1` ne sont pas considérés comme Mailpit.** Un
  relais SMTP local peut être réel (Postfix) : seuls les hôtes `mailpit`,
  `mailhog`, `mailcatcher`, `smtp4dev`, `maildev` sont classés « capture »
  par défaut. Pour un Mailpit sur 127.0.0.1, ajouter l'hôte à
  `EMAIL_CAPTURE_HOSTS`.
- **Refus d'authentification SMTP** : vérifié par simulation (Mailpit
  n'exige pas d'authentification) ; le message d'erreur réel dépend du
  fournisseur.
- **Rétention.** Contenus et pièces jointes archivés sont conservés sans
  purge automatique (volume `private_media`). Prévoir une politique de
  rétention (RGPD) avant un usage intensif.

### 0.6 Suppression d'une conversation
**LIMITATION CONNUE — décision métier.** Supprimer une conversation
(messagerie interne) l'efface aussi pour l'interlocuteur. Le comportement
n'a pas été modifié faute de règle métier explicite (suppression pour
soi seul ou pour tous).

### 0.7 Point d'API `payments/pending`
**LIMITATION CONNUE.** Cette route renvoie les paiements `is_confirmed=False`,
c'est-à-dire ANNULÉS, sous le nom « pending ». Aucun écran ne l'utilise ;
elle est conservée pour ne pas casser d'éventuels appels externes.

## 1. Visioconférence — ce qui exige un environnement réel

### 1.1 Réunion à deux participants (§32)

**À TESTER EN ENVIRONNEMENT RÉEL.**

Deux navigateurs distants et un accès média réel sont nécessaires.

*Protocole.* Deux comptes de la même classe, deux machines sur des
réseaux différents, rejoindre la même salle. Vérifier : chacun voit et
entend l'autre ; la liste des participants en compte exactement deux ;
personne n'y apparaît en double.

### 1.2 Stabilité sur 30 minutes (§33)

**À TESTER EN ENVIRONNEMENT RÉEL.**

La cause des déconnexions périodiques est identifiée et corrigée — le
composant était détruit et recréé toutes les 30 secondes par le
`refetchInterval` du parent — et la conférence vit désormais dans un
onglet séparé, hors de portée de ce cycle. Une session longue reste à
observer.

*Protocole.* Réunion à deux, 30 minutes. Surveiller : reconnexions
spontanées, participants fantômes, `docker stats` sur `jvb` et `prosody`,
journaux Prosody.

### 1.3 Poignée de main WebSocket de bout en bout

**À TESTER EN ENVIRONNEMENT RÉEL.**

Le mandataire de cet environnement **ne relaie aucune mise à niveau
WebSocket** — vérifié : un service public de test échoue exactement de la
même façon. Le code obtenu sur `meet.globalfeba.com` n'est donc **ni** une
preuve de panne **ni** une preuve de bon fonctionnement.

Ce qui **est** vérifié : le chemin `/xmpp-websocket` existe et répond
(pas de 404), `config.js` pointe bien `wss://meet.globalfeba.com/xmpp-websocket`,
et le fichier nginx du dépôt traite `Upgrade` pour `/xmpp-websocket` et
`/colibri-ws/`.

*Protocole.* Depuis un poste ordinaire :
`wscat -c wss://meet.globalfeba.com/xmpp-websocket` doit répondre
`101 Switching Protocols`.

### 1.4 Refus d'adhésion anonyme sur l'instance en service

**À TESTER EN ENVIRONNEMENT RÉEL.**

Chromium n'a **aucun accès sortant** depuis cet environnement
(`example.com` échoue également). La configuration
`ENABLE_AUTH=1 / ENABLE_GUESTS=0 / AUTH_TYPE=jwt` est vérifiée dans les
fichiers Compose ; son application effective sur l'instance en service ne
l'est pas.

*Protocole.* Ouvrir `https://meet.globalfeba.com/salle-test-xyz` dans un
navigateur, **sans passer par FEBA**. L'accès doit être refusé. Si une
salle s'ouvre, n'importe qui sur Internet peut créer des salles sur votre
serveur.

### 1.5 ICE / JVB / UDP 10000 (§24)

**À TESTER EN ENVIRONNEMENT RÉEL.**

`JVB_ADVERTISE_IPS` et l'ouverture d'UDP 10000 ne se vérifient que depuis
un client externe. Sans ce port, les participants entrent dans la salle
et ne se voient pas — le symptôme est distinct d'une panne de
signalisation, et c'est ce qui rend le contrôle nécessaire.

*Protocole.* `nc -vzu 89.167.63.1 10000` depuis un réseau externe, puis
une réunion à deux pour confirmer le flux média.

### 1.6 TURN / Coturn (§25)

**À TESTER EN ENVIRONNEMENT RÉEL.**

Aucune infrastructure TURN n'est configurée à ce jour. Elle devient
nécessaire dès qu'un participant se trouve derrière un pare-feu qui
bloque UDP — Wi-Fi scolaire, réseau d'entreprise, NAT restrictif, certains
opérateurs mobiles. C'est une population réelle pour une école en ligne
destinée à la diaspora.

*Ce qui n'est pas fait.* Coturn n'est ni installé ni configuré. Le
déclarer « prêt » sur la foi d'un fichier de configuration serait
exactement le genre d'affirmation que §48 interdit.

*Protocole d'évaluation.* Tenter une réunion depuis un réseau bloquant
l'UDP sortant. Si la connexion échoue, TURN est requis.

---

## 2. Docker

**LIMITATION CONNUE.** Le démon Docker est indisponible dans cet
environnement. `docker compose config` est vérifiable — et a été exécuté,
5 assemblages valides — mais `docker compose up` ne l'est pas.

---

## 3. Écart entre le nginx du dépôt et l'instance en service

**EXTERNAL ACTION REQUIRED.**

Mesuré sur `meet.globalfeba.com` :

| En-tête | Instance en service | Fichier du dépôt |
|---|---|---|
| `Strict-Transport-Security` | `max-age=63072000` | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | `nosniff` | `nosniff` |
| `Referrer-Policy` | **absent** | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | **absent** | `frame-ancestors 'self' https://globalfeba.com` |

L'instance en service ne sert donc **pas** la configuration du dépôt. Ce
n'est pas nécessairement un défaut — cette configuration n'a jamais été
déployée, conformément aux consignes — mais toute conclusion sur la
sécurité ou la stabilité doit en tenir compte.

L'absence de `frame-ancestors` est la plus notable : elle laisse
n'importe quel site intégrer la conférence dans une iframe.

---

## 4. Certificat TLS

**PASS VÉRIFIÉ, avec échéance.** Certificat valide pour
`meet.globalfeba.com`. Le renouvellement automatique n'a pas pu être
vérifié depuis cet environnement.

*À vérifier.* Que le renouvellement ACME est en place et que le
`location /.well-known/acme-challenge/` du proxy ne l'empêche pas.

---

## 5. Deux adresses IP distinctes

**Information d'audit.**

```
globalfeba.com       → 62.238.38.111
meet.globalfeba.com  → 89.167.63.1
```

Architecture parfaitement valable — Jitsi gagne à être isolé — mais qui
mérite d'être confirmée comme **voulue**.

---

## 6. Ce qui n'est PAS une limite

Pour éviter toute ambiguïté, ces points sont **vérifiés** :

- la contradiction de la capture est supprimée, à la source, dans les
  deux couches (11/11 en navigateur réel) ;
- le backend valide et refuse en 400 sur les **deux** chemins d'écriture ;
- les matières d'une autre académie sont refusées ;
- les trois bulletins sont conformes, PDF réels inspectés ;
- FEBA ne subit aucune régression, et la garantie est structurelle ;
- un élève d'une autre classe reçoit 403 **avec le motif** ;
- un élève ne peut pas obtenir la modération en la demandant ;
- `JITSI_APP_SECRET` est absent du bundle construit ;
- aucun repli `meet.jit.si` n'existe dans le code ;
- aucune fuite sur `/.env`, `/.git/config`, `/api/env`.

---

## 7. Identité institutionnelle de FEBA French Heritage Academy

Ces deux points ne sont pas des défauts logiciels et ne se corrigent pas
en écrivant du code. Ils étaient documentés dans les livraisons
précédentes et le restent : une limitation qu'on cesse d'écrire redevient
un oubli à la relecture suivante.

### 7.1 Cachet officiel

**Aucun cachet officiel FEBA FHA n'a été fourni ; aucun cachet d'une autre
académie n'est réutilisé.**

Les documents de l'académie en ligne — reçus, certificats, fiches —
sortent donc **sans cachet**. Ce n'est pas un oubli et ce n'est pas
réparable en écrivant du code : le visuel n'existe pas dans les éléments
transmis.

Apposer `cachet_feba.png` à la place serait pire que l'absence : cette
image porte en couronne « COMPLEXE SCOLAIRE FAITH & EXCELLENCE BILINGUAL
ACADEMY ». Sur un certificat de l'académie en ligne, elle y estampille le
nom d'une autre personne morale — sur la pièce qui fait foi. Un document
sans cachet se voit et se corrige ; un document au cachet d'un autre
établissement circule et fait autorité.

**Pour lever cette limitation :** déposer le cachet officiel FHA dans
`backend/feba_project/static_files/` et renseigner son nom dans
`ACADEMY_DEFAULTS["FEBA_FHA"]["stamp"]`
(`backend/apps/schools/branding.py`). Rien d'autre n'est à modifier.

### 7.2 Nom d'établissement sur deux lignes — limitation levée

Cette limitation figurait dans les livraisons précédentes. Elle **est
levée** : un nom d'établissement de **79 caractères est composé sur deux
lignes** sans chevauchement ni troncature, l'interligne étant calculé à
partir de la taille de police au lieu d'être laissé à sa valeur par défaut
(`backend/apps/payments/pdf_generator.py`).

Elle est maintenue dans ce document uniquement pour dire qu'elle n'a plus
lieu d'être : la laisser inscrite ferait renoncer quelqu'un à un service
qui fonctionne.
