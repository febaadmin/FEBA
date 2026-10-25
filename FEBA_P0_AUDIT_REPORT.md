# FEBA — Rapport : plugNmeet, session, expéditeur, SMS, audit

> **DOCUMENT HISTORIQUE** — il décrit une version antérieure de FEBA ; ses résultats n'ont pas été
> rejoués tels quels sur cette version. Références à jour : `DOCUMENTATION_INDEX.md`, `FINAL_REPORT.md`.

Branche `fix/feba-plugnmeet-sms-p0`, partie de la version
`FEBA_VERSION_EMAILS_CORRIGEE_AUDIT_COMPLET` (SHA-256
`e20c8989…6261`, commit `d9aac53`, toutes ses corrections conservées).

Statuts : **PASS VÉRIFIÉ** (exécuté, preuve) · **CORRIGÉ** (défaut
reproduit, corrigé, test de non-régression) · **SIMULÉ** (vérifié contre un
service simulé — ne prouve pas le fonctionnement réel) · **NON EXÉCUTÉ**
(avec la raison) · **BLOCAGE EXTERNE**.

**La mission n'est PAS déclarée terminée** : deux exigences P0 dépendent
d'accès que je n'ai pas (serveur Hetzner, compte SMS). Tout ce qui pouvait
être fait sans eux l'a été ; ce qui reste est écrit en § 7.

---

## 1. Synthèse

| Exigence | Code | Vérification réelle | Statut |
|---|---|---|---|
| P0-1 plugNmeet remplace Jitsi | intégration complète | instance plugNmeet **réelle** (v2.5.3, Docker local) + navigateur, 2 participants | PASS VÉRIFIÉ en local · **BLOCAGE EXTERNE** pour Hetzner |
| P0-2 pas de déconnexion FEBA en réunion | cause trouvée et corrigée | essai réel de 62 min, coupure serveur comprise (§ 3) | CORRIGÉ · PASS VÉRIFIÉ |
| P0-3 `noreply@globalfeba.com` | tous les chemins | en-tête From lu dans Mailpit | CORRIGÉ · délivrabilité réelle À TESTER |
| P0-4 SMS (e-mails) | mécanisme central complet | Celery réel, transport « capture » | SIMULÉ · **BLOCAGE EXTERNE** (aucun compte SMS) |
| P0-4 SMS (relances) | 10 scénarios | tests automatisés | SIMULÉ · **BLOCAGE EXTERNE** |

## 2. P0-1 — plugNmeet

**Audit de l'existant.** Jitsi : JWT HS256 signé par FEBA, iframe
`external_api.js`, présences par appels « rejoindre/quitter », aucun
suivi serveur des sorties.

**Protocole vérifié** (documentation officielle + code source
plugNmeet-server v2.5.3, puis instance réelle) : API `POST /auth/<méthode>`
signée HMAC-SHA256 du corps exact (`API-KEY`, `HASH-SIGNATURE`) ; jeton
d'adhésion à usage unique (`/?access_token=`) ; webhooks signés
(`Hash-Token` : JWT HS256, revendication `sha256` du corps).

**Intégration** (`apps/virtualclass/plugnmeet.py`, `meetings.py`) :
- droits FEBA inchangés (`assert_can_join` : académie, fonction activée,
  rôle ciblé, classe, état) contrôlés AVANT tout appel à plugNmeet ;
  enseignants/admins modérateurs ; un élève ne rouvre pas un cours fermé
  (409) ; une autre académie : 404/403 sans révéler la salle ;
- jeton d'adhésion émis par le serveur, jamais stocké ni journalisé,
  réponse `no-store` ; clé et secret absents du frontend ;
- fermeture RÉELLE (`endRoom`) ; si plugNmeet est injoignable, la salle
  n'est pas déclarée terminée (503) ;
- statut FEBA aligné : webhooks `room_started/room_finished`, endpoint
  `meeting-status`, réconciliation Celery Beat toutes les 10 min ;
- présences recalculées depuis les événements : idempotence (`event_id`
  unique), ordre indifférent, reconnexions comptées, durée effective,
  sous-groupes rattachés au cours, déconnexion brutale close par la fin de
  réunion, lien à l'inscription annuelle conservé ;
- toutes les fonctions déclarées explicitement (mesuré : une fonction
  omise est ACTIVÉE par défaut) ; enregistrement/RTMP/IA désactivés faute
  de service (matrice : `PLUGNMEET_DEPLOYMENT_GUIDE.md` § 10) ;
- Jitsi conservé UNIQUEMENT comme moteur de retour arrière
  (`VIDEO_PROVIDER=jitsi`), tests rattachés.

**Défauts trouvés par l'essai réel, corrigés :**

| Défaut | Cause | Correction | Test |
|---|---|---|---|
| Fermeture : « injoignable » après 10 s | `endRoom` sur réunion déjà close attend ~12 s (mesuré) ; code `ROOM_NOT_FOUND` non reconnu | contrôle `isRoomActive` préalable, délai propre (45 s), code reconnu | `EndAndStatusTests`, `PlugNmeetLiveTests` |
| Webhooks refusés (HTTP 400) | hôte du webhook absent d'`ALLOWED_HOSTS` — invisible | contrôle `manage.py check` (`virtualclass.W001`) | `ConfigurationCheckTests` |
| Durée de présence 0 | entrée perdue (refusée), seule la sortie reçue | présence comptée depuis l'adhésion FEBA | `test_entree_perdue…` |
| Base gonflée | `track_published`, `artifact_created`… archivés | seuls 4 événements utiles conservés | `test_evenements_secondaires…` |
| Bandeau « visio indisponible » chez les élèves | 403 du diagnostic interprété comme panne | bandeau réservé aux enseignants et plus | frontend |

**Parcours navigateur réel** (FEBA isolé + plugNmeet local) : FEBA →
jeton → client plugNmeet ; administratrice modératrice + élève ;
salle d'attente et admission ; partage d'écran verrouillé pour l'élève ;
notes partagées synchronisées (« Devoir FEBA : exercice 3 page 42 ») ;
chat élève → enseignante ; tableau blanc affiché chez l'élève ; sortie →
page FEBA « session toujours ouverte » ; reconnexion comptée (1) ;
fermeture depuis FEBA → participants déconnectés, `room_finished` reçu,
salle « Terminée », présence 192 s = 39 + 153 s. Un autre participant
(compte super-administrateur, depuis le même panneau) a publié des pistes
audio/vidéo reçues par plugNmeet.

**Déploiement Hetzner** : BLOCAGE EXTERNE (clé SSH refusée). Livré :
Compose isolé, versions figées, secrets générés hors dépôt, proxy HTTPS
(`nginx -t` validé ; acheminement WebSocket à travers ce proxy NON EXÉCUTÉ
en local : il exige que plugNmeet joigne sa propre URL publique en TLS),
pare-feu, DNS, recette, bascule, retour arrière.

## 3. P0-2 — Session FEBA pendant les réunions

**Cause racine** (reproduite par `sessionInterceptor.test.js`, qui échoue
2/3 sur l'ancien intercepteur) : rotation + liste noire des jetons de
renouvellement ; à l'expiration du jeton d'accès (60 min), plusieurs 401
simultanés lançaient chacun un renouvellement avec le même jeton → le
second était refusé → `clearAuth()` → /login. Même effet entre l'onglet
FEBA et l'onglet de la réunion, et sur coupure réseau. Second défaut :
`useRestoreUser` effaçait la session sur une simple erreur réseau.

**Correction** : renouvellement unique (promesse partagée + verrou
`navigator.locks` entre onglets + relecture du stockage partagé),
adoption du jeton d'un autre onglet, aucune déconnexion sans refus
explicite du serveur, renouvellement préventif 5 min avant expiration,
synchronisation des onglets, fermeture de l'onglet de réunion sans effet
sur la session. Aucune prolongation au-delà de la durée serveur.

**Vérification réelle — essai de 62 minutes** (pile FEBA isolée sur
PostgreSQL + plugNmeet réel, navigateur, jeton d'accès de 60 min) :

| Mesure | Résultat |
|---|---|
| Réunion | 01:43:14 → 02:46:04 UTC (62,8 min), 2 participants |
| Présences (webhooks réels) | administratrice 62,6 min, élève 62,1 min |
| Onglet FEBA ouvert pendant tout l'essai (liste des salles rafraîchie toutes les 30 s) | jamais déconnecté |
| Renouvellement | UNE rotation, préventive, ~4 min avant l'expiration (jeton suivant valable jusqu'à 03:30:58) ; côté serveur, un seul jeton mis en liste noire, aucun refus |
| Coupure à 02:10-02:12 (backend et serveur de développement reconstruits) | session conservée, mêmes jetons |
| Fin de réunion depuis FEBA | les deux onglets de réunion reviennent sur « Votre session FEBA est toujours ouverte » ; « Retour à FEBA » → tableau de bord, même utilisateur |

Observation réelle : un participant a quitté la réunion pendant la
coupure de 02:10 ; son événement de sortie n'a pas été reçu. Sa présence
a été close par la fin de réunion (comportement prévu, § 2).

## 4. P0-3 — Expéditeur

Recherche : `DEFAULT_FROM_EMAIL` (défaut `noreply@feba.bj`), deux
`.env.*.example`, `SERVER_EMAIL` absent (Django écrivait depuis
`root@localhost`), une fonction d'expéditeur dupliquée et morte
(`monthly_reports.sender_for`). Les adresses `@feba.bj` du jeu de
démonstration sont des identifiants de connexion : non modifiées.

Correction : défaut `noreply@globalfeba.com`, `SERVER_EMAIL` aligné, une
seule fonction (`mailer.sender_for`), l'adresse retirée remplacée à l'envoi
même si un `.env.prod` la contient encore (envois en file, `send_mail`
direct, `mail_admins`), contrôles `notifications.W001/W002`. Preuve sur
l'ancien code : From réel `noreply@feba.bj`, `SERVER_EMAIL=root@localhost`.
`test_email_sender_globalfeba` lit le From produit par chaque chemin.
DNS relevé et reste à faire chez Hostinger : `EMAIL_CONFIGURATION_GUIDE.md`.

## 5. P0-4 — SMS

Voir `SMS_CONFIGURATION_GUIDE.md`. Inventaire des chemins d'envoi : tous
passent par `mailer` (acquis de la mission précédente, verrouillé par un
test AST) ; le SMS y est déclenché pour chaque destinataire. Relances :
un seul mécanisme (`run_reminders`, Beat et manuel) ; un SMS par
événement, même pour une relance sans e-mail ; revérification au moment
de l'envoi.

Défauts trouvés en écrivant les tests, corrigés : espace final retiré du
texte (le SMS doit être identique) ; clé d'événement dépendante de
l'ordre des relances (une reprise aurait produit un second SMS).

## 6. Audit global

| Constat | Statut | Test |
|---|---|---|
| Limites de débit « par IP » en réalité globales derrière nginx | CORRIGÉ | `test_ratelimit_client_ip` |
| Image Mailpit non figée (`latest`) | CORRIGÉ (v1.31.4) | composition |
| Routes frontend → backend : 227 chemins, 0 orphelin | PASS VÉRIFIÉ | sonde |
| Routes accessibles sans authentification : seules les publiques par conception | PASS VÉRIFIÉ | sonde (556 routes) |
| Gestionnaires d'exception muets : 4, tous bénins | PASS VÉRIFIÉ | analyse AST |

## 6 bis. Tests

| Suite | Résultat (dépôt) |
|---|---|
| Backend PostgreSQL 16 + Mailpit SMTP réel + plugNmeet réel | 1629 réussis, 0 échec, 0 ignoré |
| Backend SQLite | 1615 réussis, 9 ignorés (services réels absents), 0 échec |
| Frontend Vitest | 306 / 306 |
| ESLint | 0 erreur (80 avertissements préexistants) |
| Build Vite + recherche de secrets dans le bundle | OK, aucun secret ni numéro |
| Assemblages Compose | 6 / 6 valides (dont plugNmeet + proxy) |

Nouveaux tests : `test_plugnmeet_integration` (39, dont 3 contre l'instance
réelle), `test_sms_mirror` (40), `test_email_sender_globalfeba` (16),
`test_ratelimit_client_ip` (5), `tokenRefresh.test` (8),
`sessionInterceptor.test` (3), `VirtualRoomEnded.test`,
`SmsPreferencesCard.test`, et les cas plugNmeet de
`VirtualRoomSession.test`. Tests modifiés (sans affaiblir une assertion) :
4 classes Jitsi rattachées explicitement au moteur de retour arrière ;
`restoreUser.test` (le cas « erreur sans réponse HTTP » figeait le défaut
réseau ; un cas 401 et un cas réseau le remplacent) ; fixtures
d'expéditeur passées à `noreply@globalfeba.com` (deux tests vérifient
désormais que l'ancienne adresse est corrigée).

**Démontrés en échec sur l'ancien code** : `sessionInterceptor.test` (2/3) ;
expéditeur (From réel `noreply@feba.bj`, `SERVER_EMAIL=root@localhost`) ;
limites de débit (même compteur pour tous, dans le test lui-même).

Vérification de l'archive livrée (extraction neuve, dépendances
réinstallées, suites complètes) : `DELIVERY_VERIFICATION.txt`, à côté de
l'archive.

## 7. Ce qui reste à faire (accès requis)

1. **Hetzner** : donner un accès SSH (ou exécuter) `PLUGNMEET_DEPLOYMENT_GUIDE.md`
   §§ 2-6 ; recette réelle ; bascule § 7.
2. **SMS** : compte Twilio propriétaire du +1 215 715 5406 ;
   `manage.py sms_check` puis `--to <numéro autorisé>` ; Geo permissions
   Bénin ; A2P 10DLC pour les numéros américains ; décision sur le
   consentement ; `SMS_ENABLED=True`.
3. **E-mail** : boîte `noreply@globalfeba.com` chez Hostinger, DKIM actif,
   `email_check --to`, lecture des en-têtes `spf/dkim/dmarc=pass`.
