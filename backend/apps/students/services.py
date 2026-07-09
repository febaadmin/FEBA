"""
apps/students/services.py

Logique métier du "passage en classe supérieure" / assistant de fin
d'année. Centralisée ici pour que les différents endpoints (anciens et
nouveaux) partagent une seule implémentation testée, et pour que
chaque opération soit systématiquement vérifiée comme appartenant au
bon établissement (tenant) — point critique en environnement
multi-tenant : un identifiant d'élève, de classe ou d'année scolaire
ne doit JAMAIS être utilisable pour agir sur les données d'un autre
établissement, même par erreur de l'interface.
"""
from django.db import transaction
from django.utils import timezone

from .models import Student, StudentEnrollment


def get_or_create_enrollment(student, school_year_id, class_obj_id=None, promotion_status='normal', note=''):
    """
    Crée (ou réactive) l'inscription annuelle d'un élève pour une année
    donnée. Ne supprime jamais d'inscription existante : si une
    inscription existe déjà pour cette année, elle est mise à jour
    plutôt que dupliquée (contrainte unique_together le garantirait de
    toute façon, mais on évite ainsi une IntegrityError évitable).

    Utilisée comme point d'entrée UNIQUE pour rattacher une donnée
    métier (note, absence, bulletin, devoir, paiement...) à l'année
    scolaire d'un élève — c'est le cœur de la refonte "années
    scolaires" : plus aucun module ne doit créer un couple
    (élève, année) sans passer par une StudentEnrollment.
    """
    enrollment, created = StudentEnrollment.objects.get_or_create(
        student=student,
        school_year_id=school_year_id,
        defaults={
            'class_obj_id': class_obj_id,
            'promotion_status': promotion_status,
            'is_active': True,
            'note': note,
        },
    )
    if not created and class_obj_id and not enrollment.class_obj_id:
        enrollment.class_obj_id = class_obj_id
        enrollment.save(update_fields=['class_obj'])
    return enrollment, created


# Alias rétro-compatible (nom interne utilisé par les premières versions
# de ce module avant son exposition aux autres apps).
_get_or_create_enrollment = get_or_create_enrollment


def set_enrollment(student, school_year_id, class_obj_id=None, promotion_status='normal', note=''):
    """
    Upsert EXPLICITE d'une inscription annuelle — contrairement à
    `get_or_create_enrollment` (qui ne fait que garantir l'existence
    d'un lien sans toucher à une inscription déjà présente), celle-ci
    EST destinée à modifier le statut de promotion/la classe/la note
    d'une inscription existante. Réservée aux actions de décision de
    fin d'année (promotion, redoublement, départ...).
    """
    enrollment, created = StudentEnrollment.objects.get_or_create(
        student=student,
        school_year_id=school_year_id,
        defaults={
            'class_obj_id': class_obj_id,
            'promotion_status': promotion_status,
            'is_active': True,
            'note': note,
        },
    )
    if not created:
        enrollment.is_active = True
        if class_obj_id:
            enrollment.class_obj_id = class_obj_id
        enrollment.promotion_status = promotion_status
        if note:
            enrollment.note = note
        enrollment.save()
    return enrollment, created


@transaction.atomic
def bulk_promote_students(school, target_year_id, scope, source_year_id=None,
                           source_class_id=None, target_class_id=None,
                           student_ids=None, promotion_status='normal'):
    """
    Promotion en masse, tenant-safe.

    scope='year'     : tous les élèves actifs de `source_year_id` → `target_year_id`
    scope='class'     : tous les élèves actifs de `source_class_id` → `target_year_id`
    scope='students'  : liste explicite `student_ids` → `target_year_id`

    Chaque élève traité DOIT appartenir à `school` ; tout élève d'un
    autre établissement (ou inexistant) est rapporté dans `failed` au
    lieu d'être silencieusement ignoré ou — pire — traité.
    """
    if school is None:
        return {'enrolled': 0, 'skipped': 0, 'failed': [{'error': "Établissement (tenant) introuvable pour cette requête."}]}

    base_qs = Student.objects.filter(school=school, is_active=True)

    if scope == 'year':
        enrolled_ids = set(
            StudentEnrollment.objects.filter(
                school_year_id=source_year_id, is_active=True, student__school=school,
            ).values_list('student_id', flat=True)
        )
        direct_ids = set(
            base_qs.filter(school_year_id=source_year_id).values_list('id', flat=True)
        )
        students = base_qs.filter(id__in=(enrolled_ids | direct_ids))
    elif scope == 'class':
        # FIX v33 (cause racine du "0 élève inscrit") : une classe appartient
        # à une année. Filtrer sur current_class_id (pointeur "classe actuelle")
        # ne trouvait personne dès que les élèves avaient déjà été promus
        # ailleurs. On récupère les élèves via l'HISTORIQUE des inscriptions
        # dans cette classe, avec repli sur le pointeur.
        enrolled_in_class = set(
            StudentEnrollment.objects.filter(
                class_obj_id=source_class_id, student__school=school,
            ).values_list('student_id', flat=True)
        )
        pointer_ids = set(
            base_qs.filter(current_class_id=source_class_id).values_list('id', flat=True)
        )
        students = base_qs.filter(id__in=(enrolled_in_class | pointer_ids))
    elif scope == 'students':
        students = base_qs.filter(id__in=(student_ids or []))
    else:
        return {'enrolled': 0, 'skipped': 0, 'failed': [{'error': f"scope invalide: {scope}"}]}

    requested_count = len(student_ids) if scope == 'students' else None

    enrolled, skipped, failed = 0, 0, []
    matched_ids = set()
    for student in students:
        matched_ids.add(student.id)
        if StudentEnrollment.objects.filter(student=student, school_year_id=target_year_id).exists() and scope != 'students':
            skipped += 1
            continue
        try:
            set_enrollment(
                student, target_year_id,
                class_obj_id=target_class_id,
                promotion_status=promotion_status,
            )
            student.school_year_id = target_year_id
            update_fields = ['school_year']
            if target_class_id:
                student.current_class_id = target_class_id
                update_fields.append('current_class')
            student.save(update_fields=update_fields)
            enrolled += 1
        except Exception as e:
            failed.append({'student_id': student.id, 'error': str(e)})

    # scope='students' : signaler explicitement les IDs demandés mais
    # non trouvés dans le tenant courant (sécurité + clarté pour l'UI),
    # plutôt que de les ignorer silencieusement.
    if scope == 'students':
        for sid in (student_ids or []):
            if int(sid) not in matched_ids:
                failed.append({'student_id': sid, 'error': "Introuvable dans cet établissement."})

    return {'enrolled': enrolled, 'skipped': skipped, 'failed': failed}


@transaction.atomic
def apply_end_of_year_decision(school, target_year_id, decision):
    """
    Applique UNE décision de fin d'année pour UN élève.
    `decision` = {"student_id": int, "action": str, ...}
    action ∈ {"promote", "honor", "repeat", "transfer", "depart", "exclude", "graduate"}
    """
    student_id = decision.get('student_id')
    action = decision.get('action')

    if school is None:
        return {'student_id': student_id, 'ok': False, 'error': "Établissement introuvable."}

    student = Student.objects.filter(school=school, id=student_id).first()
    if student is None:
        return {'student_id': student_id, 'ok': False, 'error': "Élève introuvable dans cet établissement."}

    try:
        if action in ('promote', 'honor', 'repeat', 'transfer'):
            status_map = {'promote': 'normal', 'honor': 'honor', 'repeat': 'repeat', 'transfer': 'transfer'}
            class_id = decision.get('class_id')
            set_enrollment(
                student, target_year_id,
                class_obj_id=class_id,
                promotion_status=status_map[action],
                note=decision.get('note', ''),
            )
            student.school_year_id = target_year_id
            update_fields = ['school_year']
            if class_id:
                student.current_class_id = class_id
                update_fields.append('current_class')
            student.save(update_fields=update_fields)

        elif action in ('depart', 'exclude', 'graduate'):
            reason_map = {
                'depart': 'withdrawn',
                'exclude': 'excluded',
                'graduate': 'graduated',
            }
            promo_map = {
                'depart': 'withdrawn',
                'exclude': 'excluded',
                'graduate': 'graduated',
            }
            student.is_active = False
            student.exit_reason = reason_map[action]
            student.exit_date = decision.get('exit_date') or timezone.now().date()
            student.exit_notes = decision.get('reason', '')
            student.save(update_fields=['is_active', 'exit_reason', 'exit_date', 'exit_notes'])
            # On enregistre la décision dans l'historique via une
            # inscription "fermée" (is_active=False) pour que cette
            # année-là apparaisse bien dans l'historique de l'élève.
            StudentEnrollment.objects.update_or_create(
                student=student, school_year_id=target_year_id,
                defaults={'promotion_status': promo_map[action], 'is_active': False,
                          'note': decision.get('reason', '')},
            )
        else:
            return {'student_id': student_id, 'ok': False, 'error': f"action invalide: {action}"}

        return {'student_id': student_id, 'ok': True, 'action': action}
    except Exception as e:
        return {'student_id': student_id, 'ok': False, 'error': str(e)}
