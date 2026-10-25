# FEBA — Guide des e-mails : configuration, test, diagnostic, boîte d'envoi

Tous les envois de FEBA (e-mails groupés, accusés et notifications FEBA FHA,
relances de paiement, rapports mensuels, tests SMTP) passent par une couche
unique (`backend/apps/notifications/mailer.py`). Chaque message est
**enregistré, archivé (texte, HTML, pièces jointes), tenté, et son résultat
exact conservé**. Un backend de traçage (`TrackingEmailBackend`) journalise en
plus tout envoi qui contournerait cette couche.

---

## 1. Mailpit ou fournisseur réel : la différence qui compte

| | Mailpit (développement) | Fournisseur SMTP réel (production) |
|---|---|---|
| Rôle | **Capture** les messages pour les inspecter | **Distribue** les messages sur Internet |
| Arrivée dans Gmail/Yahoo… | **Jamais** | Oui, si le fournisseur et le DNS sont corrects |
| Où lire les messages | `http://localhost:8025` | Boîte du destinataire |
| Statut affiché par FEBA | « Capturé par le serveur de test (Mailpit) — non distribué » | « Accepté par le serveur de messagerie (réception non garantie) » |

**Cause du « je ne reçois rien » constaté en octobre 2026** : l'installation
Docker de développement envoie à `mailpit:1025`. Les messages étaient bien
acceptés… par Mailpit, qui ne les transmet jamais. FEBA les présentait comme
« envoyés via un fournisseur réel » : c'est corrigé, le transport est désormais
qualifié et affiché.

Statuts d'un envoi :

| Statut | Signification |
|---|---|
| Enregistré — en file d'attente | message archivé, pas encore traité (envoi groupé) |
| Envoi en cours | tentative en cours |
| Accepté par le serveur de messagerie | le serveur SMTP a dit oui — **ce n'est pas une preuve de réception** |
| Échec temporaire — nouvel essai programmé | relance automatique à +5 min, +30 min, +3 h |
| Échec définitif | 4 tentatives épuisées ou envoi impossible ; relance manuelle possible |

## 2. Développement local avec Docker et Mailpit

`.env.dev` (créé à l'installation depuis `.env.dev.example`) :

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mailpit
EMAIL_PORT=1025
EMAIL_USE_TLS=False
EMAIL_DELIVERY_MODE=auto
MAILPIT_UI_URL=http://localhost:8025
```

`mailpit` est le **nom du service Docker** : il fonctionne depuis les conteneurs
`backend-dev`, `celery-dev` et `celery-beat-dev`. Ne pas écrire `localhost`
(dans un conteneur, `localhost` désigne le conteneur lui-même).

Parcours de vérification :

1. `docker compose up -d` puis `docker compose ps` : `feba_mailpit_dev` *healthy*.
2. Configuration effective dans chaque conteneur (secrets masqués) :
   ```bash
   docker compose exec -T backend-dev python manage.py email_check </dev/null
   ```
   ```bash
   docker compose exec -T celery-dev python manage.py email_check </dev/null
   ```
3. FEBA → **E-mails groupés** : choisir des destinataires, joindre un PDF,
   prévisualiser, envoyer. Le bandeau « Mode test… Ouvrir Mailpit » s'affiche.
4. Ouvrir `http://localhost:8025` : un message par destinataire, avec ses
   pièces jointes.
5. FEBA → **Boîte d'envoi** : ouvrir le message, lire le texte et le HTML,
   ouvrir/télécharger les pièces jointes.

## 3. Fournisseur SMTP réel

Paramètres à placer dans `.env.prod` (ou, pour un test local vers de vraies
boîtes, dans `.env.dev` — à remettre sur Mailpit ensuite) :

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<serveur SMTP du fournisseur>
EMAIL_PORT=587              # 587 avec STARTTLS, ou 465 avec SSL
EMAIL_USE_TLS=True          # pour 587
EMAIL_USE_SSL=False         # True (et TLS False) pour 465
EMAIL_HOST_USER=<compte SMTP>
EMAIL_HOST_PASSWORD=<mot de passe ou clé d'application>
DEFAULT_FROM_EMAIL=<adresse d'un domaine autorisé chez le fournisseur>
FEBA_FROM_EMAIL=            # facultatif : expéditeur propre à FEBA
FHA_FROM_EMAIL=             # facultatif : expéditeur propre à FEBA FHA
EMAIL_REPLY_TO=
EMAIL_TIMEOUT=10
```

Les valeurs exactes (hôte, port, chiffrement) sont celles **indiquées par le
fournisseur** ; aucune n'est écrite dans le code. Les secrets ne sont jamais
affichés (ni par `email_check`, ni par l'API, ni dans le journal).

### Adresse d'expédition : `noreply@globalfeba.com`

L'ancienne adresse `noreply@feba.bj` est **retirée**. L'adresse officielle est
`noreply@globalfeba.com` (défaut du code, des trois `.env.*.example`, et
`SERVER_EMAIL` pour les alertes d'erreur de Django). Une seule fonction fixe
l'expéditeur de TOUS les envois (`apps.notifications.mailer.sender_for`) ;
si un environnement contient encore `noreply@feba.bj`, elle est remplacée à
l'envoi (journal d'avertissement) et `manage.py check` le signale
(`notifications.W001`). `notifications.W002` signale un expéditeur qui
n'appartient pas au domaine du compte SMTP — Hostinger le refuse.

Relevés DNS publics de `globalfeba.com` (25/10/2026, DNS-over-HTTPS) :

| Enregistrement | Valeur | Constat |
|---|---|---|
| MX | `mx1.hostinger.com`, `mx2.hostinger.com` | messagerie chez Hostinger |
| SPF | `v=spf1 include:_spf.mail.hostinger.com ~all` | autorise le SMTP Hostinger |
| DKIM `hostingermail-a._domainkey` | clé RSA publiée | signature possible |
| DKIM `hostingermail-b._domainkey` | `p=` vide | clé révoquée/inutilisée |
| DMARC | `v=DMARC1; p=none` | observation seule |

Reste à faire chez Hostinger (non vérifiable d'ici) : créer la boîte (ou
l'alias autorisé) `noreply@globalfeba.com`, renseigner son mot de passe dans
`EMAIL_HOST_PASSWORD`, vérifier que la signature DKIM est **activée** pour
le domaine, puis envoyer le test de la section 4 et lire les en-têtes reçus
(`spf=pass`, `dkim=pass`, `dmarc=pass`). Paramètres Hostinger :
`smtp.hostinger.com`, port 465 SSL (ou 587 STARTTLS). Passer DMARC à
`p=quarantine` une fois les envois validés.

DNS (chez Hostinger pour `globalfeba.com`) — selon le fournisseur :

- **SPF** : enregistrement TXT `v=spf1 include:<domaine fourni par le fournisseur> ~all`
- **DKIM** : clé(s) publique(s) fournie(s) par le fournisseur (TXT ou CNAME)
- **DMARC** : TXT `_dmarc` (commencer par `p=none` pour observer)

Sans eux, les messages risquent d'être refusés ou classés en indésirables —
FEBA ne peut pas le détecter : un serveur qui accepte puis rejette plus tard
n'en informe pas l'expéditeur par SMTP.

Après redémarrage des conteneurs (`backend`, `celery`, `celery-beat`), lancer
le test de la section 4 vers **une seule adresse de test autorisée**.

Un relais SMTP interne au nom inhabituel peut être qualifié explicitement :
`EMAIL_DELIVERY_MODE=real` (ou `capture`), ou `EMAIL_CAPTURE_HOSTS=nom1,nom2`.

## 4. Tester l'envoi

Depuis l'écran **Boîte d'envoi** → « Diagnostic et test d'envoi » :
configuration effective, joignabilité réseau du serveur, envoi d'un message
de test à une adresse saisie (administrateurs uniquement, 5 tests par heure
et par personne, tracé dans la boîte d'envoi).

En ligne de commande (production) :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend-prod python manage.py email_check --to adresse.de.test@exemple.com </dev/null
```

Codes de sortie : `0` accepté par un serveur réel, `1` échec (erreur affichée),
`2` transport de test/local (console, mémoire, Mailpit) — rien n'est parti.

## 5. Diagnostiquer une erreur

L'erreur exacte est conservée sur l'envoi (Boîte d'envoi → détail →
« Historique des tentatives »).

| Erreur | Cause probable | Action |
|---|---|---|
| `ConnectionRefusedError` / `timed out` | hôte ou port faux, pare-feu | vérifier `EMAIL_HOST`/`EMAIL_PORT` ; « Réseau » du diagnostic |
| `SMTPAuthenticationError (535)` | identifiant ou mot de passe refusé | régénérer la clé d'application du fournisseur |
| `SMTPServerDisconnected` | TLS/SSL inversés (587 ↔ 465) | ajuster `EMAIL_USE_TLS` / `EMAIL_USE_SSL` |
| `SMTPSenderRefused` | expéditeur non autorisé | `DEFAULT_FROM_EMAIL` sur un domaine validé chez le fournisseur |
| `SMTPRecipientsRefused` | adresse du destinataire refusée | corriger l'adresse |
| `FileNotFoundError` sur une pièce jointe | fichier privé absent (volume non monté) | vérifier le volume `private_media` (§ 7) |
| « Capturé… non distribué » | transport Mailpit | normal en développement ; § 3 pour l'envoi réel |

Les échecs temporaires sont relancés automatiquement par
`notifications.retry_due_deliveries` (Celery Beat, toutes les 10 min). Si le
statut ne bouge pas : vérifier `celery-dev`/`celery-beat-dev` (`docker compose ps`).

## 6. Boîte d'envoi

Menu **Boîte d'envoi** (administrateurs : leur académie ; super-administrateur :
toutes, ou une académie). Filtres : recherche (objet, destinataire, contenu),
destinataire, statut, origine, période. Liste paginée côté serveur.

Le détail montre objet, date et heure, expéditeur, destinataire, académie,
origine, statut et transport, tentatives et erreurs, texte, HTML (affiché dans
un cadre isolé **sans exécution de script**), pièces jointes (aperçu des PDF
et images, téléchargement des autres), et permet de **relancer** un échec
(verrou anti double clic ; un envoi réussi n'est jamais relancé).

- Les envois antérieurs à cette version affichent « Contenu non archivé pour
  cet envoi historique » : le contenu n'avait pas été conservé, il n'est pas
  inventé.
- Les messages porteurs de liens de sécurité sont archivés **expurgés**
  (« lien de sécurité masqué dans l'archive ») et ne sont **jamais rejoués**
  depuis cette archive (le lien serait inutilisable) : un échec est définitif,
  la relance est refusée, la personne doit redemander un nouveau lien.
- Un envoi groupé partage UN contenu et UN exemplaire des fichiers ; chaque
  destinataire a son propre envoi et son propre statut ; aucune adresse n'est
  visible des autres.

## 7. Pièces jointes

- Formats par défaut : PDF, PNG, JPEG, GIF, WebP, Word (doc, docx), Excel
  (xls, xlsx), PowerPoint (ppt, pptx), OpenDocument (odt, ods), TXT, CSV.
  Jamais : exécutables, scripts, archives, HTML, SVG.
- Le serveur vérifie l'extension **et le contenu réel** (signature binaire) :
  un exécutable renommé en `.pdf` est refusé. Noms de fichiers neutralisés
  (aucun chemin, aucun caractère de contrôle).
- Limites : `EMAIL_ATTACHMENT_MAX_FILE_MB` (10), `EMAIL_ATTACHMENT_MAX_TOTAL_MB`
  (20), `EMAIL_ATTACHMENT_MAX_FILES` (10), liste
  `EMAIL_ATTACHMENT_ALLOWED_EXTENSIONS`. nginx accepte 25 Mo par requête.
- Stockage **privé** : `PRIVATE_MEDIA_ROOT/email_attachments/` (hors média
  public) ; téléchargement uniquement par l'API, après contrôle des droits.
  En production, le volume `private_media_prod` est partagé entre
  `backend-prod` et `celery-prod` (le worker lit les fichiers qu'il envoie).
- **Aucune analyse antivirus** n'est disponible dans cette installation :
  aucune n'est annoncée.

## 8. Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `EMAIL_BACKEND` | console | transport (smtp, console…) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | — | serveur SMTP |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | — | authentification (jamais affichée) |
| `DEFAULT_FROM_EMAIL`, `FEBA_FROM_EMAIL`, `FHA_FROM_EMAIL`, `EMAIL_REPLY_TO` | — | expéditeurs |
| `EMAIL_TIMEOUT` | 10 | délai SMTP (s) |
| `EMAIL_DELIVERY_MODE` | auto | auto / capture / real |
| `EMAIL_CAPTURE_HOSTS` | — | hôtes de capture supplémentaires |
| `MAILPIT_UI_URL` | http://localhost:8025 | lien affiché en mode capture |
| `EMAIL_ATTACHMENT_*` | voir § 7 | pièces jointes |
| `EMAIL_TEST_MAX_PER_HOUR` | 5 | tests SMTP par utilisateur et par heure |
| `MASS_EMAIL_MAX_RECIPIENTS`, `MASS_EMAIL_MAX_CAMPAIGNS_PER_HOUR`, `MASS_EMAIL_BATCH_SIZE` | 2000 / 10 / 50 | garde-fous des envois groupés |
| `PRIVATE_MEDIA_ROOT` | `backend/private_media` | fichiers privés (fiches, pièces jointes) |

## 9. Tests automatisés sans envoi réel

```bash
docker run -d --rm --name feba_mailpit_test -p 51025:1025 -p 58025:8025 axllent/mailpit
```

```bash
cd backend && MAILPIT_SMTP_PORT=51025 MAILPIT_API_URL=http://127.0.0.1:58025 DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite python -m pytest tests/test_email_outbox.py tests/test_audit_p1_mass_email.py
```
