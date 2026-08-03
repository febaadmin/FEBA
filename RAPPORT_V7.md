# Itération V7 — quatre priorités, et ce qu'elles cachaient

Ce rapport décrit ce qui a été corrigé, **pourquoi le défaut existait**, et
comment la correction est vérifiée. Les chiffres cités proviennent des
exécutions réelles reproduites dans `VERIFICATION_V7.md`.

---

## P0 — Le changement d'académie ne mettait pas les données à jour

### Ce qui se passait

Le sélecteur changeait de libellé instantanément, mais les tableaux
mettaient quatre à cinq secondes à suivre — et pouvaient afficher entre
temps les chiffres de l'académie que l'on venait de quitter. L'utilisateur
n'avait aucun moyen de savoir si ce qu'il lisait était à jour.

### Trois causes distinctes, souvent confondues en une seule

**1. Chaque bascule coûtait deux fois le trafic nécessaire.** La séquence
était `clear()` → `invalidateQueries()` → `refetchQueries({type:"active"})`.
Les deux derniers appels relançaient les requêtes des écrans *encore
montés*, juste avant que le changement de clé ne les démonte et que les
nouveaux écrans ne relancent exactement les mêmes requêtes. Le remontage
suffisait ; on ne relance plus rien à la main.

**2. Les réponses tardives réécrivaient le cache.** Une requête partie
avant la bascule aboutissait après, et repeuplait le cache avec les données
de l'ancienne académie. Vider le cache ne servait donc à rien : il était
immédiatement re-rempli. Chaque requête reçoit désormais un
`AbortController` enregistré dans `frontend/src/api/academyScope.js` ;
changer d'académie avorte tout ce qui est en vol.

**3. Le cache survivait au remontage.** Les écrans remontés lisaient les
entrées encore fraîches (`staleTime` de 30 s) et affichaient l'ancienne
académie avant même la première requête. Le cache métier est maintenant
purgé *avant* le remontage.

### Le filet de sécurité

Chaque réponse API annonce la portée qui a servi à la calculer, dans
l'en-tête `X-Academy-Scope` (middleware `apps/core/academy_scope.py`). Le
client jette toute réponse dont la portée ne correspond plus à l'écran.

L'en-tête envoyé par le **navigateur** n'a aucune autorité : la portée
effective reste résolue par `get_request_school()`. Trois tests le
vérifient explicitement, dont la tentative d'évasion la plus évidente —
prétendre être en mode « Toutes les Académies ».

### Un défaut introduit par cette correction, puis corrigé

Le contrôle de portée rejetait **la bascule elle-même**. Le serveur
enregistrait le changement et répondait 200, mais sa réponse annonçait la
*nouvelle* académie — forcément différente de celle que le client avait au
moment de l'envoi. Elle était donc traitée comme périmée : `onSuccess` ne
s'exécutait jamais et le sélecteur restait figé.

Ce défaut ne se voyait dans aucun test unitaire : l'API répondait
correctement. Il a été trouvé en rejouant le parcours dans un vrai
navigateur. Les endpoints de contexte sont maintenant exemptés du
contrôle — ce sont eux qui *établissent* la portée, ils ne peuvent pas
être vérifiés contre elle-même.

### Résultat mesuré

| | Avant | Après |
|---|---|---|
| Délai de bascule | 4 à 5 s | **299 à 310 ms** |
| Rechargement de page | parfois nécessaire | aucun |
| Réponses servies sous une portée périmée | possible | **0 sur 487 réponses observées** |

---

## P1 — Le sélecteur FR/EN ne traduisait qu'une partie du site

### Ce qui se passait

Le sélecteur était visible partout, mais seule la page FEBA FHA changeait
réellement de langue. Le carrousel, « Bienvenue à FEBA », les sections de
la page d'accueil et les formulaires restaient en français. Une traduction
partielle est plus déroutante qu'une absence de traduction : le visiteur
voyait un menu anglais au-dessus d'un contenu français, dans la même page.

### Trois natures de texte, trois traitements

**Les libellés du code** (douze pages restantes, plus les messages de
validation des formulaires — ce sont eux que l'utilisateur lit au pire
moment).

**Le contenu structurel** — niveaux, valeurs, activités, atouts — devient
une table de couples `{ fr, en }` au lieu de chaînes françaises.

**Le contenu administré** posait un problème d'une autre nature : le
carrousel, les albums et les actualités viennent de la base, aucun
mécanisme frontend ne pouvait les traduire. Or le carrousel est la
première chose que voit un visiteur. Les modèles `HeroSlide`, `NewsPost`,
`GalleryAlbum`, `GalleryItem` et `SiteSettings` reçoivent donc des champs
`_en` **facultatifs**. Le repli est délibéré : une traduction vide renvoie
le français plutôt qu'un blanc. Traduire reste un choix éditorial, pas une
obligation technique.

### Application privée

266 libellés n'avaient pas de traduction anglaise : dans le même tableau,
« Groupe » côtoyait « Subject ». Tous sont traduits, et un test parcourt
le code source pour vérifier que **chaque** chaîne passée à `t()` possède
une entrée anglaise. C'est la seule façon d'empêcher le problème de
réapparaître écran par écran.

### Corrigé au passage

`<html lang>` n'était mis à jour que lors d'un changement de langue. Après
rechargement, une page anglaise était annoncée `lang="fr"` : les lecteurs
d'écran la prononçaient avec la phonétique française et les moteurs de
recherche l'indexaient comme française.

### Résultat mesuré

Treize pages publiques parcourues dans un navigateur après un clic sur
« EN » : **zéro mot français résiduel**. Les cinq profils de l'application
privée (super administrateur, administrateur, enseignant, parent, élève),
**32 vues** : zéro libellé français résiduel.

---

## P2 — Le mode consolidé n'identifiait pas les données, et mentait sur les totaux

### Identifier

Neuf serializers ne disaient pas à quelle académie leur objet appartenait.
En vue consolidée, deux élèves homonymes de deux académies étaient
indiscernables — et rien n'empêchait de modifier le mauvais.

Un champ `academy_short_name` est ajouté : « FEBA French Heritage
Academy » ne tient pas dans une colonne, et tronqué il devenait « FEBA
Fren… », donc confondable avec « FEBA ».

La colonne « Académie » est ajoutée dans `DataTable` plutôt que dans chaque
écran : une trentaine de tableaux passent par ce composant, les annoter un
par un aurait garanti d'en oublier. Les deux écrans qui n'utilisent pas
`DataTable` (Niveaux, Notes) sont traités séparément.

Les exports CSV portent la même colonne : hors de l'application, rien ne
rappelle quelle académie était affichée au moment du clic.

### Totaliser

Deux défauts rendaient le total consolidé faux — et rien à l'écran ne le
signalait, les chiffres étaient simplement inexacts.

**Côté serveur**, le filtre « année courante » s'écrivait partout
`filter(school=school, is_current=True).first()`. En mode consolidé
`school` vaut `None` : le filtre retournait `None` et était *silencieusement
abandonné*. La vue remontait alors tout l'historique — 270 paiements
« toutes académies » pour 90 à FEBA et 0 à FEBA FHA.

**Côté interface**, une dizaine d'écrans choisissaient leur filtre par
défaut avec `years.find(y => y.is_current)`. Cette liste contient l'année
courante de *chaque* académie : `find()` en retenait une, et l'écran
filtrait dessus. 30 élèves s'affichaient au lieu de 33. C'est exactement
l'interdit « ne jamais ne renvoyer qu'une seule académie en mode
consolidé », et il était d'autant plus trompeur que les données étaient
correctes côté serveur.

Les puces d'année portent désormais le nom de leur académie : sans cela,
deux boutons « 2025-2026 » étaient indiscernables.

### Résultat mesuré

Seize endpoints sur dix-sept satisfont « total consolidé = somme des
académies ». Les deux écarts restants sont justes et expliqués :

- le **Super Administrateur** n'appartient à aucune académie (rôle
  plateforme) — il apparaît avec le badge « Sans académie » plutôt que
  d'être masqué ;
- les **salles virtuelles** sont refusées à une académie présentielle
  (403), le total consolidé vaut donc celui de la seule académie en ligne.

Douze écrans vérifiés en navigateur portent le badge d'académie sur chaque
ligne, et les deux académies apparaissent bien dans la même liste.

---

## P3 — Les emplois du temps des deux académies étaient confondus

### Pourquoi un seul modèle ne pouvait pas suffire

Une page et un modèle uniques servaient les deux académies. On ne savait
donc jamais quel emploi du temps on regardait, ni dans lequel on créait un
créneau — alors que les deux ne planifient pas la même chose.

**FEBA** planifie un cours présentiel : classe, salle physique, heure
locale de Cotonou. La contrainte forte y est l'occupation des salles.

**FEBA FHA** planifie une séance en direct : groupe en ligne, salle
virtuelle, participants répartis entre les États-Unis, le Canada et le
Bénin. Il n'y a pas de salle à réserver, mais l'heure doit être stockée en
UTC — « 17 h » ne désigne pas le même instant selon le fuseau, et l'écart
change deux fois par an — et un rappel doit partir avant la séance.

Les forcer dans une table unique obligeait à laisser vides la moitié des
colonnes et rendait impossible toute contrainte utile : une salle physique
n'a aucun sens pour un cours en ligne, un fuseau d'affichage aucun sens
pour un cours à Akpakpa.

### Ce qui a été fait

Un second modèle, `OnlineSessionSchedule`, et un second endpoint,
`/api/schedule/online-sessions/`. L'interface expose deux onglets nommés
en toutes lettres, jamais distingués par une simple couleur.

Le **jour local** est calculé et affiché quand il diffère du jour UTC : une
séance à 00 h 30 UTC le mardi a lieu le lundi soir sur la côte est, et
afficher « mardi » à ces familles serait faux.

**Aucun lien Jitsi permanent** n'est publié dans l'emploi du temps :
rejoindre exige un jeton signé, lié à l'utilisateur et valable quinze
minutes. Un lien fixe serait utilisable par quiconque le recopie.

### Relations inter-académies

Les deux modèles refusent qu'un créneau relie des objets d'académies
différentes — une classe FEBA avec une matière FHA, par exemple. La
vérification est dans `clean()`, appelée depuis `save()` : elle tient donc
pour l'API, l'admin Django, un import ou un shell, pas seulement pour le
serializer. C'est le croisement le plus insidieux : il ne se voit pas à
l'écran mais fausse tout ce qui en découle des mois plus tard.

La **création est refusée** en mode consolidé : choisir une académie
implicite reviendrait à en tirer une au hasard. `make seed-check` ajoute
quatre contrôles de croisement.

### Résultat mesuré

CRUD complet testé des deux côtés, y compris les tentatives croisées :
un administrateur FEBA ne peut ni lire, ni modifier, ni supprimer une
séance FEBA FHA, et réciproquement. L'académie d'une séance existante ne
peut pas être déplacée.

---

## Hors priorités : la suite SQLite ne démarrait plus

Huit migrations multi-tenant sont écrites en SQL PostgreSQL brut — choix
délibéré, elles devaient être rejouables sur des bases modifiées à la main.
Effet de bord : la base de test SQLite ne se créait plus, et la suite
entière échouait au `migrate` avec **529 erreurs** sans rapport avec le
code testé. Un développeur sans PostgreSQL local ne pouvait plus lancer un
seul test.

`portable_schema_change()` exprime chaque changement deux fois : le SQL
brut sur PostgreSQL, l'équivalent Django ailleurs. Un seul chemin
s'exécute. Les bases PostgreSQL existantes ne voient aucun changement, ces
migrations y étant déjà appliquées — vérifié par une migration complète
sur une base neuve, puis rejouée.

La suite SQLite passe désormais : **561 tests**, un seul ignoré (un test de
concurrence multi-threads qui nécessite un vrai serveur de base de
données, et qui s'exécute sur PostgreSQL).

---

## Récapitulatif des vérifications

| Vérification | Résultat |
|---|---|
| Backend PostgreSQL | 562 tests |
| Backend SQLite | 561 tests, 1 ignoré (concurrence) |
| Frontend (Vitest) | 98 tests |
| ESLint | 0 erreur |
| Build de production | OK |
| E2E — académies | 41 points |
| E2E — espaces en anglais | 5 profils, 32 vues |
| E2E — site public en anglais | 13 pages |
| `make seed` rejoué | comptes identiques |
| `make seed-check` | 20 contrôles |

Les sorties brutes sont dans `VERIFICATION_V7.md`.
