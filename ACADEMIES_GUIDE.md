# Guide — créer et configurer une académie

Réservé au **super administrateur**. Chaque académie est isolée : ses
élèves, parents, enseignants, notes, bulletins, appréciations, paiements,
documents, logos et salles virtuelles ne sont visibles que dans son
périmètre (vérifié par la campagne `tests/test_isolation_2_7_19_academies.py`).

## 1. Créer l'académie

Menu **Académies** → **Nouvelle académie**.

| Type | Créé automatiquement | Barème des bulletins |
|---|---|---|
| Académie en ligne | fonctionnalités en ligne (tests de placement, cours et devoirs en ligne) ; aucun niveau (les groupes dépendent du programme) | selon le cycle de chaque niveau créé |
| Académie physique — primaire | Maternelle 1 et 2, CI, CP, CE1, CE2, CM1, CM2 | sur 10 |
| Académie physique — secondaire | 6ème, 5ème, 4ème, 3ème (collège), Seconde, Première, Terminale (lycée) | sur 20 |

Champs obligatoires : type, **programme linguistique** (§ 1 bis), nom,
**code interne** (définitif : il ne peut plus être modifié), adresse, ville,
pays. Facultatif : première année
scolaire (nom, début, fin — jamais inventée).

Ce qui est installé : les niveaux du type, une **copie** du barème
d'appréciations (propre à l'académie), la matrice des fonctionnalités du
type. Ce qui n'est **jamais** copié d'une autre académie : élèves, parents,
notes, paiements, dossiers d'inscription, salles virtuelles, logo, cachets.

## 1 bis. Programme linguistique

Il est **distinct de la langue de l'interface et des documents**
(`default_language`). Le programme décide des matières, des parcours de classe
et du bulletin. Le serveur l'applique à **toutes** les écritures : matières,
classes, notes saisies une à une ou en masse, créneaux de l'emploi du temps et
séances en ligne.

| Programme | Matières admises | Parcours des classes | Bulletin |
|---|---|---|---|
| Français uniquement | françaises | francophone | section française seule, sans moyenne 60/40 |
| Anglais uniquement | anglaises | anglophone | section anglaise seule |
| Bilingue français-anglais | françaises, anglaises et **communes** | bilingue ; francophone ou anglophone seulement si l'académie autorise les classes monolingues (fonctionnalité `monolingual_classes`, active par défaut pour une académie en ligne) | deux sections ; moyenne bilingue = 60 % FR + 40 % EN, seulement quand les deux existent |

**Matière commune** (catégorie « Commune (bilingue) ») : elle n'est admise que
dans une académie bilingue et dans une classe de parcours bilingue. Elle est
comptée **une seule fois** dans la moyenne générale, avec son coefficient. Elle
n'entre ni dans la moyenne française, ni dans l'anglaise, ni dans le 60/40.
Elle s'imprime dans « Autres matières ».

Les barèmes ne changent pas : le primaire et la maternelle sont notés sur 10,
le collège et le lycée sur 20. La moyenne générale est pondérée par les
coefficients ; une matière sans note n'y entre pas.

**Changer le programme** (« Académies » → modifier) :
1. L'écran affiche le **diagnostic** (`GET /api/schools/schools/<id>/language-diagnostic/?mode=…`) : matières d'une autre langue, classes qui les portent, nombre de notes rattachées.
2. S'il y a conflit, l'enregistrement exige une **confirmation explicite**.
3. Rien n'est supprimé ni converti. Les matières en conflit restent consultables, mais ne reçoivent plus de nouvelles notes ni de nouveaux créneaux tant qu'elles ne sont pas corrigées dans « Paramètres » et « Classes ».
4. Pour un programme monolingue, le parcours **stocké** des classes est aligné sur le parcours appliqué.

Un programme ne peut pas redevenir vide. Le changement est réservé au super
administrateur : l'administrateur d'une académie ne peut pas le modifier.

**Académies antérieures** : la migration `schools.0021` les classe d'après
leurs données, sans rien deviner :
- matières FR **et** EN, ou une matière commune → bilingue ;
- toutes les matières dans une langue, toutes les classes dans le parcours monolingue correspondant, et monolingue permis → cette langue ;
- sinon « À configurer ». Le fonctionnement historique est alors conservé intégralement.

`python manage.py academy_languages_report` (lecture seule) liste les
académies à configurer, avec le motif et une proposition, ainsi que celles qui
ont des données hors programme. `init_academies` complète FEBA et FEBA FHA en
« bilingue » **seulement si leur programme est vide**.

## 2. Terminer la configuration

L'icône « Configuration restante » de chaque ligne liste ce qui manque,
d'après la base : année scolaire active, niveaux, matières, classes,
administrateur, barème valide, logo. Sélectionner l'académie dans le
sélecteur d'académie (en haut de page), puis :

1. **Paramètres** : année scolaire (si non créée), salles, matières ;
2. **Niveaux** : le cycle de chaque niveau fixe le barème (maternelle et
   primaire sur 10, collège et lycée sur 20) ; seuls les cycles admis par
   le type sont proposés (et acceptés par le serveur) ;
3. **Classes** ;
4. **Gestion Admins** : créer l'administrateur de l'académie ;
5. **Branding & Logo** : téléverser et activer le logo. Sans logo,
   l'application affiche le monogramme de l'académie et un favicon à ses
   couleurs ; les documents ne portent aucun logo — jamais celui d'une
   autre académie ;
6. **Appréciations** : vérifier ou adapter le barème ;
7. **Gabarits des documents** : téléverser, placer, vérifier et activer le
   diplôme et le certificat (`DOCUMENT_TEMPLATES_GUIDE.md`).

## 3. Appréciations

Seuil **bas inclusif**, en **pourcentage de la note maximale** : 95 % =
19/20 = 9,5/10. Une note prend l'appréciation du palier actif le plus élevé
qu'elle atteint ; une note exactement sur un seuil prend ce palier. Le
barème est enregistré en entier et refusé s'il est incohérent (seuils en
double, aucun palier à 0 %, libellé vide, seuil hors 0–100 %). Un palier
figurant sur des bulletins émis ne peut pas être supprimé : le désactiver.
Un barème propre à un cycle (ex. « Lycée ») prime sur celui de l'académie.
Les bulletins déjà émis gardent leur appréciation.

## 4. Classer une académie existante

`python manage.py academy_types_report` (lecture seule) indique le type de
chaque académie et, pour une académie non classée, le motif et une
proposition. Le classement (« Académies » → modifier → type) est refusé si
des niveaux le contredisent ; corriger d'abord ces niveaux.

## 5. Désactiver, supprimer

**Désactiver** : les utilisateurs de l'académie ne peuvent plus se
connecter ; rien n'est supprimé. **Supprimer** : uniquement une académie
vide (créée par erreur) ; sinon la suppression est refusée avec la liste
de ce qu'elle contient.

## 6. Vérifications après installation

- `python manage.py migrate --plan` : aucune migration en attente ;
- `python manage.py academy_types_report` ;
- `python manage.py academy_languages_report` ;
- `python manage.py check --deploy` ;
- dans l'application : créer une académie de test, vérifier ses niveaux
  et son barème, la sélectionner, constater qu'aucune donnée d'une autre
  académie n'apparaît, puis la supprimer (elle est vide).

## Limites

- La fiche d'inscription publique en ligne, les tests de placement et les
  rapports mensuels ne concernent que l'académie rattachée au site public
  (`PUBLIC_SITE_ONLINE_ACADEMY_CODE`, par défaut `FEBA_FHA`). Les
  préinscriptions du site ne concernent que `PUBLIC_SITE_CAMPUS_ACADEMY_CODE`
  (par défaut `FEBA`). Les menus et onglets correspondants (« Admissions en
  ligne », « Rapports mensuels », « Préinscriptions du site ») suivent ces
  capacités calculées par le serveur. Une nouvelle académie n'a pas encore de
  formulaire public à son nom.
- Diplômes et certificats : l'académie téléverse ses gabarits officiels
  dans « Gabarits des documents » (`DOCUMENT_TEMPLATES_GUIDE.md`) ; sans
  gabarit actif, la production est refusée — jamais faite au fond d'une
  autre académie.
- Une académie du **groupe FEBA** (nom de groupe dans son identité)
  imprime le numéro institutionnel du groupe ; une académie indépendante
  imprime son propre numéro (`Paramètres`).
