# Audit des références « FEBA » / « FHA » — identités d'académie codées en dur

27 octobre 2026, branche `feat/langues-identite-academies`. L'inventaire est
**exhaustif** : il couvre `backend/apps`, `backend/feba_project`,
`frontend/src`, `e2e`, `scripts`, `nginx` et `plugnmeet`. Il a été produit par
un script qui compte les occurrences de `FEBA` et `FHA`, fichier par fichier
(annexe). Chaque occurrence qui peut atteindre l'écran ou un message d'API a
ensuite été relue à la main : le script repère les chaînes qui ne sont ni des
commentaires ni des docstrings.

## Catégories

| # | Catégorie | Règle | Traitement |
|---|---|---|---|
| 1 | **Identité dynamique** | Nom, sigle ou logo d'UNE académie affiché à la place de l'académie active ou de la ligne concernée. | **Remplacé** par les données servies par l'API : `name`, `short_name` et `code` du contexte d'entité, `academy_name` / `academy_short_name` des lignes. **Il n'en reste aucune.** |
| 2 | **Règle de type ou de fonctionnalité** | Un comportement propre à un canal ou à une fonctionnalité : site public en ligne, rapports mensuels, préinscriptions du site, expéditeur par académie. | Le **nom** a été retiré des menus et des messages. La règle est portée par une capacité calculée par le serveur (`online_admissions`, `monthly_reports`, `public_preregistrations`) ou par un réglage (`PUBLIC_SITE_ONLINE_ACADEMY_CODE`, `PUBLIC_SITE_CAMPUS_ACADEMY_CODE`, `FEBA_FROM_EMAIL` / `FHA_FROM_EMAIL`). |
| 3 | **Technique, test, historique** | Commentaires et docstrings décrivant l'historique, constantes `School.CODE_FEBA`, jeux de démonstration, commandes d'administration, tests, `verbose_name` de l'admin Django, noms de variables d'environnement, polices `FEBA-Text`. | Conservés : ils n'atteignent pas l'utilisateur d'une autre académie. |
| 4 | **Marque légitime** | Site vitrine public de FEBA (`frontend/src/site/`) ; identité visuelle livrée **pour** FEBA et FEBA FHA (`branding.py`, attribuée par code et jamais à une autre académie) ; plateforme elle-même (page de connexion, tableau de bord du super administrateur, service de santé, mention de la visio). | Conservés. |

## Corrections de catégorie 1 (identité codée en dur → données)

| Où | Avant | Après |
|---|---|---|
| Emploi du temps (`Schedule.jsx`) | onglets « FEBA — cours présentiels » et « FEBA FHA — séances en ligne » | une académie active : un onglet « *son nom* — cours présentiels / séances en ligne », et pour le super administrateur la liste des autres académies sélectionnables ; « Toutes les Académies » : un onglet par type présent, avec le nombre d'académies et leur liste (abrégée au-delà de 3, complète en info-bulle). Testé à 2, 7 et 19 académies. |
| En-têtes des menus (5 espaces) | « FEBA », « FEBA Academy » | nom court de l'académie active, nom complet en info-bulle, tronqué si long (`AcademyName`) |
| Menus admin et super admin | « Admissions FEBA FHA », « Rapports mensuels » affichés sur `placement_tests` (toute académie en ligne ; toute académie chez le super admin) | « Admissions en ligne » et « Rapports mensuels » sur `online_admissions` / `monthly_reports` ; en « Toutes les Académies », affichés si une académie accessible les possède |
| URL saisie à la main (`/admin/fha-admissions`, `/admin/monthly-reports`) | écran d'une autre académie, vide ou refusé | « Fonctionnalité non activée pour *académie* » (`FeatureGate`) |
| Badge d'académie (`AcademyBadge`) | carte des codes FEBA / FEBA_FHA ; toute autre académie en **orange** (couleur d'avertissement) | texte = `academy_short_name` ou nom ; teinte stable dérivée du code ; orange réservé à « Sans académie » |
| Documents officiels, Site vitrine (badges locaux) | `academy_code === "FEBA_FHA"` | badge commun |
| Site vitrine, onglet « Préinscriptions FEBA » | affiché pour toute académie présentielle | « Préinscriptions du site », sur `public_preregistrations` |
| Paiements consolidés | « Équivalent FEBA FHA : » pour USD, « FEBA : » sinon | « Montants en *devise* : » |
| Admissions, rapports mensuels (titres) | « Admissions FEBA French Heritage Academy », « Rapports mensuels FEBA FHA » | titre au nom de l'académie active |
| Séances en ligne (messages) | « FEBA Cotonou est une école présentielle… », « Sélectionnez FEBA FHA… » | nom de l'académie active ; « une académie en ligne » |
| Logo & Branding | « l'école FEBA », « Logo FEBA par défaut », image de repli cassée sans logo | nom de l'académie ; monogramme |
| Visio, SMS, boîte d'envoi, gabarits | « instance FEBA », « que FEBA vous adresse », « envoyés depuis FEBA », « FEBA les convertit » | « la plateforme », « votre académie » |
| Notes (`Grades.jsx`) | « Système Bilingue FEBA » | « Système bilingue » |
| Création d'académie | « Cours à distance (comme FEBA FHA) » | « Cours à distance » |
| Serveur : messages d'erreur | « la frontière entre FEBA et FEBA French Heritage Academy » (tarifs, documents) ; « emploi du temps FEBA / FEBA FHA » ; « préinscriptions FEBA… Admissions FEBA FHA » ; « Sélectionnez FEBA FHA » ; « aucune donnée de FEBA » ; « FEBA n'exécute jamais de macro » ; « l'instance FEBA » | formulation sans nom d'académie |
| Serveur : envois groupés | pied « Message envoyé depuis la plateforme FEBA » sous le nom d'une autre académie | « plateforme de gestion de l'académie » |
| Serveur : rattachement du site public | `get_feba_entity` cherchait `code="FEBA"` ; tâche mensuelle et planification Celery figées sur `FEBA_FHA` | `PUBLIC_SITE_CAMPUS_ACADEMY_CODE` / `PUBLIC_SITE_ONLINE_ACADEMY_CODE` |

## Catégorie 2 — ce qui reste, et pourquoi

- `apps/website/fha_*` (modèles, vues, notifications, PDF) : module du **canal public en ligne**. Les données y sont toujours rattachées à l'académie désignée par le réglage ; une autre académie y voit une liste vide et reçoit 404 par identifiant (contrat existant, testé).
- `apps/monthly_reports` : réservé à l'académie du canal en ligne. 403 pour toute autre académie, avec le message « Les rapports mensuels ne sont pas activés pour cette académie. »
- `mailer.py`, `preflight.py`, `checks.py`, `settings/base.py` : expéditeurs `FEBA_FROM_EMAIL` / `FHA_FROM_EMAIL`. Une autre académie utilise `DEFAULT_FROM_EMAIL`.
- `outbox_views.py`, `translations.js` : catégories d'e-mails du parcours d'admission en ligne (« Accusé de réception FHA (parent) »…), qui ne concernent que ce canal. `translations.js` contient aussi les textes des formulaires publics FHA et les gabarits intégrés « Diplôme FEBA » / « Certificat FEBA » (libellés servis par le serveur, propres à ces académies).

## Catégorie 4 — décisions

- **Site vitrine** (`frontend/src/site/`) : c'est le site public de FEBA, avec une page FEBA French Heritage Academy. Il ne s'affiche pas dans l'espace privé d'une autre académie.
- **Plateforme** : la page de connexion (avant toute académie : logo par défaut `DEFAULT_ACADEMY_CODE`), « Contrôle total du système FEBA » (super administrateur), `/api/health/` (« FEBA School Management »), la mention `copyright` de plugNmeet (« FEBA ») et la politique de protection des mineurs dans `virtualclass/services.py`. FEBA y est l'**exploitant** de la plateforme, pas une académie présentée à la place d'une autre. La mention plugNmeet est vue par les participants de toute académie : voir `KNOWN_LIMITATIONS.md` § 000000000.
- `sms_models.py` : « Aucun compte FEBA ne correspond à ce destinataire » est un choix de modèle. Le modifier imposerait une migration. Il n'est visible que dans le journal SMS du super administrateur.

## Contrôles automatiques qui verrouillent l'audit

- `frontend/src/layouts/menuIdentity.test.jsx` : 5 espaces avec « testete » (nom long et accentué) ; aucune entrée admissions ou rapports ; en-tête à son nom ; « Toutes les Académies ».
- `frontend/src/pages/admin/Schedule.tabs.test.jsx` : 2, 7 et 19 académies, testete, en ligne quelconque.
- `frontend/src/components/AcademyBadge.test.jsx` : badge et `FeatureGate`.
- `backend/tests/test_academy_identity_features.py` : capacités calculées, non falsifiables par les réglages, rattachement par réglage, 403 des rapports mensuels sans nom d'académie.
- `e2e/parcours-langues-identite.mjs` : navigateur réel, super administrateur puis administrateur de testete, bascule, rechargement, reconnexion.
- Contre-épreuve : les tests frontend rejoués sur les fichiers d'origine (HEAD) échouent (15 échecs), ce qui montre qu'ils détectent les défauts corrigés.

## Annexe — inventaire complet

248 fichiers, 2057 occurrences.

| Catégorie | Fichiers |
|---|---|
| 1 — identité dynamique | 0 |
| 2 — règle de type / fonctionnalité | 24 |
| 3 — technique / test / historique | 185 |
| 4 — marque légitime | 39 |
| fichiers corrigés pendant la mission et contenant encore le mot (commentaire, historique) | 25 |

| Fichier | Occurrences | Catégorie | Mission |
|---|---|---|---|
| `backend/apps/accounts/entity_views.py` | 1 | 3 |  |
| `backend/apps/attendance/serializers.py` | 2 | 3 |  |
| `backend/apps/bulletins/pdf_generator.py` | 3 | 3 |  |
| `backend/apps/classes/migrations/0003_class_language_track.py` | 1 | 3 |  |
| `backend/apps/classes/migrations/0004_audit_language_tracks.py` | 2 | 3 |  |
| `backend/apps/classes/models.py` | 2 | 3 |  |
| `backend/apps/classes/subject_rules.py` | 6 | 3 |  |
| `backend/apps/core/academy_scope.py` | 1 | 3 |  |
| `backend/apps/core/academy_serializers.py` | 7 | 3 |  |
| `backend/apps/core/age.py` | 2 | 3 |  |
| `backend/apps/core/currency.py` | 1 | 3 |  |
| `backend/apps/core/currency_conversion.py` | 3 | 3 |  |
| `backend/apps/core/features.py` | 3 | 3 |  |
| `backend/apps/core/management/commands/clean_previous_usage_data.py` | 4 | 3 |  |
| `backend/apps/core/management/commands/field_mapping_audit.py` | 21 | 3 |  |
| `backend/apps/core/pdf_longtext.py` | 4 | 3 |  |
| `backend/apps/core/preflight.py` | 5 | 2 |  |
| `backend/apps/core/tenancy.py` | 3 | 3 |  |
| `backend/apps/dashboard/health_urls.py` | 1 | 4 |  |
| `backend/apps/dashboard/views.py` | 1 | 3 |  |
| `backend/apps/documents/academy_templates.py` | 6 | 3 |  |
| `backend/apps/documents/apps.py` | 1 | 3 |  |
| `backend/apps/documents/conversion.py` | 2 | 3 | corrigé |
| `backend/apps/documents/management/commands/document_analyze.py` | 1 | 3 |  |
| `backend/apps/documents/management/commands/document_compare.py` | 1 | 3 |  |
| `backend/apps/documents/management/commands/document_samples.py` | 4 | 3 |  |
| `backend/apps/documents/models.py` | 3 | 3 | corrigé |
| `backend/apps/documents/textfit.py` | 3 | 3 |  |
| `backend/apps/documents/views.py` | 3 | 3 |  |
| `backend/apps/grades/grading.py` | 1 | 3 |  |
| `backend/apps/grades/migrations/0012_alter_grade_note_coefficient.py` | 1 | 3 |  |
| `backend/apps/grades/models.py` | 2 | 3 |  |
| `backend/apps/monthly_reports/apps.py` | 2 | 2 |  |
| `backend/apps/monthly_reports/models.py` | 3 | 2 |  |
| `backend/apps/monthly_reports/pdf.py` | 1 | 2 |  |
| `backend/apps/monthly_reports/views.py` | 1 | 2 | corrigé |
| `backend/apps/notifications/backends.py` | 1 | 3 |  |
| `backend/apps/notifications/checks.py` | 4 | 2 |  |
| `backend/apps/notifications/mailer.py` | 12 | 2 |  |
| `backend/apps/notifications/management/commands/email_check.py` | 1 | 3 |  |
| `backend/apps/notifications/management/commands/sms_check.py` | 2 | 3 |  |
| `backend/apps/notifications/migrations/0007_sms_messages.py` | 1 | 3 |  |
| `backend/apps/notifications/outbox_views.py` | 6 | 2 |  |
| `backend/apps/notifications/sms.py` | 1 | 3 |  |
| `backend/apps/notifications/sms_models.py` | 1 | 4 |  |
| `backend/apps/notifications/sms_providers.py` | 1 | 3 |  |
| `backend/apps/notifications/tasks.py` | 3 | 3 |  |
| `backend/apps/parents/migrations/0002_unique_student_has_one_parent.py` | 1 | 3 |  |
| `backend/apps/payments/card_views.py` | 3 | 3 |  |
| `backend/apps/payments/exchange_rate_models.py` | 3 | 3 |  |
| `backend/apps/payments/management/commands/audit_payment_currencies.py` | 1 | 3 |  |
| `backend/apps/payments/management/commands/repair_payment_currencies.py` | 2 | 3 |  |
| `backend/apps/payments/migrations/0007_payment_amount_minor_payment_currency_and_more.py` | 1 | 3 |  |
| `backend/apps/payments/migrations/0011_backfill_payment_paid_at.py` | 1 | 3 |  |
| `backend/apps/payments/models.py` | 1 | 3 |  |
| `backend/apps/payments/pdf_generator.py` | 3 | 3 |  |
| `backend/apps/payments/serializers.py` | 2 | 3 |  |
| `backend/apps/payments/transaction_models.py` | 1 | 3 |  |
| `backend/apps/payments/views.py` | 4 | 3 |  |
| `backend/apps/schedule/migrations/0003_onlinesessionschedule_and_more.py` | 5 | 3 |  |
| `backend/apps/schedule/models.py` | 14 | 3 | corrigé |
| `backend/apps/schedule/serializers.py` | 7 | 3 |  |
| `backend/apps/schedule/urls.py` | 3 | 3 |  |
| `backend/apps/schedule/views.py` | 8 | 3 | corrigé |
| `backend/apps/schools/branding.py` | 42 | 4 |  |
| `backend/apps/schools/institution.py` | 7 | 4 |  |
| `backend/apps/schools/management/commands/branding_refresh_documents.py` | 9 | 3 |  |
| `backend/apps/schools/management/commands/init_academies.py` | 13 | 3 |  |
| `backend/apps/schools/management/commands/seed_check.py` | 33 | 3 |  |
| `backend/apps/schools/management/commands/seed_demo_data.py` | 61 | 3 |  |
| `backend/apps/schools/migrations/0009_school_matricule_prefix_alter_room_custom_type_label_and_more.py` | 1 | 3 |  |
| `backend/apps/schools/migrations/0010_feba_matricule_prefix.py` | 5 | 3 |  |
| `backend/apps/schools/migrations/0011_official_school_name.py` | 4 | 3 |  |
| `backend/apps/schools/migrations/0012_school_code_school_currency_school_default_language_and_more.py` | 5 | 3 |  |
| `backend/apps/schools/migrations/0013_entity_codes_and_fha.py` | 39 | 3 |  |
| `backend/apps/schools/migrations/0014_remove_school_currency_school_currency_code_and_more.py` | 4 | 3 |  |
| `backend/apps/schools/migrations/0017_enable_video_for_all_academies.py` | 1 | 3 |  |
| `backend/apps/schools/migrations/0019_branding_settings_image_defaults.py` | 1 | 3 |  |
| `backend/apps/schools/models.py` | 41 | 2 |  |
| `backend/apps/schools/public_branding.py` | 3 | 4 |  |
| `backend/apps/schools/views.py` | 6 | 3 |  |
| `backend/apps/students/migrations/0005_studentmatriculesequence.py` | 1 | 3 |  |
| `backend/apps/students/models.py` | 7 | 3 |  |
| `backend/apps/virtualclass/management/commands/jitsi_health.py` | 1 | 3 |  |
| `backend/apps/virtualclass/meetings.py` | 8 | 3 |  |
| `backend/apps/virtualclass/models.py` | 2 | 3 |  |
| `backend/apps/virtualclass/plugnmeet.py` | 6 | 4 |  |
| `backend/apps/virtualclass/serializers.py` | 1 | 3 |  |
| `backend/apps/virtualclass/services.py` | 5 | 4 |  |
| `backend/apps/virtualclass/views.py` | 4 | 3 | corrigé |
| `backend/apps/website/feba_prereg.py` | 4 | 2 |  |
| `backend/apps/website/feba_prereg_pdf.py` | 3 | 2 |  |
| `backend/apps/website/fha_enrollment.py` | 9 | 2 |  |
| `backend/apps/website/fha_notifications.py` | 6 | 2 |  |
| `backend/apps/website/fha_pdf.py` | 5 | 2 |  |
| `backend/apps/website/fha_serializers.py` | 47 | 2 | corrigé |
| `backend/apps/website/fha_views.py` | 88 | 2 |  |
| `backend/apps/website/management/commands/seed_website.py` | 33 | 3 |  |
| `backend/apps/website/migrations/0001_initial.py` | 3 | 3 |  |
| `backend/apps/website/migrations/0003_official_name_amp.py` | 2 | 3 |  |
| `backend/apps/website/migrations/0004_contactmessage_category_contactmessage_country_and_more.py` | 12 | 3 |  |
| `backend/apps/website/migrations/0005_backfill_form_entities.py` | 15 | 3 |  |
| `backend/apps/website/migrations/0006_alter_preregistration_desired_level_and_more.py` | 12 | 3 |  |
| `backend/apps/website/migrations/0010_preregistration_address_and_more.py` | 1 | 3 |  |
| `backend/apps/website/models.py` | 69 | 2 |  |
| `backend/apps/website/private_storage.py` | 3 | 2 |  |
| `backend/apps/website/serializers.py` | 5 | 2 |  |
| `backend/apps/website/urls.py` | 9 | 2 |  |
| `backend/apps/website/views.py` | 14 | 2 | corrigé |
| `backend/feba_project/branding.py` | 2 | 3 |  |
| `backend/feba_project/settings/base.py` | 20 | 2 |  |
| `e2e/academies.mjs` | 40 | 3 |  |
| `e2e/devises-et-documents.mjs` | 12 | 3 |  |
| `e2e/parcours-documents-officiels.mjs` | 85 | 3 |  |
| `e2e/parcours-gabarits-multiformats.mjs` | 17 | 3 |  |
| `e2e/parcours-gabarits.mjs` | 21 | 3 |  |
| `e2e/parcours-langues-identite.mjs` | 21 | 3 |  |
| `e2e/parcours-preinscription-feba.mjs` | 9 | 3 |  |
| `e2e/parcours-rapports-mensuels.mjs` | 7 | 3 |  |
| `e2e/parcours-v9.mjs` | 12 | 3 |  |
| `e2e/site-public-anglais.mjs` | 2 | 3 |  |
| `frontend/src/api/academyScope.js` | 3 | 3 |  |
| `frontend/src/api/academyScope.test.js` | 30 | 3 |  |
| `frontend/src/api/index.js` | 8 | 3 |  |
| `frontend/src/api/sessionInterceptor.test.js` | 1 | 3 |  |
| `frontend/src/api/tokenRefresh.js` | 1 | 3 |  |
| `frontend/src/api/tokenRefresh.test.js` | 1 | 3 |  |
| `frontend/src/components/AcademyBadge.jsx` | 3 | 3 | corrigé |
| `frontend/src/components/AcademyLogo.test.jsx` | 2 | 3 |  |
| `frontend/src/components/AcademyName.jsx` | 2 | 3 |  |
| `frontend/src/components/EntitySwitcher.jsx` | 2 | 3 |  |
| `frontend/src/components/JitsiInfrastructureBanner.jsx` | 1 | 3 | corrigé |
| `frontend/src/components/SmsPreferencesCard.jsx` | 1 | 3 | corrigé |
| `frontend/src/components/bulletins/BulletinCommentManager.test.jsx` | 3 | 3 |  |
| `frontend/src/components/ui/DataTable.jsx` | 2 | 3 |  |
| `frontend/src/components/ui/DetailField.jsx` | 2 | 3 |  |
| `frontend/src/components/ui/DetailField.test.jsx` | 2 | 3 |  |
| `frontend/src/context/academyBoot.test.jsx` | 7 | 3 |  |
| `frontend/src/hooks/useBranding.js` | 6 | 4 |  |
| `frontend/src/hooks/useBranding.test.jsx` | 23 | 3 |  |
| `frontend/src/hooks/useSessionKeepAlive.js` | 1 | 3 |  |
| `frontend/src/i18n/coverage.test.js` | 2 | 3 |  |
| `frontend/src/i18n/i18n.test.js` | 2 | 3 |  |
| `frontend/src/i18n/index.js` | 1 | 3 |  |
| `frontend/src/i18n/translations.js` | 41 | 2 |  |
| `frontend/src/layouts/AdminLayout.jsx` | 3 | 3 | corrigé |
| `frontend/src/layouts/ParentLayout.jsx` | 3 | 3 | corrigé |
| `frontend/src/layouts/StudentLayout.jsx` | 3 | 3 | corrigé |
| `frontend/src/layouts/TeacherLayout.jsx` | 3 | 3 | corrigé |
| `frontend/src/layouts/menuIdentity.test.jsx` | 25 | 3 |  |
| `frontend/src/pages/LoginPage.jsx` | 1 | 4 |  |
| `frontend/src/pages/admin/DocumentTemplates.test.jsx` | 2 | 3 |  |
| `frontend/src/pages/admin/FhaAdmissions.confirm.test.jsx` | 22 | 3 |  |
| `frontend/src/pages/admin/FhaAdmissions.jsx` | 4 | 2 | corrigé |
| `frontend/src/pages/admin/Grades.jsx` | 3 | 3 | corrigé |
| `frontend/src/pages/admin/MassEmail.test.jsx` | 3 | 3 |  |
| `frontend/src/pages/admin/MonthlyReports.jsx` | 1 | 3 | corrigé |
| `frontend/src/pages/admin/OfficialDocuments.kind.test.jsx` | 2 | 3 |  |
| `frontend/src/pages/admin/Outbox.jsx` | 1 | 3 | corrigé |
| `frontend/src/pages/admin/Outbox.test.jsx` | 3 | 3 |  |
| `frontend/src/pages/admin/Payments.jsx` | 2 | 3 | corrigé |
| `frontend/src/pages/admin/Schedule.jsx` | 3 | 3 | corrigé |
| `frontend/src/pages/admin/Schedule.tabs.test.jsx` | 5 | 3 |  |
| `frontend/src/pages/admin/Website.jsx` | 9 | 3 | corrigé |
| `frontend/src/pages/admin/Website.prereg.test.jsx` | 7 | 3 |  |
| `frontend/src/pages/admin/schedule/CampusSchedule.jsx` | 3 | 3 |  |
| `frontend/src/pages/admin/schedule/OnlineSchedule.jsx` | 11 | 3 | corrigé |
| `frontend/src/pages/admin/schedule/ScheduleGrid.test.jsx` | 9 | 3 |  |
| `frontend/src/pages/shared/VirtualRoomEnded.jsx` | 6 | 3 | corrigé |
| `frontend/src/pages/shared/VirtualRoomEnded.test.jsx` | 7 | 3 |  |
| `frontend/src/pages/shared/VirtualRoomSession.jsx` | 9 | 3 | corrigé |
| `frontend/src/pages/shared/VirtualRoomSession.test.jsx` | 11 | 3 |  |
| `frontend/src/pages/superadmin/Academies.test.jsx` | 18 | 3 |  |
| `frontend/src/pages/superadmin/Dashboard.jsx` | 1 | 4 |  |
| `frontend/src/router/index.jsx` | 6 | 3 |  |
| `frontend/src/site/SiteLayout.jsx` | 15 | 4 |  |
| `frontend/src/site/components/FhaFlyerDownload.jsx` | 6 | 4 |  |
| `frontend/src/site/components/HeroCarousel.jsx` | 1 | 4 |  |
| `frontend/src/site/components/PublicForms.jsx` | 3 | 4 |  |
| `frontend/src/site/components/Seo.jsx` | 16 | 4 |  |
| `frontend/src/site/components/Seo.test.jsx` | 14 | 3 |  |
| `frontend/src/site/components/SiteLangSwitcher.jsx` | 3 | 4 |  |
| `frontend/src/site/content.js` | 5 | 4 |  |
| `frontend/src/site/fhaContent.js` | 47 | 4 |  |
| `frontend/src/site/fhaEnrollGender.test.jsx` | 5 | 3 |  |
| `frontend/src/site/fhaFlyerDownload.test.jsx` | 7 | 3 |  |
| `frontend/src/site/fhaPlans.js` | 8 | 4 |  |
| `frontend/src/site/i18nCoverage.test.js` | 5 | 3 |  |
| `frontend/src/site/legacyNaming.test.js` | 15 | 3 |  |
| `frontend/src/site/mediaMeta.js` | 5 | 4 |  |
| `frontend/src/site/mediaMeta.test.js` | 1 | 3 |  |
| `frontend/src/site/mobileLangSwitcher.test.jsx` | 1 | 3 |  |
| `frontend/src/site/pages/AboutPage.jsx` | 16 | 4 |  |
| `frontend/src/site/pages/AcademicsPage.jsx` | 6 | 4 |  |
| `frontend/src/site/pages/AdmissionsPage.jsx` | 10 | 4 |  |
| `frontend/src/site/pages/CampusPage.jsx` | 5 | 4 |  |
| `frontend/src/site/pages/ContactPage.jsx` | 4 | 4 |  |
| `frontend/src/site/pages/FhaContactPage.jsx` | 17 | 4 |  |
| `frontend/src/site/pages/FhaEnrollPage.jsx` | 18 | 4 |  |
| `frontend/src/site/pages/FhaPage.jsx` | 103 | 4 |  |
| `frontend/src/site/pages/FhaPlacementTestPage.jsx` | 15 | 4 |  |
| `frontend/src/site/pages/GalleryPage.jsx` | 6 | 4 |  |
| `frontend/src/site/pages/HomePage.jsx` | 47 | 4 |  |
| `frontend/src/site/pages/LegalPages.jsx` | 3 | 4 |  |
| `frontend/src/site/pages/NewsPage.jsx` | 2 | 4 |  |
| `frontend/src/site/pages/SchoolLifePage.jsx` | 8 | 4 |  |
| `frontend/src/site/pages/SiteNotFound.jsx` | 2 | 4 |  |
| `frontend/src/site/site.test.jsx` | 13 | 3 |  |
| `frontend/src/site/siteApi.js` | 5 | 4 |  |
| `frontend/src/site/siteDefaults.js` | 20 | 4 |  |
| `frontend/src/site/siteTranslations.js` | 28 | 4 |  |
| `frontend/src/site/useSiteLang.js` | 5 | 4 |  |
| `frontend/src/utils/age.test.jsx` | 2 | 3 |  |
| `frontend/src/utils/classLanguage.test.js` | 2 | 3 |  |
| `frontend/src/utils/datetime.js` | 1 | 3 |  |
| `frontend/src/utils/datetime.test.js` | 1 | 3 |  |
| `frontend/src/utils/errors.js` | 2 | 3 |  |
| `frontend/src/utils/money.js` | 1 | 3 |  |
| `frontend/src/utils/money.test.js` | 1 | 3 |  |
| `nginx/nginx.prod.conf` | 3 | 3 |  |
| `nginx/sites-available/meet.globalfeba.com.conf` | 2 | 3 |  |
| `plugnmeet/client-branding/feba-branding.js` | 4 | 3 |  |
| `plugnmeet/docker-compose.plugnmeet.yml` | 2 | 3 |  |
| `plugnmeet/runtime/client/dist/assets/chunks/excalidraw.WUE7FSrg.js` | 1 | 3 |  |
| `plugnmeet/runtime/client/dist/assets/feba/feba-branding.js` | 4 | 3 |  |
| `scripts/backup_database.sh` | 2 | 3 |  |
| `scripts/backup_files.sh` | 3 | 3 |  |
| `scripts/backup_jitsi.sh` | 1 | 3 |  |
| `scripts/bootstrap.sh` | 5 | 3 |  |
| `scripts/build_branding_assets.py` | 2 | 3 |  |
| `scripts/build_fha_flyer_pdf.py` | 3 | 3 |  |
| `scripts/deploy_feba.sh` | 18 | 3 |  |
| `scripts/deploy_production.sh` | 2 | 3 |  |
| `scripts/diagnose.sh` | 2 | 3 |  |
| `scripts/doctor.sh` | 2 | 3 |  |
| `scripts/generate_guides.py` | 12 | 3 |  |
| `scripts/install_check.sh` | 2 | 3 |  |
| `scripts/jitsi_config_check.sh` | 3 | 3 |  |
| `scripts/make_delivery.sh` | 9 | 3 |  |
| `scripts/make_final_delivery.sh` | 4 | 3 |  |
| `scripts/optimize_site_media.py` | 5 | 3 |  |
| `scripts/plugnmeet_setup.sh` | 23 | 3 |  |
| `scripts/production_health.sh` | 2 | 3 |  |
| `scripts/repair.sh` | 2 | 3 |  |
| `scripts/restore_backup.sh` | 2 | 3 |  |
| `scripts/tls_bootstrap.sh` | 1 | 3 |  |
| `scripts/verify_feba.py` | 2 | 3 |  |
| `scripts/verify_parent_eleve.sh` | 2 | 3 |  |
