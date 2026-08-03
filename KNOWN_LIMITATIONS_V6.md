# Limitations connues — V6 (P0 à P3)

## 1. État réel des quatre anomalies

| | Anomalie | État | Preuve |
|---|---|---|---|
| P3 | Données non identifiées par académie | **Corrigé** | Navigateur : colonne « Académie » présente, badges FEBA×12, FEBA FHA×2, Sans académie×1 |
| P1 | Bilinguisme partiel | **Partiellement corrigé** | Navigateur : menu FR « Accueil · À propos… » → EN « Home · About… », persistant entre pages. **12 pages de contenu restent en français** — voir §3 |
| P0 | Filtre lent / données périmées | **Partiellement corrigé** | Navigateur : bascule vers FHA → 6 lignes (contre 15 en mode consolidé), sans rechargement manuel. La bascule reste **lente** — voir §2 |
| P2 | Onglet Préinscriptions pour FHA | **API corrigée, UI NON** | Tests : admin FHA reçoit 403 sur l'API. **L'onglet reste visible dans l'interface** — voir §4 |

## 2. P0 — ce qui marche et ce qui reste

**Corrigé** : la bascule change réellement les données, sans aucun
`window.location.reload()`. Vérifié en navigateur : mode consolidé
15 utilisateurs, FEBA FHA 6 utilisateurs. Les clés React Query des écrans
retouchés portent l'académie active.

**Non résolu — la lenteur.** La correction repose sur un remontage du
sous-arbre routé (`<Outlet key={academyKey}>`), qui purge le cache et
relance toutes les requêtes. Conséquences mesurées :

- la bascule déclenche **deux remontages** successifs (cache vidé, puis
  contexte rechargé), donc deux vagues de requêtes ;
- il faut environ **4 à 5 secondes** avant que les données définitives
  s'affichent, ce qui correspond exactement à la plainte d'origine
  (« ça met trop de temps à s'actualiser ») ;
- les états locaux non persistés (filtres de tableau, onglet ouvert)
  sont perdus à chaque bascule.

Aucune donnée périmée n'est présentée comme actuelle, mais l'objectif
« immédiat » du cahier des charges **n'est pas atteint**.

## 3. P1 — couverture réelle du bilinguisme

**Traduit** : navigation, pied de page, liens rapides, boutons et
libellés d'accessibilité du layout — donc présents sur toutes les pages —
ainsi que les quatre pages FEBA FHA.

**NON traduit — 12 pages de contenu** : Accueil, À propos, Académique,
Admissions, Vie scolaire, Campus, Galerie, Actualités, Détail actualité,
Contact, Pages légales, 404.

Concrètement : en mode EN, le menu passe bien en anglais, mais le
carrousel affiche toujours « Bienvenue à FEBA » et les sections de la
page d'accueil restent en français. **La plainte d'origine n'est donc que
partiellement levée.**

Le fichier `src/site/i18nCoverage.test.js` fige cette liste : elle ne peut
pas s'allonger sans faire échouer la suite. L'application privée n'est pas
non plus intégralement traduite.

## 4. P2 — la moitié qui manque

**Corrigé (sécurité)** : l'API `/api/website/admin/preregistrations/`
refuse désormais un administrateur d'académie EN LIGNE avec un 403 et un
message renvoyant vers « Admissions FEBA FHA ». Le superadmin conserve
l'accès, l'admin FEBA aussi, et l'admin FHA garde son propre module.
Cinq tests couvrent ces cas.

**NON corrigé (interface)** : l'onglet « Préinscriptions » **reste
visible** dans la page Site vitrine quelle que soit l'académie active.

Le filtrage conditionnel ne fonctionne pas : à l'intérieur du sous-arbre
remonté, `useEntityContext()` ne renvoie pas de façon fiable
`entity_type`, si bien que la condition « académie en ligne » est
toujours fausse. Trois tentatives (filtre simple, attente du chargement
du contexte, squelette) n'ont pas résolu le problème dans cette session.

Atténuation apportée : l'onglet est explicitement libellé
**« Préinscriptions FEBA »** dans tous les contextes, et sa vue n'est plus
rendue pour une académie en ligne. Un administrateur FHA qui cliquerait
dessus verrait une zone vide plutôt qu'une liste trompeuse — mais
l'onglet ne devrait pas être là du tout.

**Piste pour la reprise** : sortir la décision du sous-arbre remonté, par
exemple en calculant les onglets disponibles dans le layout (qui, lui, a
le contexte fiable) et en les passant par contexte React, ou en cessant de
remonter l'Outlet au profit de clés d'académie sur chaque requête.

## 5. Correctif d'environnement

`settings/test_postgres.py` ne définissait aucune origine CORS. Toute
vérification en navigateur avec ce module échouait à la connexion, alors
que l'API répondait correctement en ligne de commande. Les origines de
développement y sont désormais déclarées.

## 6. Non réalisé dans cette itération

- Tests visuels multi-résolutions (320 → 1920 px) et captures avant/après.
- Commandes `audit_academy_data` / `repair_academy_data`.
- Audit de performance (N+1, index sur `academy_id`, pagination).
- Traduction des contenus administrables (titres/descriptions bilingues
  en base) et des documents PDF.
- Rapports détaillés demandés (ACADEMY_SWITCH_REPORT, I18N_COMPLETE_REPORT,
  PERFORMANCE_REPORT…) : seul le présent document et le manifeste sont
  fournis.

## 7. Rappel des limitations antérieures

Inchangées : Zoom n'est pas intégré (l'intégration est Jitsi
auto-hébergé, et aucune réunion à deux participants réels n'a été tenue) ;
les espaces parent, élève et enseignant spécifiques à FHA, la messagerie
cloisonnée et les paiements FHA ne sont pas livrés. Voir
`KNOWN_LIMITATIONS_V5.md`.
