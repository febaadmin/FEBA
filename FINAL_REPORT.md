# FEBA — Programme linguistique des académies, identités sans nom codé en dur

27 octobre 2026 · branche `feat/langues-identite-academies`.

- **Départ** : commit `3ef0b22` (archive `FEBA_GABARITS_MULTIFORMATS_DIPLOMES_CERTIFICATS_VALIDEE.zip`, vérifiée identique).
- **Commit livré** : voir `SOURCE_COMMIT.txt` dans l'archive.
- **Statuts** : PASS · FAIL · BLOCKED · NOT RUN.
- **Documents associés** :
  - tests : `TEST_REPORT.md` ;
  - audit des références : `AUDIT_IDENTITES_ACADEMIES.md` ;
  - mode d'emploi : `ACADEMIES_GUIDE.md` § 1 bis ;
  - actions de production : `MANUAL_PRODUCTION_ACTIONS.md` § 00000000 ;
  - limites : `KNOWN_LIMITATIONS.md` § 000000000.

Toutes les validations sont **locales** : PostgreSQL, Mailpit, Chrome réel, image Docker avec LibreOffice, et pile de production locale construite depuis l'archive (`DELIVERY_VERIFICATION_LANGUES_IDENTITE.txt`, à côté de l'archive). Rien n'a été fait sur Hetzner (SSH refusé). Rien n'a été déployé en production.

---

## A. Programme linguistique (P0-A)

**Modèle.** Nouveau champ `School.curriculum_language_mode` (`french_only`, `english_only`, `bilingual`), distinct de `default_language`, qui reste la langue de l'interface et des documents.
- Il est **obligatoire** à la création : le serializer le refuse s'il manque, avec le message « Le programme linguistique est obligatoire… ».
- Il ne peut pas redevenir vide.
- Seul le super administrateur peut le modifier.

**Une seule source de vérité** : `apps/classes/subject_rules.py`. `Class.language_track` est conservé. Le parcours **appliqué** (`effective_track`) vaut francophone dans une académie « français uniquement » et anglophone dans une académie « anglais uniquement ». Dans une académie bilingue, c'est le parcours déclaré, sauf si l'académie n'autorise pas les classes monolingues (`monolingual_classes`) : il vaut alors bilingue.

**Contrôles serveur**, sur chaque chemin d'écriture :

| Chemin | Contrôle |
|---|---|
| Matières (création, modification) | langue admise par le programme ; changement de langue refusé si une classe qui porte la matière ne l'enseigne pas |
| Classes (création, modification) | parcours admis par l'académie ; parcours par défaut du programme |
| Copie d'année | conserve le parcours (**défaut corrigé** : les classes copiées devenaient toutes bilingues) |
| Notes unitaires, `bulk_save`, `bulk-create` | matière admise par le programme, et enseignée par la classe de l'élève pour l'année ; refus ligne par ligne |
| Créneaux présentiels, séances en ligne | mêmes règles, par classe ou groupe |
| Bulletins | sections attendues = langues du parcours appliqué. Français : section française seule, pas de 60/40. Anglais : section anglaise seule. Bilingue : deux sections et 60/40 |

**Matière « bilingue »**, auparavant refusée partout : elle devient une matière **commune**. Elle n'est admise que dans une classe bilingue d'une académie bilingue. Elle est comptée **une fois** dans la moyenne générale, n'entre ni dans les moyennes FR/EN ni dans le 60/40, et s'imprime dans « Autres matières ».

**Barèmes** inchangés : /10 (maternelle, primaire), /20 (collège, lycée). Ils sont vérifiés sur le PDF imprimé (« 7.20/10 », « 13.00/20 »).

**Changement de programme** :
- diagnostic (`GET …/language-diagnostic/?mode=`, super administrateur seul) : matières, classes, notes rattachées ;
- refus 400 avec ce diagnostic, sauf confirmation explicite ;
- **rien n'est supprimé ni converti** ; le parcours stocké des classes est aligné sur le parcours appliqué.

**Migration** `schools.0021`. Elle classe les académies d'après leurs données, sans deviner. Une académie ambiguë reste « À configurer » et garde son fonctionnement historique. `init_academies` ne complète FEBA et FEBA FHA en « bilingue » que si leur programme est vide. Le retour arrière `migrate schools 0020` a été testé (puis réappliqué).

**Écran « Académies »** : section « Programme linguistique » à la création (bouton inactif sans choix) et à la modification. Diagnostic affiché, case de confirmation exigée en cas de conflit, colonne « Programme linguistique » (« À configurer » si vide). Les écrans Matières, Classes et Notes ne proposent que ce que le serveur admet. L'onglet « Bilingue » des notes est masqué pour un programme monolingue.

## B. Identités codées en dur (P0-B)

`AUDIT_IDENTITES_ACADEMIES.md` couvre 248 fichiers et 2057 occurrences, classées en quatre catégories avec un inventaire complet. **Aucune identité d'académie codée en dur ne reste à l'écran ni dans un message d'API.**

**Emploi du temps** :
- une académie active : un onglet à **son** nom, pour **son** type ;
- un super administrateur voit en plus les autres académies sélectionnables, nommées ;
- « Toutes les Académies » : un onglet par type, avec le nombre et la liste des académies. Testé à 2, 7 et 19 académies.

**Menus** : « Admissions en ligne » et « Rapports mensuels » suivent les capacités calculées par le serveur (`online_admissions`, `monthly_reports`). Avant, ils suivaient `placement_tests`, c'est-à-dire toute académie en ligne, et toute académie chez le super administrateur. L'URL saisie à la main affiche « Fonctionnalité non activée ». Côté serveur : les rapports mensuels renvoient 403 ; les admissions d'une autre académie donnent une liste vide et 404 par identifiant (contrat existant, testé).

**Rattachement du site public** : réglages `PUBLIC_SITE_ONLINE_ACADEMY_CODE` et `PUBLIC_SITE_CAMPUS_ACADEMY_CODE` (défauts : FEBA_FHA, FEBA) au lieu des codes écrits dans le code. Les capacités ne peuvent pas être falsifiées par `settings['features']`.

**Autres corrections** :
- en-têtes des 5 espaces ;
- badge d'académie : une nouvelle académie n'est plus en orange « avertissement » ;
- documents officiels ;
- onglet « Préinscriptions » (`public_preregistrations`) ;
- paiements consolidés (libellé par devise) ;
- titres des admissions et rapports mensuels ;
- branding (monogramme au lieu d'une image cassée) ;
- messages serveur et visio.

## C. Isolation, bascule, rechargement, reconnexion

- Campagnes 2, 7 et 19 académies (`test_isolation_2_7_19_academies.py`) : PASS.
- Navigateur réel (`e2e/parcours-langues-identite.mjs`) :
  - le super administrateur crée « testete » (« Académie Évangélique Saint-Éloi de Natitingou », français uniquement) **depuis l'écran** ;
  - bascules testete / FEBA FHA / Toutes, rechargement ;
  - l'administrateur de testete se connecte, se déconnecte et se reconnecte : toujours testete, aucun menu ni nom d'une autre académie ;
  - une matière anglaise forgée à la main est refusée (400).
- `e2e/academies.mjs` : PASS après deux corrections.
  - Son contrôle des deux onglets « FEBA » / « FEBA FHA » était **obsolète**, car il encodait précisément le défaut à supprimer. Il est remplacé par l'onglet nommé d'après les données, la liste des académies en ligne et le 403 serveur, que le scénario vérifie désormais par l'API. La couverture est conservée.
  - Sa mesure lisait la réponse de l'académie précédente après un délai fixe de 500 ms (échec déjà observé lors de la mission précédente). Elle attend maintenant la réponse effective qui suit la bascule.

## D. Défauts trouvés et corrigés pendant la mission

| Défaut | Correction | Preuve |
|---|---|---|
| `copy_from_year` perdait le parcours des classes | copie de `language_track` | test ; contre-épreuve : le test échoue sans la correction |
| Matière « bilingue » inutilisable (refusée par toute classe) | sens défini (matière commune) | bulletin PDF bilingue |
| Diagnostic accessible à un administrateur d'académie (`get_permissions` écrasait la permission de l'action) | réservé au super administrateur | test 403 |
| Migration : parcours comparés en minuscules alors qu'ils sont stockés en majuscules (une académie francophone serait restée « À configurer ») | constantes alignées sur `Class.TRACK_*` | test de migration sur données |
| Diagnostic dans le 400 : DRF convertit `ok: False` en chaîne « False », qui devient vraie dans le navigateur | `ok` retiré du détail d'erreur | test |
| Onglet « Bilingue » des notes (60/40) proposé à une académie monolingue | masqué | E2E |
| Image de logo cassée sur « Logo & Branding » pour une académie sans logo | monogramme | E2E sans erreur HTTP hors refus attendus |

Contre-épreuve frontend : les nouveaux tests, rejoués sur les fichiers d'origine, échouent (15 échecs).

## E. Livraison et statuts

| Élément | Statut |
|---|---|
| Backend PostgreSQL, SQLite, migrations, PDF (dans l'image LibreOffice) | PASS (chiffres : `TEST_REPORT.md`) |
| Vitest, ESLint (0 erreur), build | PASS |
| E2E navigateur réel | PASS |
| Archive, extraction neuve, tests depuis l'extraction, montée de version sur la pile de production locale, sauvegarde / restauration | voir `DELIVERY_VERIFICATION_LANGUES_IDENTITE.txt` |
| plugNmeet réel (`test_plugnmeet_integration`) | **NOT RUN** (pile locale retirée ; code de visio inchangé hors deux messages) |
| Hetzner, préproduction, plugNmeet de production, SMTP Hostinger, Twilio | **BLOCKED** |
| Déploiement en production | **NOT RUN** (non autorisé) |
