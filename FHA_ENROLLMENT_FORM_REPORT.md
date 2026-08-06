# FHA_ENROLLMENT_FORM_REPORT — titres des étapes de la fiche de renseignements

**Priorité n°3.** Page : `/feba-fha/enroll`. Statut : **corrigé.**

## Symptôme

Chaque étape présentait une série de champs sans titre au-dessus d'eux. Le
libellé de l'étape n'existait que dans la barre de progression de l'en-tête,
en petits caractères et à distance des champs concernés.

## Cause racine — ANALYSE STATIQUE

`frontend/src/site/pages/FhaEnrollPage.jsx` définissait `STEP_TITLES`, mais
cette constante n'était lue qu'à un seul endroit : le texte
`Étape {n}/12 — {titre}` de la barre de progression. Aucun des douze blocs
`{step === n && (…)}` ne rendait de titre.

## Correction

`STEP_META` remplace `STEP_TITLES` et porte, pour chaque étape,
`[titre FR, titre EN, intro FR, intro EN]`. Un bloc `<header>` unique, piloté
par `step`, est rendu juste au-dessus des champs : les douze étapes héritent
du même traitement, il est impossible d'en oublier une.

Chaque étape affiche : le rang (« Étape 3 / 12 »), un `<h2>` sémantique
(`id="fha-step-title"`, `tabIndex={-1}` pour permettre le déplacement du
focus), une phrase d'introduction expliquant la nature des données demandées,
et la mention « Les champs suivis d'un astérisque (*) sont obligatoires ».

`STEP_TITLES` est conservé comme dérivé de `STEP_META` : la barre de
progression continue de fonctionner sans duplication de libellés.

## Les douze titres

| # | Français | English |
|---|---|---|
| 1 | Informations sur l'enfant | Child information |
| 2 | Origines familiales et langues parlées | Family background and languages spoken |
| 3 | Niveau actuel de français | Current level of French |
| 4 | Expérience d'apprentissage du français | Previous French learning experience |
| 5 | Objectifs des parents pour l'enfant | Your goals for your child |
| 6 | Coordonnées du parent ou du tuteur principal | Main parent or guardian contact details |
| 7 | Second parent ou responsable | Second parent or guardian |
| 8 | Contact d'urgence | Emergency contact |
| 9 | Disponibilités et fuseau horaire | Availability and time zone |
| 10 | Équipement et connexion | Equipment and connection |
| 11 | Besoins pédagogiques particuliers | Specific learning needs |
| 12 | Choix de la formule, documents et consentements | Plan choice, documents and consents |

Les titres suivent les **étapes réellement présentes** dans le formulaire.
La demande citait « Test de placement » comme étape : il s'agit en réalité
d'un parcours distinct (`/feba-fha/placement-test`, modèles
`FHAPlacementTestRequest` / `FHAPlacementTestResult`), pas d'une étape de
cette fiche. Aucune étape n'a été inventée pour coller à la liste d'exemples.

## Bilinguisme

Les titres et introductions passent par le mécanisme `t(fr, en)` déjà utilisé
par la page, alimenté par le sélecteur global `useSiteLang`. Aucun texte
codé en dur dans une seule langue n'a été introduit.

## Accessibilité

Le choix de formule ajouté à l'étape 12 est groupé dans un `<fieldset>` avec
`<legend>`. Les champs existants conservent leurs `label` liés. Aucune
annotation rouge des captures n'a été intégrée à l'interface.

## Vérifications

- **Build** : `npm run build` réussit.
- **TEST AUTOMATISÉ** : la suite frontend complète (179 tests) passe, dont le
  test de couverture i18n qui refuse toute chaîne française non traduite.
- **VALIDATION DOCKER LOCALE REQUISE** : navigation précédent/suivant,
  reprise du brouillon depuis `localStorage`, validation clavier et rendu
  mobile/tablette/desktop n'ont pas été rejoués dans un navigateur réel.
