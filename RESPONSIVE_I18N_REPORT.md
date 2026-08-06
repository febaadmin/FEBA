# RESPONSIVE_I18N_REPORT — bouton EN/FR sur mobile

**Priorité n°9.** Statut : **corrigé, prouvé par test automatisé.**

## Symptôme

Sur petit écran, aucun bouton de traduction n'était visible dans l'en-tête.
Il fallait ouvrir le menu hamburger — et deviner qu'il s'y trouvait.

## Cause racine — ANALYSE STATIQUE

Dans `frontend/src/site/SiteLayout.jsx`, `SiteLangSwitcher` n'apparaissait
qu'à deux endroits :

1. `<div className="hidden min-[1200px]:flex …">` — masqué sous 1200 px ;
2. à l'intérieur de `{menuOpen && (<nav …>)}` — donc conditionné à
   l'ouverture du menu.

Entre 320 px et 1199 px, menu fermé, le sélecteur n'existait tout simplement
pas dans le DOM.

## Correction

Un conteneur `min-[1200px]:hidden` réunit désormais le sélecteur et le bouton
menu dans la barre elle-même, dans l'ordre attendu
`Logo | FEBA | EN/FR | Menu`. C'est le **même composant** que sur desktop —
une seule source de vérité pour la langue, aucune désynchronisation possible.
Le sélecteur du menu déroulant a été supprimé : il aurait affiché deux
sélecteurs simultanés dès l'ouverture du menu.

## Accessibilité

Inchangée et vérifiée par test : `role="group"` avec `aria-label` traduit,
`aria-pressed` sur l'option active, `aria-label` par bouton (« English » /
« Français »), éléments `<button>` natifs donc navigables et activables au
clavier. Cible tactile : `px-3 py-1.5` sur un texte de 12 px, soit environ
32 px de haut, dans un conteneur d'en-tête de 64 px.

## Tests — 6 passants

`frontend/src/site/mobileLangSwitcher.test.jsx` : présence menu fermé ; les
deux langues étiquetées ; `aria-pressed` correct ; changement effectif au
clic ; pas de doublon menu ouvert ; sélecteur et bouton menu dans le même
conteneur direct.

Les 6 tests échouent contre le code d'origine.

## Non vérifié

**VALIDATION DOCKER LOCALE REQUISE** — les largeurs 320 / 375 / 390 / 430 /
768 / 1024 px n'ont pas été observées dans un navigateur réel. Les tests
s'exécutent sous jsdom, qui n'applique pas les media queries Tailwind : ils
vérifient la présence dans le DOM et l'absence de classes desktop-only, pas
le rendu pixel. Le point de rupture utilisé (`min-[1200px]`) est celui déjà
en place dans le projet, donc les six largeurs demandées tombent toutes du
côté « mobile » de la règle.
