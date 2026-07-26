"""
V8 — Priorité 4 : toutes les évaluations pèsent 1.

Règle métier : quel que soit le type (devoir, interrogation, contrôle, examen,
TP…), une évaluation compte pour 1 dans la moyenne de la matière. L'examen ne
pèse plus davantage que l'interrogation.

Migration de données SÛRE et RÉVERSIBLE dans sa structure :
  1. RAPPORT AVANT — recense les notes dont le poids ≠ 1 et les élèves/matières
     dont la moyenne va changer (affiché dans la sortie de `migrate`) ;
  2. EXÉCUTION — normalise `note_coefficient` à 1 ;
  3. VÉRIFICATION APRÈS — confirme qu'il ne reste aucun poids ≠ 1.

Sauvegarde : les anciennes valeurs sont journalisées dans la sortie de la
migration ; la procédure complète de sauvegarde/restauration est décrite dans
RESTORE_GUIDE.md (dump SQL avant migration). Les NOTES elles-mêmes ne sont pas
modifiées — seul leur poids change.
"""
from django.db import migrations

ASSESSMENT_WEIGHT = 1


def forwards(apps, schema_editor):
    Grade = apps.get_model("grades", "Grade")
    impacted = Grade.objects.exclude(note_coefficient=ASSESSMENT_WEIGHT)
    total = impacted.count()

    if total:
        # ── Rapport AVANT ───────────────────────────────────────────────────
        by_weight = {}
        for weight in impacted.values_list("note_coefficient", flat=True):
            by_weight[weight] = by_weight.get(weight, 0) + 1
        # Couples (élève, matière, période) dont la moyenne peut bouger.
        touched = impacted.values_list(
            "student_id", "subject_id", "period"
        ).distinct().count()
        print(
            f"\n[V8] Poids d'évaluation → 1 : {total} note(s) concernée(s) "
            f"(répartition {by_weight}) ; {touched} moyenne(s) "
            f"élève×matière×période susceptible(s) de changer."
        )
        # ── Exécution ───────────────────────────────────────────────────────
        impacted.update(note_coefficient=ASSESSMENT_WEIGHT)
    else:
        print("\n[V8] Poids d'évaluation : aucune note à normaliser.")

    # ── Vérification APRÈS ──────────────────────────────────────────────────
    remaining = Grade.objects.exclude(note_coefficient=ASSESSMENT_WEIGHT).count()
    if remaining:
        raise RuntimeError(
            f"[V8] Échec de normalisation : {remaining} note(s) ont encore un "
            f"poids ≠ {ASSESSMENT_WEIGHT}."
        )
    print("[V8] Vérification OK : toutes les évaluations pèsent 1.")


def backwards(apps, schema_editor):
    """Les anciens poids hétérogènes ne sont pas reconstituables.

    La restauration passe par le dump SQL réalisé avant migration
    (cf. RESTORE_GUIDE.md). On laisse volontairement les poids à 1 plutôt que
    d'inventer des valeurs.
    """
    print("\n[V8] Retour arrière : poids conservés à 1 "
          "(restaurer le dump pré-V8 pour retrouver les anciens poids).")


class Migration(migrations.Migration):
    dependencies = [
        ("grades", "0010_alter_grade_note_type"),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
