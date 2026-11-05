# Boîte mail contact@globalfeba.com — phase 8

## 1. Fournisseur identifié (vérifié le 05/11/2026)
| Élément | Valeur constatée |
|---|---|
| MX | `mx1.hostinger.com` (5), `mx2.hostinger.com` (10) → **Hostinger Email** héberge la boîte |
| SPF | `v=spf1 include:_spf.mail.hostinger.com ~all` |
| DKIM | `hostingermail-a._domainkey` → clé publiée (CNAME Hostinger) ; `hostingermail-b` clé vide (révoquée) |
| DMARC | `v=DMARC1; p=none` (surveillance seule ; recommandation : passer à `quarantine` après contrôle des rapports) |
| Envoi | SMTP `smtp.hostinger.com:587` STARTTLS (configuration FEBA existante) |
| Réception | IMAP `imap.hostinger.com:993` SSL — joignable depuis le serveur FEBA |
| Compte | `contact@globalfeba.com` : le compte SMTP déjà configuré sur le serveur (variables d'environnement) |
| Dossiers (SPECIAL-USE) | `INBOX`, `INBOX.Sent` (\Sent), `INBOX.Trash` (\Trash), `INBOX.Junk` (\Junk), `INBOX.Drafts` (\Drafts) ; pas de dossier d'archives (créé à la première archive) |
| Capacités annoncées | IMAP4rev1, IDLE, LITERAL+, SASL-IR (pas de MOVE ni UIDPLUS : déplacement par COPY + \Deleted + EXPUNGE) |

**Constat déterminant** : la boîte comptait 44 messages en réception et **1 seul** dans « Envoyés », alors que FEBA a envoyé 52 e-mails depuis cette adresse : Hostinger **ne conserve pas** les envois SMTP. Les envois FEBA sont donc importés depuis l'historique FEBA, et les envois faits depuis la boîte FEBA sont aussi déposés dans `INBOX.Sent` (APPEND), comme le ferait un logiciel de messagerie.

## 2. Architecture
- Application `apps/boite_mail` : copie locale synchronisée (`MessageMail`, `PieceJointeMail`, `EtatSynchroDossier`), droits (`AccesBoiteMail`), journal (`JournalBoiteMail`). Migration `boite_mail.0001_initial` : **tables nouvelles uniquement**.
- Synchronisation incrémentale par dossier : UIDVALIDITY + dernier UID ; corps lus en `BODY.PEEK[]` (aucun message marqué lu par la synchronisation) ; drapeaux (\Seen, \Flagged) et disparitions repris à chaque passage ; changement d'UIDVALIDITY → resynchronisation du dossier ; première synchronisation bornée aux 500 messages les plus récents par dossier ; messages > 25 Mo : en-têtes seulement ; pièces > 15 Mo : signalées, non copiées.
- Déclenchement : tâche Celery `boite_mail.synchroniser` toutes les 3 minutes + bouton « Actualiser » ; verrou de cache (aucun chevauchement) ; un dossier en erreur n'arrête pas les autres ; aucune autre fonction de FEBA n'est bloquée.
- Rapprochement sans doublon : identité (dossier IMAP, UIDVALIDITY, UID) ; entre sources (historique FEBA ↔ fournisseur) par **Message-ID** ; le mailer conserve désormais le Message-ID d'origine quand un message est reconstruit (copie, nouvel essai).
- HTML : nettoyé à la synchronisation (nh3, liste blanche : pas de script, d'attribut d'événement, de style actif, de formulaire, de cadre) ; images distantes retirées de la version affichée par défaut, version avec images servie à la demande.
- Actions **d'abord chez le fournisseur** (lu / non lu, important, archiver, corbeille, restaurer, suppression définitive depuis la corbeille), puis dans la copie locale ; un refus du fournisseur renvoie une erreur (502), jamais une fausse réussite.
- Écrire, répondre, répondre à tous, transférer : depuis l'adresse officielle, via le journal d'envoi FEBA, avec `In-Reply-To` / `References` ; Cci jamais dans les en-têtes (destinataires supplémentaires de l'enveloppe en copie cachée) ; transfert avec les pièces jointes d'origine.

## 3. Sécurité et accès
- Identifiants : variables d'environnement du serveur (`MAILBOX_IMAP_*`, par défaut celles du compte SMTP) ; jamais en base, jamais dans les journaux (seul le type d'erreur est journalisé), jamais dans les réponses API (testé).
- Droits **explicites** : le super administrateur a tous les droits et gère les accès ; seuls des administrateurs d'académie peuvent recevoir un accès (lire ; écrire / répondre / transférer ; supprimer) ; enseignants, parents et élèves n'y accèdent jamais (403, testé).
- Journal d'audit : lectures, téléchargements de pièces, envois, déplacements, suppressions définitives, modifications de droits (qui, quoi, quand — jamais le contenu).
- Pièces jointes : stockage privé, téléchargement authentifié et autorisé (`nosniff`, `no-store`).

## 4. Interface
Page « Boîte mail contact » (ancienne « Boîte d'envoi », mêmes adresses `/superadmin/outbox`, `/admin/outbox`) : dossiers avec compteurs de non-lus, liste (expéditeur, objet, extrait, date, non lu, important, pièce jointe), recherche (expéditeur, destinataire, objet, contenu), filtres non lus / pièces jointes, pagination, sélection multiple et actions groupées, lecture (en-têtes, HTML nettoyé, images à la demande, pièces jointes), composition. L'ancien journal technique des envois (diagnostic SMTP, relances) reste un onglet.

## 5. Tests et vérifications
| Vérification | Résultat | Niveau |
|---|---|---|
| Connexion IMAP au vrai compte, lecture seule | OK : INBOX 44, Sent 1 | **Production (lecture seule)** |
| Analyse des 45 messages réels (INBOX + Sent) par le code de FEBA | 45 OK, 0 erreur (6 avec pièces, 8 HTML, 1 avec images distantes) ; drapeaux inchangés (40 non lus avant et après) | **Production (lecture seule, aucune écriture en base)** |
| Synchronisation initiale / incrémentale / drapeaux / disparitions / UIDVALIDITY | OK | Local + CI (faux serveur IMAP) |
| HTML dangereux neutralisé, images distantes masquées | OK | idem |
| Actions chez le fournisseur d'abord, refus → aucune fausse réussite | OK | idem |
| Archiver (dossier créé), corbeille, restaurer, suppression définitive, sans doublon | OK | idem |
| Répondre : fil, Cci invisible, copie dans Envoyés sans doublon ; transférer avec pièces | OK | idem |
| Envois FEBA dans « Envoyés », autre expéditeur exclu | OK | idem |
| Droits (enseignant, administrateur sans droit, lecture seule) et journal | OK | idem |
| Fournisseur indisponible : message clair, aucun secret | OK | idem |

## 6. Ce qui reste à vérifier après déploiement
- Première synchronisation réelle (écriture de la copie locale en base de production) et consultation dans le navigateur avec un compte super administrateur.
- Un envoi réel de test vers une adresse contrôlée (réponse à un message de test), puis vérification dans le webmail Hostinger (copie dans « Envoyés »).
