from celery import shared_task
import logging
logger = logging.getLogger("apps")


@shared_task(name="bulletins.run_operation", ignore_result=True)
def run_bulletin_operation(operation_id):
    """Exécute une opération groupée sur les bulletins (commentaire ou génération)."""
    from apps.bulletins.models import BulletinOperation
    from apps.bulletins.operations import run_operation
    from django.utils import timezone
    # Prise atomique : deux livraisons du même message n'exécutent pas
    # deux fois l'opération.
    claimed = BulletinOperation.objects.filter(pk=operation_id, status="queued").update(
        status="running", started_at=timezone.now())
    op = BulletinOperation.objects.select_related("school", "created_by").filter(
        pk=operation_id).first() if claimed else None
    if op is None:
        # Déjà prise par un autre worker, ou inexistante : rien à faire.
        logger.warning("Opération bulletins %s introuvable ou déjà traitée", operation_id)
        return
    run_operation(op)


@shared_task
def generate_bulletin_task(student_id, period, school_year_id):
    from apps.bulletins.pdf_generator import generate_bulletin
    try:
        from apps.students.models import Student
        from apps.schools.models import SchoolYear
        student = Student.objects.get(pk=student_id)
        school_year = SchoolYear.objects.get(pk=school_year_id)
        generate_bulletin(student, period, school_year)
        logger.info(f"Bulletin generated for {student} - {period}")
    except Exception as e:
        logger.error(f"Bulletin generation error: {e}")
