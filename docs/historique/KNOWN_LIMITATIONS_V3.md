# KNOWN_LIMITATIONS — FEBA V3 bilingue auditée (16/07/2026)

Limitations réelles restantes, avec leur raison exacte. Aucune n'est
bloquante pour l'exploitation.

1. **Revalidation PostgreSQL en toute fin de session** : Docker Desktop a
   été arrêté en dehors de la session de travail pendant la validation
   finale. Le résultat **220/220 sur PostgreSQL** (migrations incluses) a
   été obtenu juste avant, après la dernière modification backend ; les
   changements ultérieurs sont exclusivement frontend + docs, re-validés
   sur SQLite (219 + 1 skip) et par la suite Vitest (22/22). À la
   prochaine disponibilité de Docker : `make dev` puis
   `DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres pytest`.

2. **Test de concurrence sur SQLite** : `ParentStudentConcurrencyTest` est
   marqué `skipIf(sqlite)` — SQLite en mémoire verrouille la table entière
   sous threads (« database table is locked »), limitation du moteur, pas
   de l'application. Le test passe sur PostgreSQL.

3. **E-mails** : backend console en développement (aucun serveur SMTP dans
   l'environnement). La logique d'envoi est exercée, pas la délivrance
   réelle. Configurer `EMAIL_BACKEND` SMTP en production (voir
   `.env.example`).

4. **Jitsi auto-hébergé (jetons JWT)** : nécessite l'instance
   `docker-compose.jitsi.yml` et les secrets `JITSI_APP_*`. Non testable
   ici ; le mode démo public (meet.jit.si, appels ~5 min) est fonctionnel.

5. **Couverture i18n** : ~1 060 chaînes traduites et vérifiées sur les
   parcours principaux des cinq rôles. D'éventuels reliquats très marginaux
   s'affichent en français (repli sûr — jamais de clé technique visible) ;
   les corriger = une ligne dans `frontend/src/i18n/translations.js`.

6. **Doublons/conflits historiques en base** : les nouvelles validations
   (doublons de présence, chevauchements d'emploi du temps) s'appliquent
   aux écritures futures via l'API. Les données historiques éventuellement
   incohérentes ne sont pas purgées (aucune migration destructive,
   conformément à la mission).

7. **Migrations v29 en SQL brut PostgreSQL** : inchangées (les réécrire
   risquerait de casser les bases existantes). Conséquence : le mode démo
   local SQLite crée son schéma depuis les modèles
   (`migrate --run-syncdb`), documenté dans
   `backend/feba_project/settings/dev_sqlite.py`.

8. **Tests E2E navigateur** : la validation navigateur (connexion des
   rôles, page Parent, notifications, bascule FR/EN) a été exécutée
   manuellement outillée dans un vrai navigateur pendant cette session ;
   il n'y a pas encore de suite Playwright/Cypress automatisée dans le
   dépôt. Les parcours critiques sont couverts par les tests
   Vitest (rendu ParentHome, i18n, anti-shadowing) et pytest (API).
