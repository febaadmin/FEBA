# PROFILE_CREATION_REPORT.md — Création des profils (V8-P1/P2, 26/07/2026)

## 1. Reproduction du bug (Priorité 1)

Scénario exact : Super administrateur → `/superadmin/teachers` → « Nouvel
enseignant » → compte utilisateur `teacher`, spécialité, date d'embauche,
contrat, 2 classes, 2 matières → **Enregistrer**.

### Payload envoyé (relevé réel)

```json
{
  "user_write": 4,
  "specialization": "test",
  "hire_date": "2026-07-26",
  "contract_type": "permanent",
  "class_ids": [10, 20],
  "subject_ids": [1, 2],
  "bio": ""
}
```

Le payload est **correct** : identifiants entiers, date ISO, contrat valide,
listes d'identifiants (et non d'objets). Le problème était ailleurs.

### Traceback relevé (avant correction)

```
django.db.utils.IntegrityError: UNIQUE constraint failed: teachers_teacher.employee_id
```

État de la base au moment de l'erreur : `count = 4`, matricules
`ENS-2026-0002 … ENS-2026-0005`.

## 2. Cause racine

`Teacher.save()` générait le matricule ainsi :

```python
count = Teacher.objects.count() + 1
self.employee_id = f"ENS-{timezone.now().year}-{count:04d}"
```

`count()` **n'est pas une séquence**. Dès qu'un enseignant est supprimé (ou que
deux créations s'entrecroisent), le compteur retombe sur un matricule **déjà
attribué** → violation de la contrainte `unique=True` → **erreur 500**, profil
non créé. Avec 4 enseignants et un maximum à `0005`, le code générait `0005`.

C'est un bug **latent** : il ne se déclenche qu'après une suppression, ce qui
explique qu'il soit apparu en production et pas sur une base neuve.

## 3. Correctifs

| Correctif | Détail |
|---|---|
| Matricule fiable | Généré à partir du **plus grand suffixe réellement utilisé** (`max + 1`), avec reprise automatique (10 tentatives) en cas de collision concurrente. |
| Création atomique | `transaction.atomic()` : profil **et** relations (matières, classes) enregistrés ensemble, ou rien. Aucune donnée partielle après échec. |
| Compte obligatoire | `user_write` requis à la création → **400 explicite** au lieu d'un 500 (violation `NOT NULL` sur `user_id`). |
| Erreurs exploitables | `IntegrityError` traduite en message métier ; **aucun traceback** exposé à l'utilisateur. |

### Réponse après correction (même état de collision)

```
STATUS = 201
employee_id  = "ENS-2026-0006"        (max+1, et non count+1)
subjects     = [Mathématiques, Français]
classes      = [3ème-A, 3ème-A]
```

## 4. Faille de sécurité découverte pendant l'audit (P2)

Le cloisonnement multi-établissement des matières et classes était
**silencieusement inopérant** :

```python
self.fields["subject_ids"].queryset = Subject.objects.filter(school=school)
```

Pour un `PrimaryKeyRelatedField(many=True)`, DRF enveloppe le champ dans un
`ManyRelatedField` : la validation lit `child_relation.queryset`, jamais le
`queryset` de l'enveloppe. Un administrateur pouvait donc rattacher à un
enseignant des **matières et classes d'un AUTRE établissement**.

Corrigé (`child_relation.queryset`) + test dédié.

## 5. Codes de retour

| Situation | Code | Message |
|---|---|---|
| Donnée invalide (date, contrat, classe introuvable) | `400` | champ concerné |
| Profil déjà existant pour ce compte | `400` | « Un profil enseignant existe déjà… » |
| Matière/classe d'un autre établissement | `400` | `subject_ids` / `class_ids` |
| Compte utilisateur absent | `400` | « Sélectionnez le compte utilisateur… » |
| Rôle non autorisé (parent, anonyme) | `403` / `401` | permission |

## 6. Audit des autres profils (Priorité 2)

`tests/test_profile_creation.py` — **16 cas** :

- **Enseignant** : régression matricule après suppression ; 10 créations avec
  suppressions intercalées (aucun doublon) ; relations enregistrées ;
  modification (matricule conservé, relations mises à jour) ; doublon refusé ;
  compte manquant ; date invalide ; contrat invalide ; matière d'un autre
  établissement ; classe introuvable ; **atomicité** (aucune donnée partielle) ;
  permissions (parent 403, anonyme 401).
- **Élève** : création OK ; **matricule unique après suppression** (même
  classe de bug vérifiée — non reproduite).
- **Parent** : création sans erreur 500.

Toutes les erreurs de validation renvoient un **400 exploitable** ; aucune
n'aboutit à un 500.

## 7. Preuves

- Reproduction et correction exécutées sur la base de développement réelle
  (traceback ci-dessus, puis `201`).
- 16 tests automatisés ; suite backend complète : **383 tests**.
- Parcours navigateur (super administrateur) : voir `FINAL_REPORT.md`.
