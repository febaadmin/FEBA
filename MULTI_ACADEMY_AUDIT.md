# FEBA — Audit de la portée académique (V10)

§6 et §44 : ne pas réparer quatre menus déroulants séparément, mais
chercher si l'abstraction de portée est cassée.

---

## 1. La bonne question

Le défaut signalé n'était pas « le menu Classe est vide ». C'était :

> un écran filtre sur `is_current=True` en supposant qu'une académie a
> toujours une année active, et **rend zéro résultat** quand ce n'est pas
> le cas.

« Classes assignées » et le menu d'une salle virtuelle tombaient ensemble
parce qu'ils appellent le **même endpoint** (`classesAPI.list()`). Deux
symptômes, une cause.

La question posée à l'application entière est donc : **existe-t-il encore
un endpoint qui rende zéro là où il y a des données ?**

---

## 2. Ce que l'audit a trouvé

Deux formes de filtrage cohabitent dans le code.

### Forme A — l'abstraction, qui est saine

`apps/core/tenancy.current_school_years(school)` renvoie un **queryset**,
et les appelants le gardent derrière `if annees.exists()` :

```python
annees = current_school_years(school)
if annees.exists():
    qs = qs.filter(school_year__in=annees)
```

Sans année active, aucun filtre n'est appliqué : ces écrans montrent
**trop**, jamais **rien**. C'est une dégradation acceptable et
volontaire, documentée dans le module.

Endpoints concernés (vérifiés) : présences, devoirs, annonces, paiements,
notes, élèves, tableau de bord, rapports mensuels, documents.

### Forme B — le contournement, qui était le défaut

Un seul endroit filtrait directement un queryset :

```python
qs = qs.filter(school_year__is_current=True)   # apps/classes/views.py
```

Aucun garde. Une académie sans année active tombait à zéro classe.

**C'était le seul.** Recherche exhaustive de `school_year__is_current`
dans `apps/` : une seule occurrence, désormais remplacée par
`scope_to_active_year(qs, school)`.

---

## 3. Le test qui empêche la récidive

`AuditDeLaPorteeAcademiqueTests` pose la question à **toutes les listes
d'un coup**, sur une académie sans année activée — l'état réel de
FEBA FHA :

| Endpoint | Données présentes |
|---|---|
| `/api/classes/` | 3 classes |
| `/api/subjects/` | matières |
| `/api/students/` | élèves |
| `/api/teachers/` | enseignants |
| `/api/schools/levels/` | niveaux |
| `/api/schools/years/` | années scolaires |

Le test échoue en **nommant l'endpoint fautif**, pas en constatant qu'un
menu est vide :

```
listes vides alors que l'académie a ces données — le filtre
« année active » retombe à zéro :
  /api/classes/ (classes)
```

Trois autres tests l'encadrent :

- un garde-fou qui vérifie que la fixture reproduit **bien** l'état sans
  année active — sans lui, tout le reste passerait pour de mauvaises
  raisons ;
- **§37** : FEBA voit toujours ses listes ;
- **le cloisonnement** : montrer plus ne doit jamais vouloir dire montrer
  l'autre académie. Le repli élargit ce qu'on voit **dans** son académie,
  il n'ouvre aucune brèche.

En remettant le filtre d'origine, 2 tests tombent.

---

## 4. Réparation à la source

L'audit corrige le symptôme. L'invariant, lui, est réparé là où il naît :

| Niveau | Mécanisme |
|---|---|
| Écriture | `SchoolYear.save()` active la première année d'une académie — **à la création uniquement** |
| Données | migration `schools.0016` répare les académies déjà orphelines |
| Lecture | `academic_year.active_year()` se replie sur l'année la plus récente |

La garde `_state.adding` est essentielle : sans elle, une année
enregistrée à `is_current=False` était aussitôt réactivée, et le bouton
« Clôturer » ne clôturait plus rien. Une académie dont toutes les années
sont closes n'est **pas** rattrapée à l'écriture — le repli de lecture
prend le relais, sans jamais rouvrir ce qu'un administrateur a fermé.

`has_explicit_active_year()` permet de **signaler** l'anomalie plutôt que
de la corriger en douce : un repli silencieux qui dure devient une
seconde vérité.

---

## 5. Ce qui n'était pas un défaut de portée

« Salles physiques de l'école (0) ». `Room` n'a aucun lien avec l'année
scolaire ; `RoomViewSet` filtre sur `school`, un point c'est tout.
FEBA FHA affichait « 0 » parce qu'elle n'avait **réellement** aucune salle.

La correction est dans les données de démonstration, pas dans le
filtrage. Modifier la requête pour faire apparaître un chiffre aurait
affiché les salles de FEBA dans les paramètres de FEBA FHA.

`SallesPhysiquesTests` fixe les deux affirmations : le cloisonnement est
correct, et une salle créée est bien comptée.

---

## 6. Le cache frontend n'était pas en cause

`AcademyContext` fait déjà, à chaque bascule d'académie :

```js
queryClient.cancelQueries();
setAcademyScope(nextScope);
queryClient.removeQueries({ … });
```

et `AcademyScopedOutlet` ne monte aucun écran métier avant que la portée
ne soit posée. Les 33 fichiers à clés de requête simples n'ont donc **pas**
été modifiés : le défaut était côté backend, et le prouver a évité une
réécriture massive sans objet.

**Une exception a été trouvée** — et corrigée : la nouvelle route de
conférence vit à la racine du routeur et échappait à ce garde. Voir
`JITSI_AUDIT_REPORT.md` §6.

---

## 7. Cloisonnement — vérifications

| Vérification | Statut |
|---|---|
| Les classes ne fuient pas d'une académie à l'autre | **PASS VÉRIFIÉ** |
| Un admin FHA ne voit pas les salles physiques de FEBA | **PASS VÉRIFIÉ** |
| Affecter une classe d'une autre académie à un enseignant → 400 | **PASS VÉRIFIÉ** |
| Rejoindre une salle d'une autre académie → 403 | **PASS VÉRIFIÉ** |
| Une académie sans visio activée → 403 | **PASS VÉRIFIÉ** |
| FEBA : 10 classes au menu, 30 avec `?all_years=1` | **PASS VÉRIFIÉ** |
