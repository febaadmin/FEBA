# FEBA — Rapport de corrections : e-mails, pièces jointes, boîte d'envoi

> **DOCUMENT HISTORIQUE** — il décrit une version antérieure de FEBA ; ses résultats n'ont pas été
> rejoués tels quels sur cette version. Références à jour : `DOCUMENTATION_INDEX.md`, `FINAL_REPORT.md`.

Branche `fix/feba-email-outbox`, partie de la version de référence
`FEBA_VERSION_CORRIGEE_AUDIT_COMPLET` (commit `04595a7`, toutes ses
corrections conservées). Résultats chiffrés : `EMAIL_OUTBOX_VALIDATION_REPORT.md`.
Limites : `KNOWN_LIMITATIONS.md` § 0.5 et 0.5 bis. Mode d'emploi :
`EMAIL_CONFIGURATION_GUIDE.md`.

---

## 1. « Les e-mails n'arrivent pas dans la boîte de réception »

### Diagnostic (conteneurs `backend-dev`, `celery-dev`, `celery-beat-dev`)
Configuration effective lue dans les trois conteneurs, secrets masqués :
transport `smtp`, hôte `mailpit:1025`, sans mot de passe, identique
partout. Les messages envoyés depuis FEBA, y compris le test vers une
adresse `ymail.com`, se trouvaient bien **dans Mailpit**.

### Cause racine
Le stack Docker de développement envoie à **Mailpit**, un serveur de test
qui **capture** les messages et ne les distribue jamais sur Internet.
C'est le comportement voulu en développement. Le défaut était que FEBA
affichait ces messages comme « envoyés par un fournisseur réel » :
`used_real_provider` excluait seulement les backends console/mémoire, si
bien que tout SMTP, Mailpit compris, passait pour une remise réelle.
L'administrateur attendait donc une réception que rien ne pouvait
produire.

### Correction
- Classement du transport (`mailer.current_transport`) : `console`,
  `memory`, `file`, **`capture`** (mailpit, mailhog, mailcatcher, smtp4dev,
  maildev, ou `EMAIL_CAPTURE_HOSTS`), `smtp` (réel), `unconfigured`.
  `EMAIL_DELIVERY_MODE` permet de forcer `capture` ou `real`.
- Ce classement est enregistré **sur chaque envoi** (`transport`,
  `smtp_host`, `message_id`). Les libellés affichés deviennent :
  - « Capturé par le serveur de test (Mailpit) — non distribué sur Internet »
  - « Accepté par le serveur de messagerie (réception non garantie) »
  - Le mot « reçu » n'est jamais employé.
- `email_check` réécrit : transport, hôte, joignabilité réseau, aucun
  secret. Codes de sortie : 0 = accepté par un fournisseur réel,
  1 = échec, 2 = transport de test/local.
- Administration → Boîte d'envoi → **Configuration SMTP** affiche la
  configuration (utilisateur masqué) et permet un envoi de test vers une
  adresse saisie. Cet envoi est limité (`EMAIL_TEST_MAX_PER_HOUR`), tracé
  (purpose `smtp_test`) et réservé aux administrateurs.
- Mode réel documenté (`EMAIL_CONFIGURATION_GUIDE.md` § 3 : paramètres,
  SPF/DKIM/DMARC). Aucun identifiant n'a été inventé.

### Envois silencieux supprimés
Trois chemins contournaient le journal. Un test AST
(`test_email_single_path.py`) les détecte sur `04595a7` et échoue :
| Fichier | Défaut | Correction |
|---|---|---|
| `website/fha_notifications.py` | `send_mail(fail_silently=True)` : un échec disparaissait | `send_tracked_email`, un envoi tracé par destinataire |
| `monthly_reports/emails.py` | `EmailMultiAlternatives.send()` direct ; Mailpit compté « envoyé » | `send_tracked_email` + PDF joint ; une capture n'est pas une remise |
| tout futur `send_mail` | aucune trace | `TrackingEmailBackend` : journalise tout message non tracé (liens de sécurité masqués dans l'archive) |

Un échec SMTP n'interrompt jamais l'opération métier : `send_tracked_email`
ne lève pas d'exception, et l'erreur exacte est conservée.

## 2. Pièces jointes des e-mails groupés

- **Interface** (`MassEmail.jsx`, composant `AttachmentPicker`) : sélection
  multiple, nom, taille, retrait, limites affichées, refus expliqué
  (format, taille unitaire, total, nombre).
- **Serveur** (`notifications/attachments.py`) : liste blanche
  d'extensions, **signature binaire** contrôlée (un exécutable renommé
  `.pdf` est refusé), taille par fichier, taille totale, nombre de
  fichiers, nom assaini (aucun chemin, aucun `..`).
- **Stockage privé** : `PRIVATE_MEDIA_ROOT/email_attachments/`, hors
  `MEDIA_ROOT` public. Le téléchargement passe uniquement par l'API, avec
  contrôle de l'académie, `nosniff`, `no-store` et une CSP `sandbox`. Une
  seule copie par campagne, dédupliquée par SHA-256. Volume
  `private_media_prod` ajouté au backend et au worker en production.
  `client_max_body_size 25M` dans nginx.
- **Aucun antivirus** : ce point n'est pas prétendu (voir les limites).

## 3. Boîte d'envoi (Administration / Super-administration → « Boîte d'envoi »)

- **Contenu archivé** (`EmailContent`, `EmailAttachment`), partagé par tous
  les destinataires d'une campagne, avec un statut par destinataire
  (`EmailDelivery`) et un historique des tentatives
  (`EmailDeliveryAttempt`). Migration : `notifications.0006`.
- **Liste** : date, académie, destinataire, objet, origine, statut,
  pièces jointes et tentatives. Filtres : statut, origine, destinataire,
  objet, texte libre, période, avec ou sans pièces jointes. Pagination
  côté serveur et compteurs par statut.
- **Détail** :
  - texte brut ;
  - HTML dans une `iframe sandbox=""` : aucun script, aucun formulaire ;
  - pièces jointes : aperçu (images, PDF) ou téléchargement, récupérées
    avec le jeton et jamais via une URL publique ;
  - historique des tentatives et erreur exacte.
- **Envois antérieurs** : « Contenu non archivé pour cet envoi
  historique », sans relance.
- **Jetons de sécurité** : ils sont masqués dans l'archive, et ces
  messages ne sont **jamais rejoués** depuis l'archive masquée (voir § 4).
- **Isolation multi-académies** côté serveur. Un administrateur ne voit
  que son académie : détail par ID, pièce jointe et relance d'une autre
  académie renvoient 404 ; un `academy_id` forcé renvoie 403 ; la liste
  ne contient aucune ligne d'une autre académie. Le super-administrateur
  choisit l'académie.

## 4. Statuts et relances

| Statut | Libellé |
|---|---|
| `queued` | Enregistré — en file d'attente |
| `pending` | Envoi en cours |
| `sent` | Accepté par le serveur de messagerie (ou « Capturé… » si Mailpit) |
| `retry` | Échec temporaire — nouvel essai programmé (5, 30 puis 180 min ; 4 tentatives) |
| `failed` | Échec définitif |

- **Relance manuelle** : réservée aux administrateurs. La ligne est
  verrouillée (`select_for_update(of=("self",))`), donc deux clics ou deux
  onglets ne produisent qu'un envoi. Le verrou est aussi posé côté
  interface. Un envoi réussi n'est jamais renvoyé (409). L'historique
  est conservé.
- **Relance automatique** : `retry_due_deliveries` rejoue le contenu
  archivé, pièces jointes comprises, avec `skip_locked` entre workers.
- **Campagnes** : un envoi est créé par destinataire à la mise en file.
  « Relancer les échecs » remet en file uniquement les échecs.
- **Corrigé pendant l'audit** : un message porteur d'un lien de sécurité
  (archive masquée) aurait été rejoué **avec le lien masqué**, puis
  affiché « accepté ». Désormais :
  - un échec temporaire de ce message devient définitif, avec
    l'explication « Demander un nouveau lien » ;
  - la relance manuelle renvoie 409 ;
  - la relance automatique n'envoie rien.
  Tests : `RedactedReplayTests`.

## 5. Autres défauts trouvés pendant l'audit

| Défaut | Correction | Test |
|---|---|---|
| Relance outbox → 500 sur PostgreSQL (« FOR UPDATE cannot be applied to the nullable side of an outer join ») | `select_for_update(of=("self",))` | `FailureAndRetryTests` (exécuté sur PostgreSQL) |
| Écran bloqué sur « Chargement… » quand un jeton existe sans utilisateur (connexion interrompue avant `/auth/me`) | `useRestoreUser` recharge l'utilisateur, ou revient à la connexion | `restoreUser.test.jsx` |
| Admissions FHA : « Sans fournisseur » affiché pour un message capturé par Mailpit | badge « Capturé (Mailpit) » | sérialiseur + interface |
| Rapports mensuels : Mailpit compté comme fournisseur externe ; le test figeait ce défaut | prémisse du test corrigée (hôte réel) + test inverse ajouté | `test_monthly_reports.py` |
| Test `roleRedirect` : magasin simulé incomplet → 2 rejets non gérés (vitest code 1) | simulation complétée (`/auth/me` en attente), assertions inchangées | `roleRedirect.test.jsx` |

Sondes d'audit relancées : 314 appels API du frontend résolus, 0 route
orpheline. Aucune action d'écriture inattendue ouverte aux parents ou aux
élèves.

## 6. Fichiers

- **Nouveaux** :
  - `notifications/attachments.py`, `backends.py`, `outbox_views.py`
  - migration `0006_email_outbox_content_attachments.py`
  - `pages/admin/Outbox.jsx`
  - tests `test_email_outbox.py`, `test_email_single_path.py`,
    `Outbox.test.jsx`, `restoreUser.test.jsx`
- **Modifiés** :
  - `mailer.py`, `email_models.py`, `campaigns.py`, `campaign_models.py`,
    `campaign_views.py`, `tasks.py`, `urls.py`, `email_check.py`
  - `payments/reminders.py`, `fha_notifications.py`, `fha_serializers.py`,
    `monthly_reports/emails.py`
  - `settings/base.py`, `docker-compose.prod.yml`, `nginx.prod.conf`,
    `.env.*.example`
  - `MassEmail.jsx`, `FhaAdmissions.jsx`, `router/index.jsx`, menus,
    `api/index.js`, `translations.js`

**Production** : la migration `0006` ajoute des tables et des colonnes
nullables, sans aucune suppression. Ajouter le volume `private_media_prod`.
Rien n'a été déployé ni migré en production.
