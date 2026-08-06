# SCHEDULE_PARITY_REPORT.md — P2, juillet-août 2026

## Ce que les captures montraient

FEBA (`CampusSchedule.jsx`) : bascule Grille/Liste, filtre par classe,
grille visuelle riche. FEBA FHA (`OnlineSchedule.jsx`) : un tableau simple,
sans bascule de vue.

## Ce que l'audit réel a trouvé — pas ce qu'on pourrait supposer

Comparer les deux fichiers ligne à ligne a montré que l'écart n'était PAS
principalement esthétique. Trois différences réelles, listées par gravité :

### 1. Détection de conflit incomplète côté FEBA FHA (le vrai « CRUD partiel »)

`ClassScheduleSerializer` (FEBA) empêche trois conflits : classe,
enseignant, salle. `OnlineSessionScheduleSerializer` (FEBA FHA)
n'empêchait que l'enseignant :

```python
# AVANT — seul l'enseignant était vérifié
teacher = field("teacher")
if teacher and start is not None and day is not None:
    ...
```

Un groupe pouvait donc se voir planifier deux séances qui se chevauchent,
et une salle virtuelle être réservée deux fois en même temps — le genre de
bug qui ne se voit pas sur une capture d'écran, mais qui EST le « CRUD
partiel » que la demande décrit.

**Corrigé** : ajout de la détection de conflit groupe et salle virtuelle,
même structure que côté FEBA (`backend/apps/schedule/serializers.py`).

### 2. Erreurs silencieuses côté FEBA (dans l'autre sens que prévu)

```javascript
// AVANT — CampusSchedule.jsx
const updateMut = useMutation({ mutationFn: ..., onSuccess: ... });  // pas de onError !
const deleteMut = useMutation({ mutationFn: ..., onSuccess: ... });  // pas de onError !
const createMut = useMutation({ ..., onError: (e) => toast.error(t("Erreur serveur")) });  // message générique
```

Modifier ou supprimer un créneau FEBA qui échouait côté serveur (conflit,
permission) ne montrait **rien du tout** à l'utilisateur. `OnlineSchedule.jsx`
affichait déjà le détail réel renvoyé par le serveur — c'est FEBA qui
était en retard sur ce point, pas FEBA FHA.

**Corrigé** : les trois mutations de `CampusSchedule.jsx` extraient
maintenant le message réel renvoyé par le serveur (même fonction `failure()`
qu'`OnlineSchedule.jsx` utilisait déjà).

### 3. Absence de bascule Grille/Liste côté FEBA FHA

Bien réelle, celle-là. **Corrigée** : `OnlineSchedule.jsx` a maintenant la
même bascule Grille/Liste que `CampusSchedule.jsx`, avec une grille dont
les colonnes sont les jours (7 colonnes au lieu de 6 côté FEBA — FEBA FHA
planifie aussi le week-end, différence dictée par le métier, pas par un
oubli) et les lignes les créneaux horaires UTC (l'heure locale du fuseau
choisi reste visible dans chaque case).

## Ce qui n'a PAS été corrigé, et pourquoi

La demande liste aussi, dans les « Contrôles métier » : *« une matière non
affectée à la classe ; un enseignant non affecté à la matière »*. Le
modèle de données le permet (`Class.subjects`, `Teacher.subjects`, deux
relations many-to-many déjà présentes) — mais **aucune commande de seed ne
les peuple jamais**. Vérifié directement :

```bash
$ grep -rn "\.subjects\.set\|\.subjects\.add" apps/*/management/commands/seed_demo_data.py
# aucun résultat
```

Activer cette validation aurait fait échouer TOUTE création de créneau sur
les données de démonstration, pour les deux académies — remplacer un bug
rapporté par une régression généralisée. Je ne l'ai pas fait. C'est un
gap réel, à traiter dans une session dédiée qui commence par peupler le
seed.

## Tests (32 tests concernés, tous verts contre PostgreSQL réel)

Nouveaux (7, `tests/test_online_schedule_conflicts.py`) :

| Test | Vérifie |
|---|---|
| `test_meme_groupe_meme_creneau_est_refuse` | conflit de groupe (nouveau) |
| `test_meme_enseignant_meme_creneau_est_refuse` | conflit d'enseignant (déjà présent) |
| `test_meme_salle_virtuelle_meme_creneau_est_refusee` | conflit de salle (nouveau) |
| `test_creneaux_qui_ne_se_chevauchent_pas_sont_acceptes` | pas de faux positif |
| `test_jour_different_meme_heure_est_accepte` | l'axe jour est respecté |
| `test_modifier_une_seance_sans_la_comparer_a_elle_meme` | édition normale non bloquée |
| `test_seance_inactive_ne_bloque_pas_un_nouveau_creneau` | désactivation libère le chevauchement |

Préexistants (25, `tests/test_schedule_separation.py`) : isolation
FEBA/FEBA FHA, symétrie de base du CRUD, fuseaux horaires — tous
confirmés toujours verts après ce correctif.

## Détail technique : pourquoi deux tests utilisent un horaire décalé de 30 min

Le modèle a déjà une contrainte d'unicité `(group, day_of_week,
start_time_utc)` en base — elle bloquait déjà les doublons EXACTS, avant
ce correctif. Écrire les tests avec un horaire identique aurait donc
« réussi » sans jamais exercer le nouveau code de détection de
CHEVAUCHEMENT (17h00–18h00 qui chevauche 17h30–18h30, sans être identique).
Corrigé pour tester le bon mécanisme.

## Frontend — vérification

```
npm run lint    → 0 erreur (fichiers modifiés)
npm run build   → succès
```
