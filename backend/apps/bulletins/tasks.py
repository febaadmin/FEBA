from celery import shared_task
import logging
logger = logging.getLogger("apps")

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