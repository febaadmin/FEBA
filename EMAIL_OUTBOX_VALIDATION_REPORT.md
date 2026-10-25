# FEBA — Rapport de validation : e-mails, pièces jointes, boîte d'envoi

> **DOCUMENT HISTORIQUE** — il décrit une version antérieure de FEBA ; ses résultats n'ont pas été
> rejoués tels quels sur cette version. Références à jour : `DOCUMENTATION_INDEX.md`, `FINAL_REPORT.md`.

Chaque statut renvoie à une commande exécutée. Statuts possibles :
PASS VÉRIFIÉ · CORRIGÉ · FAIL · À TESTER EN ENVIRONNEMENT RÉEL ·
BLOCAGE EXTERNE · LIMITATION CONNUE.

Corrections : `EMAIL_OUTBOX_CORRECTIONS_REPORT.md`. Limites :
`KNOWN_LIMITATIONS.md` § 0.5 et 0.5 bis.

---

## 1. Diagnostic des conteneurs de l'utilisateur (lecture seule)

| Contrôle | Résultat | Statut |
|---|---|---|
| Configuration effective `backend-dev`, `celery-dev`, `celery-beat-dev` | `smtp` → `mailpit:1025`, sans mot de passe, identique dans les 3 | PASS VÉRIFIÉ |
| Messages envoyés depuis FEBA | présents dans Mailpit (4, dont le test vers `ymail.com`) | PASS VÉRIFIÉ |
| Cause « pas dans la boîte de réception » | Mailpit capture et ne distribue jamais ; FEBA l'affichait comme fournisseur réel | CORRIGÉ |

## 2. Scénarios de bout en bout — pile Docker isolée

Chaîne testée : HTTP réel → Django → Celery → SMTP → Mailpit, sur des
conteneurs, ports et volumes distincts de ceux de l'utilisateur.
Script : 31 contrôles.

| Scénario | Contrôles | Statut |
|---|---|---|
| A — configuration et envoi de test | transport `capture` (pas console), Mailpit joignable, aucun secret exposé, message de test dans Mailpit, libellé « Capturé… » | PASS VÉRIFIÉ |
| B1 — campagne avec un PDF | traitée par le worker Celery ; nom et type MIME corrects ; PDF reçu identique octet pour octet | PASS VÉRIFIÉ |
| B2 — 4 pièces jointes (PDF, PNG, DOCX, CSV) | noms et types corrects ; une seule copie archivée | PASS VÉRIFIÉ |
| B — fichier déguisé (`faux.pdf`) | refusé par le serveur avec un message explicite | PASS VÉRIFIÉ |
| B — redémarrage du worker | pièce jointe toujours lisible | PASS VÉRIFIÉ |
| C — boîte d'envoi | tous les envois listés ; filtres objet et destinataire ; détail (texte, HTML, 4 pièces) ; téléchargement identique | PASS VÉRIFIÉ |
| D — envoi individuel | 5 messages pour 5 destinataires ; aucune autre adresse exposée | PASS VÉRIFIÉ |
| E — isolation | un admin FHA reçoit 404 sur un envoi FEBA, refus sur une pièce FEBA, aucune ligne FEBA, `academy_id` FEBA refusé | PASS VÉRIFIÉ |
| F — Mailpit arrêté | statut `retry`, jamais « envoyé » ; erreur exacte (`gaierror`) ; campagne intacte ; relance manuelle acceptée ; second essai → 409 ; reprise automatique : 5 messages / 5 destinataires ; campagne terminée | PASS VÉRIFIÉ |
| Navigateur | boîte d'envoi : libellés capture, détail, HTML en `iframe sandbox=""`, aperçu PDF | PASS VÉRIFIÉ |
| G — fournisseur SMTP réel | aucun identifiant disponible ; non exécuté | BLOCAGE EXTERNE / À TESTER EN ENVIRONNEMENT RÉEL |

Commande pour le scénario G, vers UNE adresse de test autorisée,
après avoir rempli `.env.prod` :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend-prod python manage.py email_check --to adresse.de.test@exemple.com </dev/null
```

Code de sortie 0 = **accepté** par le fournisseur. La réception se vérifie
dans la boîte de l'adresse de test (et ses indésirables).

## 3. Tests automatisés (dépôt, commit de la branche)

| Suite | Résultat | Statut |
|---|---|---|
| Backend SQLite (`test_sqlite`) | 1523 réussis, 3 ignorés (concurrence : PostgreSQL requis), 0 échec | PASS VÉRIFIÉ |
| Backend PostgreSQL 16 + Mailpit SMTP réel | 1526 réussis, 0 ignoré, 0 échec | PASS VÉRIFIÉ |
| Frontend Vitest | 287 / 287, 0 erreur non gérée | PASS VÉRIFIÉ |
| ESLint | 0 erreur (80 avertissements préexistants) | PASS VÉRIFIÉ |
| Build Vite | OK | PASS VÉRIFIÉ |
| Sonde routes (appels API du frontend) | 314 appels, 0 route orpheline | PASS VÉRIFIÉ |
| Sonde permissions | aucune écriture inattendue ouverte aux parents ou aux élèves | PASS VÉRIFIÉ |

Ces deux suites backend ont été lancées avant le dernier correctif (relance
des messages masqués). Les 36 tests de `test_email_outbox.py`, dont les
3 de `RedactedReplayTests`, ont été rejoués après ce correctif. Le passage
complet sur le code final est consigné au § 4.

**Les tests de régression échouent bien sur l'ancien code :**
- `test_email_single_path` échoue sur `04595a7` : il détecte les envois
  hors couche centrale (`fha_notifications` et `monthly_reports`).
- `RedactedReplayTests` : 3 échecs sur `748b983` (statut `retry` au lieu
  de `failed`, relance acceptée).

## 4. Vérification depuis une extraction neuve de l'archive

Voir `DELIVERY_VERIFICATION.txt`, livré à côté de l'archive : empreinte,
`unzip -t`, `SHA256SUMS.txt`, dépendances réinstallées, migrations,
suites complètes, build, Compose, pile Docker neuve et scénarios A à F.
