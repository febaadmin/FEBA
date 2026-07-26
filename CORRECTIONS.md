# CORRECTIONS — FEBA V4 → V8 (26/07/2026)

## V8 (26/07/2026)

P1 création du profil Enseignant réparée (matricule `count()+1` → `max+1`,
création atomique, erreurs 400 exploitables) ; P2 audit de tous les profils +
faille de cloisonnement multi-établissement corrigée ; P3 remontée **réelle**
des erreurs techniques aux super administrateurs (incidents, sanitisation,
dédoublonnage, notifications, interface dédiée) ; P4 poids d'évaluation unique
(12 + 5 = **8,50**) ; P5 bulletins **sur 10** pour les niveaux 1 à 11 (collège
sur 20) ; P6 reçu « Le Secrétariat » + cachet dédié ; P7 cachet « LA
DIRECTION » repositionné. Défauts supplémentaires corrigés sur les documents
réels (chevauchement d'en-tête, pondérée incohérente, texte tronqué) et sur les
incidents (date de résolution).

Backend **393** (SQLite) / **394** (PostgreSQL 16) ; frontend **70** ; ESLint
**0 erreur** ; build **OK**. Détails : `FINAL_REPORT.md`,
`PROFILE_CREATION_REPORT.md`, `TECHNICAL_INCIDENTS_REPORT.md`,
`GRADE_WEIGHTING_REPORT.md`, `GRADING_SCALE_REPORT.md`,
`STAMP_INTEGRATION_REPORT.md`, `PDF_LAYOUT_REPORT.md`.


## V7 (25/07/2026)
P1 nom officiel « Faith & Excellence Bilingual Academy » (& partout, source centralisée) ;
P2 « GROUPE ÉDUCATIF FEBA » sur bulletins/reçus ; P3 cachet officiel apposé (bulletins & reçus) ;
P4 note 10 conservée exactement (champs texte décimaux, plus d'altération molette/flèche) ;
P5 nouvelle façade ; P6 vidéo galerie (visionneuse à contrôles) ; P7 recadrage Admissions
(corps entiers). Backend 311 tests, frontend 70, eslint 0, build OK. Voir FINAL_REPORT.md.


## V6 / V6.1 — Carrousel, galerie, doublons, cadrages, menu, saisie groupée

Synthèse (détails : `FINAL_REPORT.md`, `CHANGELOG_FIXES.md`,
`VISUAL_FIXES_REPORT.md`, `BULK_GRADES_REPORT.md`,
`MEDIA_DUPLICATES_REPORT.md`, `MEDIA_CROP_AUDIT.md`) :

- **P1** carrousel réel à 5 slides + repli packagé (jamais d'image statique) ;
  **P2** galerie pleine + repli ; **P3** dédoublonnage (hero-campus ~8× → 2) ;
  **P4/P5** recadrages individuels + zones crème ; **P6** menu desktop une
  ligne + hamburger ; **P7** saisie groupée de notes atomique (16+6 tests,
  permissions backend, erreurs indexées), saisie simple préservée.
- **V6.1** (captures annotées) : médias fournis intégrés (`campus-logo`,
  `campus-fresque`, `apropos-equipe-pedagogique`, `petite-enfance-creche`) ;
  image de bureau **bannie** (`apropos-direction*`, `galerie-mosaique-3`)
  supprimée du site ET du paquet ; « Notre campus » et « Une équipe engagée »
  dédoublonnées ; 5 vignettes recadrées ; voile gris du carrousel → dégradé
  marine DA FEBA.
- Backend 300 tests (+1 skip), frontend 56 tests, eslint 0 erreur, build OK ;
  vérifié navigateur 375→1920 (captures + DOM).

## V5 — Corrections visuelles du site vitrine

Audit visuel complet des 44 emplacements médias du site public, puis :
**système de point focal** (backend administrable `focal_x`/`focal_y` +
registre central frontend appliqué automatiquement, variante mobile),
**dégradés FEBA centralisés** et composant `MediaFrame`, **zones crème
vides transformées en compositions** (carte CM1·CM2 conforme à la maquette,
bilinguisme, admissions, FEBA Online en vert), recadrages corrigés (portrait
équipe tête coupée, cartes niveaux, ronde, hero slide 4), hero mobile sans
chevauchement de flèches. Preuves : `MEDIA_CROP_AUDIT.md`,
`VISUAL_FIXES_REPORT.md`, captures avant/après et 9 breakpoints dans la
livraison. Tests : 284 backend / 41 frontend / build ✓ / ERP non régressé.

## V4 — priorités P1–P4 + audit

Cette itération livre les **quatre demandes prioritaires** puis une passe
d'audit :

1. **P1 — Types de notes renommés** : « Interrogation / Devoir de classe »
   et « Examen / Évaluation » dans toutes les interfaces (création,
   modification, tableaux, filtres, exports) ; valeurs internes stables →
   anciennes notes intactes.
2. **P2 — Réinitialisation de mot de passe par administrateur** :
   endpoint sécurisé (admin → enseignant/parent/élève de son
   établissement ; superadmin → + admins ; jamais un superadmin),
   hachage Django, révocation des sessions, journal d'audit, modal dans
   les écrans utilisateurs et **parcours complet de changement obligatoire**
   à la connexion suivante.
3. **P3 — Barème officiel des appréciations** : source unique
   `get_appreciation()` (9 niveaux EXCELLENT → TRÈS FAIBLE, décimales,
   normalisation des barèmes ≠ 20, rejet des valeurs invalides),
   migration des appréciations stockées, plus aucune ancienne échelle.
4. **P4 — Site vitrine public** : `/` est désormais un site public premium
   aux couleurs FEBA (13 pages, carrousel administrable, galerie +
   visionneuse + vidéo à la demande, formulaires contact/préinscription
   sécurisés, SEO complet, 57 médias réels optimisés WebP ≈9 Mo) avec CMS
   administrable (écran ERP « Site vitrine » + admin Django) — la
   connexion ERP reste accessible via le menu (« Connexion »), les cinq
   espaces privés sont inchangés.

**Preuves et détails** : [`CHANGELOG_FIXES.md`](./CHANGELOG_FIXES.md) ·
[`TEST_REPORT.md`](./TEST_REPORT.md) (280 tests backend ✅, 35 frontend ✅,
E2E navigateur desktop + mobile, build de production) ·
[`AUDIT_REPORT.md`](./AUDIT_REPORT.md) (tableau récapitulatif) ·
[`MEDIA_INVENTORY.md`](./MEDIA_INVENTORY.md) ·
[`KNOWN_LIMITATIONS.md`](./KNOWN_LIMITATIONS.md) ·
[`SECURITY_NOTES.md`](./SECURITY_NOTES.md).

## Démarrage rapide (démo locale sans Docker)

```bash
cd backend
DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite python manage.py bootstrap_demo
DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite python manage.py runserver 8000

cd frontend
npm install
BACKEND_ORIGIN=http://localhost:8000 npm run dev   # http://localhost:5173
```

Comptes de démo : `superadmin@feba.bj / SuperAdmin@2024` ·
`admin@feba.bj / Admin@2024` · `prof.math@feba.bj / Teacher@2024` ·
`parent1@feba.bj / Parent@2024` · `eleve1@feba.bj / Student@2024`.

Historique des itérations précédentes : `docs/historique/` (…_V3.md) et
`docs/RAPPORT_V*.md`.
