# FEBA FHA — Validation des classes : anomalies, causes, corrections

Format §45. Statuts §46.

---

## BUG-V11-001 — Contradiction entre l'affichage et l'enregistrement

| | |
|---|---|
| **Priorité** | P0 |
| **Gravité** | Bloquant — la fonctionnalité est inutilisable |
| **Statut** | **CORRIGÉ ET VÉRIFIÉ** |

**Symptôme.** Une classe francophone de FEBA FHA affiche « Configuration
complète ✓ — 4 matière(s) FR », puis refuse l'enregistrement avec
« Sélectionnez au moins une matière anglaise. »

**Reproduction.** FEBA FHA → Classes → Junior Roots → Matières → cocher
les 4 matières françaises → « Enregistrer les matières ».

**Cause racine.** Les deux phrases venaient du **même composant**. Le
bandeau de résumé lisait `subjectModal.language_track` ; la garde de
soumission `onSaveSubjects`, vingt lignes plus haut, appliquait encore
« une matière française **et** une anglaise », écrite en dur :

```js
if (frSelected.length === 0) { toast.error("… matière française."); return; }
if (enSelected.length === 0) { toast.error("… matière anglaise."); return; }
```

Le lot précédent avait corrigé l'affichage sans toucher à cette garde :
exactement la moitié du travail.

**Fichiers.** `frontend/src/pages/admin/Classes.jsx`,
`frontend/src/utils/classLanguage.js` (créé).

**Correction.** L'affichage et la soumission appellent la même fonction,
`validateSelection`. Ils ne peuvent plus diverger sans que ce fichier
change.

**Migration.** Aucune.

**Tests.** `classLanguage.test.js` — cas A à H, 20 tests.

**Résultat.** 11/11 en navigateur réel sur le scénario exact de la
capture, persistance après rechargement complet incluse.

---

## BUG-V11-002 — Le backend ne validait rien

| | |
|---|---|
| **Priorité** | P0 |
| **Gravité** | Critique |
| **Statut** | **CORRIGÉ ET VÉRIFIÉ** |

**Symptôme.** Aucun, visible. C'est ce qui le rend grave.

**Reproduction.** `POST /api/classes/{id}/subjects/` avec
`{"subject_ids": [<n'importe quoi>]}` → 200, matières assignées.

**Cause racine.** Les **deux** chemins d'écriture faisaient :

```python
Subject.objects.filter(id__in=subject_ids)
```

Sans validation métier et sans restriction d'académie. La seule règle qui
existait vivait dans le navigateur, là où elle ne protège rien.

Autrement dit : le frontend sur-validait, le backend ne validait pas.

**Fichiers.** `apps/classes/views.py` (`manage_subjects`),
`apps/classes/serializers.py` (`_set_subjects`),
`apps/classes/subject_rules.py` (créé).

**Correction.** Les deux chemins passent par
`validate_subject_configuration` et répondent 400. Création et
modification sont désormais atomiques : une liste refusée ne laisse plus
derrière elle une classe créée et vide.

**Tests.** `test_v11_class_language_rules.py` — 16 tests.

---

## BUG-V11-003 — Matières inter-académies assignables

| | |
|---|---|
| **Priorité** | P0 |
| **Gravité** | Critique — cloisonnement multi-académies |
| **Statut** | **CORRIGÉ ET VÉRIFIÉ** |

**Symptôme.** Un administrateur de FEBA FHA pouvait assigner une matière
appartenant à FEBA, en postant son identifiant.

**Reproduction.** `POST /api/classes/{id_fha}/subjects/` avec l'identifiant
d'une matière FEBA → 200 avant correction.

**Cause racine.** Le `filter(id__in=...)` n'était borné par aucune
académie, sur les deux chemins d'écriture.

**Correction.** `validate_subject_configuration` refuse toute matière dont
`school_id` diffère de celui de la classe, et l'écarte de la suite du
raisonnement : sa langue n'a pas à décider du parcours.

**Tests.** `CloisonnementDesMatieresTests` — les deux chemins.

---

## BUG-V11-004 — Bulletin d'une classe monolingue

| | |
|---|---|
| **Priorité** | P1 |
| **Gravité** | Majeur — document officiel remis aux familles |
| **Statut** | **CORRIGÉ ET VÉRIFIÉ** |

**Symptôme.** Le bulletin d'une classe francophone imprimait une section
anglaise vide, une « Moyenne Anglaise » à « — » et une moyenne bilingue
pondérée par une langue absente.

**Cause racine.** Traitée en V10 pour l'essentiel ; réapparue quand
`effective_track` forçait `BILINGUAL` sur toute classe dont l'académie
n'était pas résolvable.

**Correction.** `forbids_monolingual` ne répond vrai que sur une académie
**connue** (voir `CLASS_TYPE_BUSINESS_RULES_REPORT.md` §2).

**Tests.** `test_bulletin_language_track.py`.

**Résultat mesuré** sur trois PDF réellement générés et inspectés :

| Bulletin | Occurrences interdites |
|---|---|
| FRANCOPHONE (Junior Roots) | **0** |
| ANGLOPHONE (French Ambassadors) | **0** |
| BILINGUE (French Explorers) | les deux sections, les trois moyennes, la formule |

---

## BUG-V11-005 — Refus « introuvable » au lieu d'expliqué

| | |
|---|---|
| **Priorité** | P1 |
| **Gravité** | Majeur — code de protection mort |
| **Statut** | **CORRIGÉ ET VÉRIFIÉ** |

**Symptôme.** Un élève visant la salle virtuelle d'une autre classe
recevait 404 « ressource introuvable » sur une salle qui existe.

**Cause racine.** `join` passait par `get_object()`, donc par le queryset
**filtré par rôle**. Les messages de `assert_can_join` écrits pour ce cas
(« Vous n'êtes pas inscrit dans le groupe de cette salle ») étaient
**inatteignables** depuis ce chemin : du code mort décrivant une
protection qu'aucun utilisateur ne rencontrait.

**Correction.** `_salle_a_rejoindre()` résout la salle dans le périmètre
de l'**académie**. Deux frontières, deux réponses : l'académie reste
opaque (404, l'existence n'est pas révélée) ; à l'intérieur, le refus est
expliqué (403 avec le motif).

**Tests.** `RefusExpliqueDansLAcademieTests` ; parcours navigateur par
rôle, 17/17.

---

## BUG-V11-006 — Contrôles de santé aveugles à deux pannes

| | |
|---|---|
| **Priorité** | P2 |
| **Gravité** | Moyen — diagnostic trompeur |
| **Statut** | **CORRIGÉ ET VÉRIFIÉ** |

**Symptôme.** `make jitsi-health` annonçait « opérationnel » alors que
`external_api.js` n'était pas servi, ou que le proxy n'avait aucune règle
pour `/xmpp-websocket`.

**Correction.** Deux sondes ajoutées, dérivant leur URL de la même base
que le contrôle principal — les coder sur le domaine public aurait refait
la régression P7 (`JITSI_INTERNAL_URL`). Seul un 404 est traité comme une
absence de règle : 400, 426 et 501 sont des réponses normales à un GET
sans en-têtes de mise à niveau.

**Tests.** `test_v11_jitsi_health_checks.py`.

**Résultat mesuré** contre `meet.globalfeba.com` : les deux contrôles
sont **OK**.

---

## BUG-V11-007 — `jitsi_health` pouvait lever

| | |
|---|---|
| **Priorité** | P2 |
| **Statut** | **CORRIGÉ ET VÉRIFIÉ** |

**Symptôme.** La fonction promet « ne lève JAMAIS » — c'est sa raison
d'être, elle alimente la page qui sert à diagnostiquer une panne. Le bloc
TLS ne rattrapait que `SSLCertVerificationError` et `OSError` : toute
autre exception faisait tomber l'écran de diagnostic au moment précis où
l'on en a besoin.

**Correction.** Rattrapage explicite, avec le motif reporté dans le
contrôle plutôt qu'avalé.

---

## BUG-V11-008 — Route `/join/` supprimée (introduit puis corrigé)

| | |
|---|---|
| **Priorité** | P0 |
| **Statut** | **CORRIGÉ ET VÉRIFIÉ** |

**Symptôme.** `POST /api/virtual-rooms/{id}/join/` → 404 HTML.

**Cause racine.** Le helper `_salle_a_rejoindre` avait été inséré **entre**
le décorateur `@action` et la méthode `join` : le décorateur s'est
appliqué au helper, et la route est devenue `/_salle_a_rejoindre/`.

Deux tests passaient alors **pour une mauvaise raison** — ils attendaient
un 404 et recevaient celui de l'URL absente. Ce sont les parcours
navigateur qui l'ont révélé.

**Correction.** Décorateur remis sur `join`. Vérifié par inspection des
routes résolues, pas seulement par le retour au vert.

---

## Cas de non-régression exigés (§37)

| Cas | Académie | Parcours | FR | EN | Attendu | Résultat |
|---|---|---|---|---|---|---|
| A | FHA | FRANCOPHONE | 4 | 0 | VALIDE | **PASS VÉRIFIÉ** |
| B | FHA | FRANCOPHONE | 0 | 0 | INVALIDE (FR requise) | **PASS VÉRIFIÉ** |
| C | FHA | ANGLOPHONE | 0 | 3 | VALIDE | **PASS VÉRIFIÉ** |
| D | FHA | ANGLOPHONE | 0 | 0 | INVALIDE (EN requise) | **PASS VÉRIFIÉ** |
| E | FHA | BILINGUE | ≥1 | ≥1 | VALIDE | **PASS VÉRIFIÉ** |
| F | FHA | BILINGUE | ≥1 | 0 | INVALIDE | **PASS VÉRIFIÉ** |
| G | FHA | BILINGUE | 0 | ≥1 | INVALIDE | **PASS VÉRIFIÉ** |
| H | FEBA | — | — | — | comportement historique | **PASS VÉRIFIÉ** |

Chaque cas est vérifié **deux fois** : sur l'API (autorité) et sur le
helper navigateur (reflet).
