# FEBA — Rapport final : corrections prioritaires et audit complet (octobre 2026)

> **DOCUMENT HISTORIQUE** — il décrit une version antérieure de FEBA ; ses résultats n'ont pas été
> rejoués tels quels sur cette version. Références à jour : `DOCUMENTATION_INDEX.md`, `FINAL_REPORT.md`.

Statuts : **PASS VÉRIFIÉ** (exécuté et réussi) · **CORRIGÉ** · **FAIL** ·
**À TESTER EN ENVIRONNEMENT RÉEL** · **BLOCAGE EXTERNE** · **LIMITATION CONNUE**.
Détail chiffré des contrôles : `VALIDATION_REPORT.md`.

---

## A. État initial

| Élément | Valeur |
|---|---|
| Dépôt | `https://github.com/febaadmin/FEBA.git` |
| ZIP fourni | `feba_v13_production_finale.zip` — SHA-256 `386742cb…01ad` vérifié ; contenu **identique** à `origin/claude/feba-v13-production-final` (`d66d015`), seul `SHA256SUMS.txt` diffère |
| `main` | `d3bc137` — contient 3 commits absents de la V13 : hotfix stdin du `deploy.yml`, chemin de montage nginx Jitsi (`/config/nginx-custom`), nettoyage Makefile |
| Base de travail | branche **`fix/feba-audit-complet`** = V13 + fusion de `main` (`4b3777a`). Makefile V13 conservé (ses scripts existent) ; chemin Jitsi de `main` retenu et propagé au script `deploy_production.sh` et à 2 tests qui vérifiaient encore l'ancien chemin |
| Référence backend SQLite | 1330 réussis, 1 ignoré, 0 échec |
| Référence backend PostgreSQL 16 | 1331 réussis, 0 échec |
| Référence frontend | 246 tests / 25 fichiers ; ESLint 0 erreur, 81 avertissements ; build OK |

Aucune opération de production, aucun déploiement, aucun envoi réel.

---

## B. Les cinq corrections prioritaires

### B1. Âge des élèves — **PASS VÉRIFIÉ**
- **Cause** : aucun écran n'affichait l'âge ; deux calculs divergents existaient (fiches FHA, « aujourd'hui » pris à Porto-Novo).
- **Correction** : `apps/core/age.py` (années révolues, 29 février → 1er mars, date du jour **dans le fuseau de l'académie**, statut `ok/missing/invalid`, jamais d'âge négatif, rien de stocké). Exposé par les serializers élèves, inscriptions, paiements, absences, notes, bulletins, rapports mensuels, enfants du parent, moyennes de classe. Date de naissance future/invraisemblable refusée à la saisie. Frontend : colonne « Âge » (élèves, paiements, absences, notes, bulletins, rapports mensuels, classes enseignant, inscriptions, parents, enfants), sélecteurs d'élèves, exports ; tri numérique du `DataTable`. Pas de N+1 (`select_related` ajoutés, test du nombre de requêtes).
- **Trouvé en route** : `/api/students/enrollments/` répondait 404 (ordre du routeur) et son POST levait une 500 ; N+1 de `ParentSerializer` ; lien de parenté toujours « — ».
- **Tests** : `test_audit_p1_student_age.py` (27), `utils/age.test.jsx` (8).

### B2. Date et heure des paiements — **PASS VÉRIFIÉ**
- **Cause** : `Payment.payment_date` est un `DateField` ; l'heure n'était conservée nulle part.
- **Correction** : `Payment.paid_at` + `paid_at_source` (provenance), saisie de l'heure (heure locale de l'académie), affichage `JJ/MM/AAAA HH:mm` dans le fuseau de l'académie, tri `NULLS LAST`, filtres `date_from/date_to`. Migration `0011` : reprise de `created_at` **uniquement** si la saisie a eu lieu le jour même ; sinon heure inconnue affichée « heure n.e. » — **aucune heure inventée**, aucune date modifiée, réversible. Paiement carte : date locale de l'académie (était UTC) + heure de confirmation. Reçu PDF : heures locales (étaient UTC). Colonne date ajoutée aux transactions carte.
- **Trouvé en route** : **faille** — élève d'une autre académie accepté à la création d'un paiement ; modes « mobile_money/Virement/Chèque » et type « autre » refusés par l'API (400) ; « Mois concerné » jamais enregistré ; historique lisant des champs inexistants ; paiement annulé affiché « En attente » au parent ; date par défaut du formulaire en UTC.
- **Tests** : `test_audit_p1_payment_datetime.py` (19), `utils/datetime.test.js` (10) ; **vérifié en navigateur** (paiement saisi à 14:37 affiché « 09/10/2026 14:37 »).

### B3. E-mails par académie et par profil — **PASS VÉRIFIÉ** (SMTP de production : À TESTER EN ENVIRONNEMENT RÉEL)
- **Constat** : fonctionnalité absente.
- **Réalisation** : modèles `EmailCampaign` / `EmailCampaignRecipient`, service `notifications/campaigns.py`, API `/api/mass-email/…`, écran « E-mails groupés » (admin et super-admin). Destinataires recalculés par le serveur à partir de règles (profils, tous les profils, inclusions, exclusions) ; identifiant hors académie → refus complet ; un message individuel par destinataire ; inactifs / sans adresse / invalides / doublons ignorés et rapportés ; aperçu obligatoire, nombre confirmé, jeton anti double-clic, plafond et limite horaire configurables ; Celery par lots (`SKIP LOCKED`), reprise après arrêt du worker sans doublon, relance des seuls échecs.
- **Trouvé en route** : le statut « nouvel essai programmé » n'était relu par **aucune** tâche → ajout de `notifications.retry_due_deliveries` (Beat).
- **Tests** : `test_audit_p1_mass_email.py` (29, dont 1 contre **Mailpit** en vrai SMTP), `MassEmail.test.jsx` (3), `massEmailSelection.test.js` (6) ; vérifié en navigateur.

### B4. Relances automatiques des paiements — **PASS VÉRIFIÉ** (activation : BLOCAGE EXTERNE, voir D)
- **Constat** : aucun échéancier, aucun abonnement, aucune exonération dans le code ; la grille ne disait que « combien ».
- **Réalisation** : `FeeInstallment`, `StudentFeeArrangement`, `PaymentReminderPolicy`, `ReminderRun`, `PaymentReminder` (clé d'idempotence unique, instantané des montants). Moteur `payments/reminders.py` : tarif le plus spécifique, paiements confirmés nets des remboursements, imputation au mois concerné puis à l'échéance la plus ancienne, réductions sur les dernières tranches ; statuts à venir / réglée / échue / partielle / exonérée ; abstention et anomalie en cas de données incohérentes ; responsables financiers de la même académie ; un message par famille ; notification interne + e-mail, statuts constatés. Celery Beat quotidien, **double interrupteur** (serveur + académie, faux par défaut), verrou, reprise, journal des exécutions. Écran « Relances de paiement » (état dégradé expliqué, règles, suspension, simulation, envoi manuel confirmé, échéanciers, dispositions, historique). Commande `load_fee_plan` + plan FEBA 2026-2027 tiré de l'affiche (simulation par défaut). Type de paiement « Garderie ».
- **Tests** : `test_audit_p1_payment_reminders.py` (46, dont **2 exécutions parallèles réelles sur PostgreSQL**) ; vérifié en navigateur (simulation : 150 000 prévus, 70 000 payés, 80 000 dus).

### B5. Mails de confirmation par ligne + envoi groupé — **PASS VÉRIFIÉ**
- **Cause racine** : indicateur d'occupation **unique** (`resendMut.isPending`) passé à toutes les lignes ; un clic désactivait toutes les lignes et l'appel suivant écrasait le précédent. Côté serveur, aucun garde contre deux envois simultanés.
- **Correction** : état par identifiant de dossier, verrou synchrone, résultat sur sa ligne ; cases à cocher, sélection des lignes affichées (lignes masquées par un filtre jamais incluses), confirmation, reprise des seuls échecs. Backend `send_confirmation()` (verrou de ligne, fenêtre anti-doublon limitée aux renvois manuels, destinataire manquant explicite, `skip_sent`) et action `bulk-resend-confirmation` (ids revalidés, résultat par ligne). N+1 de la liste supprimé.
- **Tests** : `test_audit_p1_confirmation_emails.py` (17, dont concurrence réelle PostgreSQL), `FhaAdmissions.confirm.test.jsx` (5) ; vérifié en navigateur (2ᵉ clic → « envoi déjà en cours »).

---

## C. Audit global — défauts confirmés et corrigés

Chacun a été **reproduit par un test qui échoue sans le correctif**.

| # | Défaut | Gravité | Correction |
|---|---|---|---|
| 1 | Absences, notes, bulletins, devoirs, créneaux, annonces, élèves, classes, matières acceptaient en écriture l'élève/la matière/la classe **d'une autre académie** (7 tests échouaient sans correctif) | Critique (isolation) | `TenantRelationsMixin` générique |
| 2 | `bulk-delete` sans contrôle de rôle : un **parent ou un élève** pouvait supprimer en masse paiements, notes, absences… | Critique | admin par défaut, surchargeable |
| 3 | Absences sans restriction de rôle en écriture : un parent pouvait changer « absent » en « présent » | Critique | admin/enseignant |
| 4 | `StudentViewSet.get_permissions()` écrasait les `permission_classes` des actions : enroll, promote, fin d'année… ouverts à tout authentifié | Critique | toute écriture = admin |
| 5 | Bulletins create/update et suppression de pièces jointes de devoirs ouverts à tout authentifié | Élevée | admin / admin-enseignant |
| 6 | Restauration d'une note sans filtre d'académie ni contrôle enseignant (et 500 sur id inconnu) | Élevée | portée + droits |
| 7 | Tableau de bord : **paiements annulés comptés comme recettes** | Élevée (comptable) | `is_confirmed=True` |
| 8 | « Restaurer » un paiement supprimé : toujours **404** ; un paiement annulé puis supprimé revenait « confirmé » | Élevée | corrigé + état d'avant |
| 9 | Suppression groupée de paiements/notes sans historique | Moyenne | tracée comme l'unitaire |
| 10 | Annonces du super-administrateur invisibles partout | Moyenne | portée par année scolaire |
| 11 | 6 fonctions API frontend vers des routes inexistantes (code mort) | Faible | retirées ; 307 appels vérifiés au résolveur Django |
| 12 | Dates par défaut en UTC (absences), validation « futur » au fuseau du serveur | Faible | fuseau de l'académie |
| 13 | Production : pas de healthcheck Celery worker/Beat | Moyenne (exploitation) | healthchecks ajoutés |

Régression introduite puis corrigée pendant le travail (détectée par la suite complète) : le routeur des échéanciers capturait `/api/payments/` (405) → `SimpleRouter`.

### Risques résiduels
Voir `KNOWN_LIMITATIONS.md` § 0 : jours d'échéance à confirmer, noms de niveaux en production, abonnements à saisir, paiements anciens sans heure, SMTP réel non testé, suppression de conversation pour les deux interlocuteurs, route `payments/pending` mal nommée (inutilisée).

---

## D. Validation technique

Voir `VALIDATION_REPORT.md` (chiffres exacts de la dernière exécution).

---

## E. Livraison et actions manuelles

Archive : `delivery/FEBA_VERSION_CORRIGEE_AUDIT_COMPLET.zip`, construite depuis le
commit par `scripts/make_final_delivery.sh`, empreintes dans `SHA256SUMS.txt`
(à la racine de l'archive) et `…zip.sha256`.

Actions manuelles (aucune n'a été exécutée) :
1. Sauvegarde (procédure existante, `ROLLBACK_GUIDE.md`), puis déploiement de la branche `fix/feba-audit-complet` après revue.
2. Migrations : `payments.0010–0013`, `notifications.0004–0005` — additives, réversibles ; `0011` et `0013` ne modifient ni montant ni date.
3. `.env.prod` : nouvelles variables `MASS_EMAIL_*`, `PAYMENT_REMINDERS_*` (voir `.env.prod.example`), SMTP réel + SPF/DKIM/DMARC chez Hostinger.
4. **Décision métier** : confirmer les jours d'échéance 2026-2027, puis `load_fee_plan` (simulation, puis `--apply`).
5. Saisir abonnements et exonérations ; simulation ; puis `PAYMENT_REMINDERS_ENABLED=True` et activation par académie (`PAYMENT_REMINDERS_GUIDE.md` § 6).
