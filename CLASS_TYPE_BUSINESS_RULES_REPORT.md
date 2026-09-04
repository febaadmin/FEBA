# FEBA — Règles métier des types de classe

Source de vérité : `backend/apps/classes/subject_rules.py`.
Reflet navigateur : `frontend/src/utils/classLanguage.js`.

---

## 1. La règle, en une phrase

Une classe n'accepte que les matières des langues de son parcours, et
doit avoir au moins une matière dans **chacune** de ces langues.

| Parcours | Langues admises | Langues obligatoires |
|---|---|---|
| `BILINGUAL` | `fr`, `en` | `fr` **et** `en` |
| `FRANCOPHONE` | `fr` | `fr` |
| `ANGLOPHONE` | `en` | `en` |

Admises et obligatoires sont **identiques** : un parcours monolingue est
strict. Une classe francophone n'accepte pas de matière anglaise — sans
quoi une matière glissée par erreur ressort ensuite dans le bulletin,
dans les moyennes et dans l'emploi du temps, sans que rien ne l'ait
jamais annoncée.

---

## 2. La décision dépend de DEUX choses

Le parcours déclaré de la classe ne suffit pas.

**Faith & Excellence Bilingual Academy est bilingue par construction.**
C'est son identité, pas un réglage. FEBA French Heritage Academy accueille
au contraire des enfants de la diaspora dont certains ne suivent que le
français ou que l'anglais.

L'autorisation des parcours monolingues est donc portée par l'**académie**,
via le drapeau `monolingual_classes` de la matrice de fonctionnalités
(`School.FEATURE_FLAGS`), déjà vérifiée côté serveur :

| Type d'entité | `monolingual_classes` | Effet |
|---|---|---|
| `campus` (FEBA) | `False` | parcours effectif toujours `BILINGUAL` |
| `online` (FEBA FHA) | `True` | le parcours déclaré gouverne |

Conséquence : **une donnée corrompue ou un `language_track` posté ne peut
pas transformer une classe de FEBA en classe monolingue.** La
non-régression de FEBA est structurelle, pas promise.

### « Inconnue » n'est pas « interdit »

`allows_monolingual(None)` renvoie `False` — on n'affirme jamais qu'un
parcours monolingue est autorisé sans preuve. Mais `forbids_monolingual`
n'est **pas** sa négation : elle n'est vraie que si l'académie est
**connue** et l'interdit.

Confondre les deux avait un coût réel : forcer `BILINGUAL` dès que
l'académie n'était pas résolvable faisait réapparaître, sur le bulletin
d'une classe francophone, la partie anglaise vide et la moyenne bilingue
pondérée par une langue absente.

Le renversement ne coûte aucune protection : `school_year` puis `school`
sont des clés étrangères non nulles, donc toute classe **enregistrée** a
une académie. Le cas « inconnue » ne se rencontre que sur un objet non
sauvegardé, hors de portée d'un attaquant.

---

## 3. Une seule implémentation

| Couche | Rôle |
|---|---|
| `subject_rules.py` | **décide** |
| `Class` (modèle) | **délègue** — ne réimplémente rien |
| `ClassViewSet.manage_subjects` | applique, répond 400 |
| `ClassSerializer._set_subjects` | applique, répond 400 |
| `ClassSerializer` (lecture) | expose `effective_language_track`, `allowed_languages`, `monolingual_allowed` |
| `classLanguage.js` | **reflète** ce que l'API a renvoyé |
| `Classes.jsx` | affichage **et** soumission appellent la même fonction |

Une seconde implémentation, même fidèle le jour où on l'écrit, finit par
diverger. C'est exactement ainsi qu'un écran a pu afficher « Configuration
complète » et refuser l'enregistrement dans le même souffle.

---

## 4. Les trois familles de refus

Dans l'ordre où on les lit :

1. **matière d'une autre académie** — « Ces matières n'appartiennent pas
   à {académie} : … » ;
2. **langue hors parcours** — « Cette classe n'enseigne pas la matière
   anglaise {nom}. » ;
3. **langue attendue absente** — « Sélectionnez au moins une matière
   française. »

Chaque message **nomme** les matières fautives : un message qui ne dit
pas quoi décocher oblige à chercher.

---

## 5. Ce que le navigateur fait, et ne fait pas

`classLanguage.js` **ne protège rien** : l'autorité est le backend, qui
refuse en 400. Son rôle est de ne pas laisser l'utilisateur composer une
configuration que le serveur rejettera.

D'où la préférence donnée aux champs renvoyés par l'API
(`effective_language_track`, `allowed_languages`) : le navigateur
**reflète** la décision plutôt que de la recalculer. Le repli sur la
table locale ne sert qu'aux réponses d'API antérieures.

---

## 6. Interface (§6)

| État | Ce que l'utilisateur voit |
|---|---|
| Colonne hors parcours | grisée, cases désactivées, phrase d'explication |
| Configuration monolingue valide | « Configuration complète — 4 matière(s) française(s) ✓ » |
| Configuration bilingue valide | « Configuration bilingue complète — 4 FR / 3 EN ✓ » |
| Configuration invalide | les motifs exacts, ceux-là mêmes que le serveur renverrait |

Le résumé **nomme** ce qui est configuré. « Configuration complète » tout
court ne disait rien, et ce vide rendait la contradiction avec le message
d'erreur d'autant plus déroutante.

---

## 7. Migration des classes existantes (§5)

`classes.0004_audit_language_tracks` lit les matières **déjà assignées**,
qui sont un fait, et n'en tire une conclusion que si elle est univoque :

| Constat | Conclusion |
|---|---|
| uniquement des matières `fr` | `FRANCOPHONE` |
| uniquement des matières `en` | `ANGLOPHONE` |
| les deux langues | `BILINGUAL` (inchangé) |
| **aucune matière** | **inchangé**, et signalé dans le rapport |

Le dernier cas est le seul ambigu — et c'est précisément celui où il ne
faut rien décider. La classe garde la valeur par défaut et apparaît dans
la sortie de migration, pour qu'un administrateur tranche depuis l'écran
Classes.

Les académies qui n'autorisent pas le monolingue ne sont **jamais**
touchées. La migration est réversible.

Résultat mesuré sur la base de développement :

```
FEBA_FHA   French Ambassadors   → ANGLOPHONE   (matières : en)
FEBA_FHA   Junior Roots         → FRANCOPHONE  (matières : fr)
FEBA_FHA   French Explorers     → BILINGUAL    (matières : en, fr)
FEBA       (17 classes)         → inchangées, toutes BILINGUAL
```
