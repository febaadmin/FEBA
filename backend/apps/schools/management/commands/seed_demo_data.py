"""
Seeder de données de démonstration — FEBA v31.

Génère un établissement complet et immédiatement exploitable :
  - 3 années scolaires (N-2, N-1, N courante) calculées dynamiquement
  - Niveaux, classes (une par niveau et par année), matières FR + EN
  - Comptes : superadmin, admins, enseignants, parents, élèves
  - Élèves avec HISTORIQUE RÉALISTE : inscription N-2 → N-1 → N avec
    progression de niveau (CM1 → CM2 → 6ème...), redoublements inclus
  - Notes (3 années, liées aux inscriptions annuelles)
  - Absences / retards / justifiées (3 années)
  - Paiements (inscription + mensualités, 3 années)
  - Bulletins T1/T2 avec moyennes calculées depuis les vraies notes
  - Emplois du temps (année courante) avec salles
  - Salles physiques, devoirs, annonces, notifications, salles virtuelles

Idempotent : ré-exécuter la commande ne duplique pas les données.

Usage :
    python manage.py seed_demo_data
"""
import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.grades.grading import ASSESSMENT_WEIGHT
from apps.schools.institution import official_phone

FM = ["Koffi", "Emeka", "Jean", "Pierre", "Marc", "David", "Samuel", "Éric", "Paul", "Hervé",
      "Ayo", "Sègun", "Kwame", "Malik", "Idriss"]
FF = ["Marie", "Sarah", "Amina", "Rosine", "Chantal", "Grace", "Fatou", "Aïcha", "Josiane",
      "Estelle", "Bintou", "Mariama", "Reine", "Nadège", "Sylvie"]
LN = ["Agossou", "Dossou", "Zinsou", "Loko", "Acakpo", "Hounsou", "Kpossou", "Tokpanou",
      "Adjou", "Gbaguidi", "Ahouansou", "Codjo", "Dansou", "Mensah", "Ajayi"]


def rgrade(lo, hi):
    return Decimal(str(round(random.uniform(lo, hi), 2)))


class Command(BaseCommand):
    help = "Génère un jeu complet de données de démonstration (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help=(
                "Supprime les données de démonstration avant de les regénérer. "
                "REFUSÉ si DEBUG=False (garde-fou production)."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)  # données reproductibles

        # Garde-fou : « seed-reset » ne doit jamais tourner en production.
        if options.get("reset"):
            from django.conf import settings as dj_settings
            if not dj_settings.DEBUG:
                raise CommandError(
                    "« --reset » est refusé hors développement (DEBUG=False). "
                    "Il supprimerait des données réelles."
                )
            self._reset_demo_data()

        from apps.accounts.models import CustomUser
        from apps.announcements.models import Announcement
        from apps.attendance.models import Attendance
        from apps.bulletins.models import Bulletin
        from apps.classes.models import Class
        from apps.grades.models import Grade
        from apps.homework.models import Homework
        from apps.notifications.models import Notification
        from apps.parents.models import Parent, ParentStudent
        from apps.payments.models import Payment
        from apps.schedule.models import ClassSchedule
        from apps.schools.models import School, SchoolYear, Level, Room
        from apps.students.models import Student, StudentEnrollment
        from apps.subjects.models import Subject
        from apps.teachers.models import Teacher
        from apps.virtualclass.models import VirtualRoom

        self.stdout.write(self.style.MIGRATE_HEADING("Seed démonstration FEBA v31"))

        # ── ÉTABLISSEMENT ────────────────────────────────────────────────
        # V5 : identification par le CODE INTERNE STABLE, jamais par le nom.
        # Rechercher par nom créait un second établissement dès que
        # l'administration renommait l'académie.
        school, _ = School.objects.get_or_create(
            code=School.CODE_FEBA,
            defaults={
                "name": "Faith & Excellence Bilingual Academy",
                "legal_name": "Faith & Excellence Bilingual Academy",
                "slug": "feba",
                "entity_type": "campus",
                "address": "Rue des Cocotiers, Akpakpa",
                "city": "Cotonou", "country": "Bénin",
                "phone": official_phone(), "email": "contact@feba.bj",
                "timezone": "Africa/Porto-Novo",
                "currency_code": "XOF",
                "default_language": "fr",
                "matricule_prefix": "FEBA",  # matricules FEBA-26-0001
            },
        )
        if not school.matricule_prefix:
            school.matricule_prefix = "FEBA"
            school.save(update_fields=["matricule_prefix"])
        self.stdout.write("  ✅ Établissement")

        # ── 3 ANNÉES SCOLAIRES (dynamiques : N-2, N-1, N) ────────────────
        today = timezone.now().date()
        start_year = today.year if today.month >= 9 else today.year - 1
        # FIX v39 : purge de tout drapeau actif AVANT création (respecte la
        # contrainte « une seule année active » même sur base pré-remplie).
        SchoolYear.objects.filter(school=school, is_current=True).update(is_current=False)
        years = []
        for offset in (-2, -1, 0):
            y0 = start_year + offset
            sy, _ = SchoolYear.objects.get_or_create(
                school=school, name=f"{y0}-{y0 + 1}",
                defaults={
                    "start_date": datetime.date(y0, 10, 1),
                    "end_date": datetime.date(y0 + 1, 7, 31),
                    "is_current": False,
                },
            )
            years.append(sy)
        year_n2, year_n1, year_curr = years
        # Une seule active : l'année courante
        year_curr.is_current = True
        year_curr.save(update_fields=["is_current"])
        self.stdout.write(f"  ✅ Années scolaires : {year_n2.name}, {year_n1.name}, {year_curr.name} (active)")

        # ── NIVEAUX (chaîne de progression) ──────────────────────────────
        LEVEL_CHAIN = [
            ("CP1", "primaire"), ("CP2", "primaire"),
            ("CE1", "primaire"), ("CE2", "primaire"),
            ("CM1", "primaire"), ("CM2", "primaire"),
            ("6ème", "college"), ("5ème", "college"),
            ("4ème", "college"), ("3ème", "college"),
        ]
        levels = {}
        for order, (name, cycle) in enumerate(LEVEL_CHAIN):
            lvl, _ = Level.objects.get_or_create(
                school=school, name=name, defaults={"order": order, "cycle": cycle},
            )
            levels[name] = lvl
        level_names = [n for n, _ in LEVEL_CHAIN]
        self.stdout.write(f"  ✅ {len(levels)} niveaux")

        # ── MATIÈRES (FR + EN) ───────────────────────────────────────────
        fr_defs = [
            ("Mathématiques", "MATH", 4), ("Français", "FR", 4),
            ("Sciences", "SCI", 3), ("Histoire-Géo", "HG", 2),
            ("Éducation Civique", "EC", 1), ("Sport", "EPS", 1),
        ]
        en_defs = [
            ("English", "ENG", 4), ("Mathematics", "MATH_EN", 3),
            ("Science", "SCI_EN", 2), ("Social Studies", "SS", 2),
        ]
        subjects = {}
        for i, (name, code, coeff) in enumerate(fr_defs):
            s, _ = Subject.objects.get_or_create(
                school=school, code=code,
                defaults={"name": name, "coefficient": coeff, "language": "fr", "order": i},
            )
            subjects[code] = s
        for i, (name, code, coeff) in enumerate(en_defs):
            s, _ = Subject.objects.get_or_create(
                school=school, code=code,
                defaults={"name": name, "coefficient": coeff, "language": "en", "order": 10 + i},
            )
            subjects[code] = s
        all_codes = [c for _, c, _ in fr_defs] + [c for _, c, _ in en_defs]
        self.stdout.write(f"  ✅ {len(subjects)} matières (FR + EN)")

        # ── SALLES PHYSIQUES ─────────────────────────────────────────────
        room_defs = [
            ("Salle 101", "classroom"), ("Salle 102", "classroom"),
            ("Salle 103", "classroom"), ("Salle 104", "classroom"),
            ("Salle informatique", "computer"), ("Bibliothèque", "library"),
        ]
        for rname, rtype in room_defs:
            Room.objects.get_or_create(school=school, name=rname, defaults={"room_type": rtype})
        self.stdout.write(f"  ✅ {len(room_defs)} salles physiques")

        # ── CLASSES : une "-A" par niveau, pour CHAQUE année ─────────────
        classes = {}  # (year.id, level_name) -> Class
        for sy in years:
            for lname in level_names:
                cls, _ = Class.objects.get_or_create(
                    name=f"{lname}-A", school_year=sy,
                    defaults={"level": levels[lname], "max_students": 30},
                )
                if not cls.subjects.exists():
                    cls.subjects.set([subjects[c] for c in all_codes])
                classes[(sy.id, lname)] = cls
        self.stdout.write(f"  ✅ {len(level_names)} classes × {len(years)} années")

        # ── COMPTES ──────────────────────────────────────────────────────
        def create_user(email, pwd, role, first, last):
            u = CustomUser.objects.filter(email=email).first()
            if u:
                return u
            u = CustomUser(email=email, username=email.split("@")[0],
                           first_name=first, last_name=last, role=role,
                           school=None if role == "superadmin" else school)
            u.set_password(pwd)
            u.save()
            return u

        create_user("superadmin@feba.bj", "SuperAdmin@2024", "superadmin", "Super", "Admin")
        admin_user = create_user("admin@feba.bj", "Admin@2024", "admin", "Admin", "FEBA")
        create_user("directeur@feba.bj", "Admin@2024", "admin", "Directeur", "FEBA")
        self.stdout.write("  ✅ SuperAdmin & Admins")

        # ── ENSEIGNANTS ──────────────────────────────────────────────────
        teacher_defs = [
            ("prof.math@feba.bj",     "Mathématiques", "Koffi",  "Agossou", ["MATH", "MATH_EN"]),
            ("prof.francais@feba.bj", "Français",      "Marie",  "Dossou",  ["FR", "HG"]),
            ("prof.sciences@feba.bj", "Sciences",      "Pierre", "Zinsou",  ["SCI", "SCI_EN"]),
            ("prof.anglais@feba.bj",  "Anglais",       "Sarah",  "Loko",    ["ENG", "SS"]),
            ("prof.eps@feba.bj",      "Sport",         "Jean",   "Acakpo",  ["EPS", "EC"]),
        ]
        teachers = []
        for email, spec, first, last, subj_codes in teacher_defs:
            u = create_user(email, "Teacher@2024", "teacher", first, last)
            t, _ = Teacher.objects.get_or_create(
                user=u, defaults={"specialization": spec, "hire_date": datetime.date(2020, 10, 1)},
            )
            t.subjects.set([subjects[c] for c in subj_codes])
            teachers.append(t)
        # Chaque enseignant couvre toutes les classes de l'année courante
        curr_classes = [classes[(year_curr.id, ln)] for ln in level_names]
        for t in teachers:
            t.classes.set(curr_classes)
        self.stdout.write(f"  ✅ {len(teachers)} enseignants")

        # ── ÉLÈVES + HISTORIQUE RÉALISTE SUR 3 ANS ───────────────────────
        # Classes "vitrines" (index dans la chaîne ≥ 2 → 2 ans d'historique
        # avec progression de niveau ; un redoublant simulé par classe).
        demo_levels = ["CE1", "CM1", "CM2", "6ème", "3ème"]
        already_seeded = Student.objects.filter(school=school, user__email__startswith="eleve").exists()
        student_list = list(Student.objects.filter(school=school)) if already_seeded else []

        if not already_seeded:
            idx = 1
            for lname in demo_levels:
                chain_i = level_names.index(lname)
                for k in range(6):
                    gender = random.choice(["M", "F"])
                    first = random.choice(FM if gender == "M" else FF)
                    last = random.choice(LN)
                    u = create_user(f"eleve{idx}@feba.bj", "Student@2024", "student", first, last)
                    dob = datetime.date(random.randint(2008, 2016), random.randint(1, 12), random.randint(1, 28))

                    cls_now = classes[(year_curr.id, lname)]
                    student = Student.objects.create(
                        user=u, school=school,
                        first_name=first, last_name=last, gender=gender,
                        date_of_birth=dob,
                        current_class=cls_now, school_year=year_curr,
                    )

                    is_repeater = (k == 5)  # le 6e élève de chaque classe redouble
                    if is_repeater:
                        # Redoublement : N-1 dans le même niveau, N-2 au niveau inférieur
                        path = [
                            (year_n2, level_names[chain_i - 1], "normal"),
                            (year_n1, lname, "normal"),
                            (year_curr, lname, "repeat"),
                        ]
                    else:
                        path = [
                            (year_n2, level_names[chain_i - 2], "new"),
                            (year_n1, level_names[chain_i - 1], "normal"),
                            (year_curr, lname, "normal"),
                        ]

                    for sy, path_level, status in path:
                        enr = StudentEnrollment.objects.create(
                            student=student, school_year=sy,
                            class_obj=classes[(sy.id, path_level)],
                            promotion_status=status,
                        )
                        # Backdater la date d'inscription (auto_now_add contourné via update)
                        StudentEnrollment.objects.filter(pk=enr.pk).update(
                            enrolled_at=sy.start_date,
                        )
                    student_list.append(student)
                    idx += 1
            self.stdout.write(f"  ✅ {len(student_list)} élèves — historique 3 années avec progression réelle")
        else:
            self.stdout.write("  ↷ Élèves déjà présents — section ignorée (idempotence)")

        enrollments = {
            (e.student_id, e.school_year_id): e
            for e in StudentEnrollment.objects.filter(student__school=school)
        }

        # ── PARENTS ──────────────────────────────────────────────────────
        if not Parent.objects.filter(user__school=school).exists() and student_list:
            rels = ["father", "mother", "guardian"]
            for i in range(0, min(len(student_list), 20), 2):
                first = random.choice(FF if i % 4 else FM)
                last = student_list[i].last_name  # même nom que l'enfant
                u = create_user(f"parent{i // 2 + 1}@feba.bj", "Parent@2024", "parent", first, last)
                p, _ = Parent.objects.get_or_create(user=u, defaults={"profession": random.choice(
                    ["Commerçant(e)", "Enseignant(e)", "Infirmier(ère)", "Chauffeur", "Couturière"])})
                children = student_list[i:i + 2]
                for c in children:
                    ParentStudent.objects.get_or_create(
                        parent=p, student=c,
                        defaults={"relationship": random.choice(rels), "is_primary_contact": True},
                    )
            self.stdout.write("  ✅ Parents liés aux élèves (2 enfants/parent)")

        # ── NOTES (3 années, liées aux inscriptions) ─────────────────────
        if not Grade.objects.filter(school_year=year_curr).exists():
            fr_t = teachers[0]
            en_t = teachers[3]
            for student in student_list:
                for sy, periods in [(year_n2, ["T1", "T2", "T3"]),
                                    (year_n1, ["T1", "T2", "T3"]),
                                    (year_curr, ["T1", "T2"])]:
                    enr = enrollments.get((student.id, sy.id))
                    cls = enr.class_obj if enr else None
                    if not cls:
                        continue
                    for period in periods:
                        for subj in cls.subjects.all():
                            Grade.objects.create(
                                student=student, subject=subj,
                                school_year=sy, enrollment=enr, period=period,
                                teacher=fr_t if subj.language == "fr" else en_t,
                                value=rgrade(7, 18.5),
                                note_type=random.choice(["devoir", "interrogation", "controle"]),
                                # V8 : toutes les évaluations pèsent 1. Le seed
                                # tirait auparavant au sort 1 ou 2, ce qui
                                # réintroduisait d'anciens poids à chaque
                                # nouvelle installation de démonstration.
                                note_coefficient=ASSESSMENT_WEIGHT,
                                graded_at=sy.start_date + datetime.timedelta(days=60 * (["T1", "T2", "T3"].index(period) + 1)),
                            )
            self.stdout.write("  ✅ Notes : 3 années, toutes matières, liées aux inscriptions")

        # ── ABSENCES / RETARDS ───────────────────────────────────────────
        if not Attendance.objects.filter(school_year=year_curr).exists():
            statuses = ["absent", "late", "excused", "absent", "late"]
            for student in student_list:
                for sy, n in [(year_n1, 4), (year_curr, 6)]:
                    enr = enrollments.get((student.id, sy.id))
                    for j in range(random.randint(1, n)):
                        Attendance.objects.create(
                            student=student, school_year=sy, enrollment=enr,
                            date=sy.start_date + datetime.timedelta(days=random.randint(10, 200)),
                            status=random.choice(statuses),
                            created_by=admin_user,
                        )
            self.stdout.write("  ✅ Absences / retards / justifiées (2 années)")

        # ── PAIEMENTS (inscription + mensualités, 3 années) ──────────────
        if not Payment.objects.filter(school_year=year_curr).exists():
            for student in student_list:
                for sy in years:
                    enr = enrollments.get((student.id, sy.id))
                    if not enr:
                        continue
                    Payment.objects.create(
                        student=student, school_year=sy, enrollment=enr,
                        payment_type="inscription", amount=Decimal("25000"),
                        payment_method="cash", received_by=admin_user,
                        payment_date=sy.start_date,
                        notes="Frais d'inscription",
                    )
                    for m in range(2):
                        Payment.objects.create(
                            student=student, school_year=sy, enrollment=enr,
                            payment_type="mensualite", amount=Decimal("35000"),
                            payment_method=random.choice(["cash", "mtn_momo", "moov_money"]),
                            received_by=admin_user,
                            payment_date=sy.start_date + datetime.timedelta(days=30 * (m + 1)),
                            notes=f"Mensualité {m + 1}",
                        )
            self.stdout.write("  ✅ Paiements : inscription + mensualités × 3 années")

        # ── BULLETINS (moyennes issues du MOTEUR CENTRAL de calcul) ────────
        if not Bulletin.objects.filter(school_year=year_curr).exists():
            for student in student_list:
                for sy, periods in [(year_n1, ["T1", "T2", "T3"]), (year_curr, ["T1"])]:
                    enr = enrollments.get((student.id, sy.id))
                    for period in periods:
                        # FIX v32 : même logique que les bulletins PDF et les
                        # tableaux de bord (pondération coefficients de notes
                        # puis coefficients de matières) — plus de divergence.
                        avg = Grade.calculate_average(student, sy, period)
                        if avg is None:
                            continue
                        # Barème officiel centralisé — jamais de seuils locaux.
                        from apps.grades.models import get_appreciation
                        appreciation = get_appreciation(avg)
                        Bulletin.objects.get_or_create(
                            student=student, school_year=sy, period=period,
                            defaults={
                                "enrollment": enr,
                                "average": avg,
                                "appreciation": appreciation,
                                "general_comment": f"Bulletin {period} — {sy.name}",
                            },
                        )
            self.stdout.write("  ✅ Bulletins avec moyennes du moteur central (2 années)")

        # ── EMPLOI DU TEMPS (année courante) ─────────────────────────────
        if not ClassSchedule.objects.filter(school_year=year_curr).exists():
            slots = [(datetime.time(8, 0), datetime.time(10, 0)),
                     (datetime.time(10, 15), datetime.time(12, 15)),
                     (datetime.time(15, 0), datetime.time(17, 0))]
            rooms_cycle = [r[0] for r in room_defs[:4]]
            for ci, lname in enumerate(demo_levels):
                cls = classes[(year_curr.id, lname)]
                subj_cycle = list(cls.subjects.all())
                for day in range(5):  # Lundi → Vendredi
                    for si, (t1, t2) in enumerate(slots[:2]):
                        subj = subj_cycle[(day * 2 + si) % len(subj_cycle)]
                        ClassSchedule.objects.create(
                            cls=cls, subject=subj,
                            teacher=teachers[(day + si) % len(teachers)],
                            school_year=year_curr,
                            day_of_week=day, start_time=t1, end_time=t2,
                            room=rooms_cycle[ci % len(rooms_cycle)],
                        )
            self.stdout.write("  ✅ Emplois du temps (5 classes × 5 jours × 2 créneaux)")

        # ── DEVOIRS ──────────────────────────────────────────────────────
        if not Homework.objects.filter(school_year=year_curr).exists():
            for lname in demo_levels:
                cls = classes[(year_curr.id, lname)]
                for subj in list(cls.subjects.all())[:2]:
                    Homework.objects.create(
                        title=f"{subj.name} — exercices chapitre 3",
                        description="Faire les exercices 1 à 5 page 42. Rédiger proprement.",
                        subject=subj, teacher=teachers[0], cls=cls,
                        due_date=today + datetime.timedelta(days=random.randint(3, 14)),
                        school_year=year_curr,
                    )
            self.stdout.write("  ✅ Devoirs (année courante)")

        # ── ANNONCES ─────────────────────────────────────────────────────
        ann_texts = [
            ("Rentrée scolaire", f"La rentrée {year_curr.name} est fixée au {year_curr.start_date:%d/%m/%Y}. Bonne rentrée à tous !"),
            ("Réunion parents-professeurs", "Réunion parents-professeurs le 15 novembre à 16h en salle 101."),
            ("Examens du Trimestre", "Les compositions du trimestre se dérouleront la dernière semaine du mois."),
        ]
        for title, body in ann_texts:
            Announcement.objects.get_or_create(
                title=title,
                defaults={"content": body, "school_year": year_curr,
                          "author": admin_user, "target_roles": ["all"]},
            )
        self.stdout.write("  ✅ Annonces")

        # ── NOTIFICATIONS ────────────────────────────────────────────────
        if not Notification.objects.filter(user=admin_user).exists():
            notif_defs = [
                ("payment", "Paiements enregistrés", "Les paiements de démonstration ont été enregistrés."),
                ("grade", "Notes saisies", "Les notes du trimestre ont été saisies pour toutes les classes."),
                ("announcement", "Bienvenue sur FEBA", "Le jeu de données de démonstration est prêt."),
            ]
            for ntype, title, msg in notif_defs:
                Notification.objects.create(user=admin_user, type=ntype, title=title, message=msg)
            self.stdout.write("  ✅ Notifications")

        # ── SALLES VIRTUELLES ────────────────────────────────────────────
        # V5 : AUCUNE salle virtuelle pour FEBA. La visioconférence est une
        # fonctionnalité d'ACADÉMIE EN LIGNE : l'API la refuse à une entité
        # `campus` (403), donc en semer ici produisait des données que
        # personne ne pouvait consulter — et que `make seed-check`
        # signalait à juste titre comme incohérentes.
        # Les salles de démonstration sont créées côté FEBA FHA, plus bas.
        self.stdout.write("  ⏭  Salles virtuelles : réservées à FEBA FHA (académie en ligne)")

        # ── RÉSUMÉ ───────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS("\n✅ Seed terminé — application immédiatement exploitable."))
        self.stdout.write(f"   Années   : {year_n2.name} / {year_n1.name} / {year_curr.name} (active)")
        self.stdout.write(f"   Élèves   : {len(student_list)} (historique 3 ans, redoublants inclus)")
        self.stdout.write("")
        self.stdout.write("   Comptes de démonstration :")
        self.stdout.write("   superadmin@feba.bj  / SuperAdmin@2024")
        self.stdout.write("   admin@feba.bj       / Admin@2024")
        self.stdout.write("   prof.math@feba.bj   / Teacher@2024")
        self.stdout.write("   parent1@feba.bj     / Parent@2024")
        self.stdout.write("   eleve1@feba.bj      / Student@2024")

        # ══════════════════════════════════════════════════════════════
        # ACADÉMIE 2 — FEBA FRENCH HERITAGE ACADEMY
        # ══════════════════════════════════════════════════════════════
        # Le seed d'origine ne connaissait qu'une seule école. Sans ce
        # bloc, une base de démonstration ne permettait pas de tester le
        # filtre d'académie, l'isolation, ni les parcours FHA.
        self._seed_fha(school)

    # ──────────────────────────────────────────────────────────────────
    def _reset_demo_data(self):
        """
        Supprime les données de démonstration. Ne touche PAS aux académies
        elles-mêmes : elles sont recréées à l'identique et référencées par
        les migrations.
        """
        from apps.accounts.models import CustomUser
        from apps.website.models import (
            ContactMessage, FHAEnrollmentApplication, FHAPlacementTestRequest,
            PreRegistration,
        )

        self.stdout.write(self.style.WARNING("  ⚠ Réinitialisation des données de démonstration…"))
        FHAPlacementTestRequest.objects.all().delete()
        FHAEnrollmentApplication.objects.all().delete()
        PreRegistration.objects.all().delete()
        ContactMessage.objects.all().delete()
        # Seuls les comptes de démonstration (@test / @feba.bj) sont retirés.
        CustomUser.objects.filter(email__endswith="@feba.bj").exclude(
            role="superadmin",
        ).delete()
        CustomUser.objects.filter(email__endswith="@febafha.org").delete()

    # ──────────────────────────────────────────────────────────────────
    def _seed_fha(self, feba_school):
        """
        Peuple FEBA French Heritage Academy : académie, comptes, groupes,
        salles virtuelles, préinscriptions, demandes de test et contacts.

        Idempotent : `get_or_create` partout, aucune duplication au rejeu.
        Aucune donnée commerciale inventée (tarifs, dates de rentrée...).
        """
        import datetime

        from django.utils import timezone

        from apps.accounts.models import CustomUser
        from apps.classes.models import Class
        from apps.schools.models import Level, Room, School, SchoolYear
        from apps.students.models import Student
        from apps.subjects.models import Subject
        from apps.teachers.models import Teacher
        from apps.virtualclass.models import VirtualRoom
        from apps.website.models import (
            ContactMessage, FHAEnrollmentApplication, FHAPlacementTestRequest,
        )

        self.stdout.write(self.style.MIGRATE_HEADING("\nSeed FEBA French Heritage Academy"))

        fha, _ = School.objects.get_or_create(
            code=School.CODE_FEBA_FHA,
            defaults={
                "name": "FEBA French Heritage Academy",
                "legal_name": "FEBA French Heritage Academy",
                "slug": "feba-fha",
                "entity_type": "online",
                "address": "Programme 100 % en ligne — cours dispensés depuis FEBA, Cotonou.",
                "city": "Cotonou", "country": "Bénin",
                "phone": official_phone(),
                "whatsapp": "+1 (215) 715-5406",
                "timezone": "America/New_York",
                "currency_code": "USD",
                "default_language": "en",
                "matricule_prefix": "FHA",
                "settings": {
                    "tagline": "From English Speakers to Confident French Speakers",
                    # Non validé par la direction → reste nul.
                    "pending_direction_validation": {
                        "annual_fee": None, "installments_allowed": None,
                        "school_year_start_date": None, "group_schedules": None,
                        "sibling_discount": None, "early_bird_discount": None,
                        "refund_policy": None, "teacher_names": None,
                        "payment_provider": None, "zoom_recording_policy": None,
                    },
                },
            },
        )
        self.stdout.write("  ✅ Académie FEBA FHA")

        today = timezone.now().date()
        start = today.year if today.month >= 9 else today.year - 1
        SchoolYear.objects.filter(school=fha, is_current=True).update(is_current=False)
        year, _ = SchoolYear.objects.get_or_create(
            school=fha, name=f"{start}-{start + 1}",
            defaults={
                "start_date": datetime.date(start, 9, 1),
                "end_date": datetime.date(start + 1, 6, 30),
            },
        )
        year.is_current = True
        year.save(update_fields=["is_current"])

        # Les trois groupes de lancement du document de cadrage.
        #
        # Chacun illustre un PARCOURS LINGUISTIQUE différent : les groupes
        # de la diaspora ne suivent pas tous le même. Une base de
        # démonstration où les trois classes seraient bilingues ne
        # montrerait jamais le cas monolingue — celui-là même qui était
        # déclaré « incomplet » pour toujours.
        groups = {}
        for order, (key, label, track) in enumerate(
            [("junior_roots", "Junior Roots", Class.TRACK_FRANCOPHONE),
             ("french_explorers", "French Explorers", Class.TRACK_BILINGUAL),
             ("french_ambassadors", "French Ambassadors", Class.TRACK_ANGLOPHONE)], start=1,
        ):
            level, _ = Level.objects.get_or_create(
                school=fha, name=label, defaults={"order": order, "cycle": "primaire"},
            )
            groups[key], created = Class.objects.get_or_create(
                school_year=year, level=level, name=label,
                defaults={"max_students": 15, "language_track": track},
            )
            if not created and groups[key].language_track != track:
                groups[key].language_track = track
                groups[key].save(update_fields=["language_track"])

        # Matières de chaque parcours, et rattachement aux groupes.
        #
        # Sans elles, les trois groupes restent « incomplets » à l'écran et
        # aucun bulletin n'a de contenu : la démonstration s'arrêtait là.
        fha_subjects = {}
        for nom, langue, ordre in (
            ("Français — expression", "fr", 1),
            ("Français — lecture", "fr", 2),
            ("Culture francophone", "fr", 3),
            ("English — conversation", "en", 4),
            ("African Heritage & Culture", "en", 5),
        ):
            fha_subjects[nom], _ = Subject.objects.get_or_create(
                school=fha, name=nom,
                defaults={"language": langue, "coefficient": 1, "order": ordre},
            )
        par_langue = {
            "fr": [s for n, s in fha_subjects.items() if s.language == "fr"],
            "en": [s for n, s in fha_subjects.items() if s.language == "en"],
        }
        for groupe in groups.values():
            attendues = []
            for langue in groupe.expected_subject_languages():
                attendues.extend(par_langue[langue])
            groupe.subjects.set(attendues)

        self.stdout.write(
            "  ✅ Groupes : Junior Roots (francophone) · French Explorers "
            "(bilingue) · French Ambassadors (anglophone)")

        # Salles PHYSIQUES de l'académie en ligne.
        #
        # L'écran « Paramètres » affichait « Salles physiques de l'École
        # (0) » alors que trois groupes existaient. Ce n'était pas un
        # défaut de portée : une salle physique n'est pas une classe, et
        # FEBA FHA n'en avait tout simplement aucune. Une académie en ligne
        # en a peu — mais elle en a : le studio d'où les cours sont
        # diffusés depuis Cotonou.
        for rname, rtype in (
            ("Studio de diffusion 1", "computer"),
            ("Studio de diffusion 2", "computer"),
            ("Bureau pédagogique FHA", "admin"),
        ):
            Room.objects.get_or_create(
                school=fha, name=rname, defaults={"room_type": rtype})
        self.stdout.write("  ✅ 3 salles physiques FHA")

        def make_user(email, role, first, last, password):
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    # Préfixe « fha_ » : le nom d'utilisateur est unique
                    # GLOBALEMENT, et « admin@febafha.org » produirait
                    # sinon le même « admin » que le compte FEBA.
                    "username": f"fha_{email.split('@')[0]}", "role": role,
                    "first_name": first, "last_name": last, "school": fha,
                    "preferred_language": "en",
                },
            )
            if created:
                user.set_password(password)
                user.save()
            return user

        admin_fha = make_user("admin@febafha.org", "admin", "Awa", "Koffi", "Admin@2024")
        teacher_fha = make_user("prof@febafha.org", "teacher", "Céline", "Doe", "Teacher@2024")
        Teacher.objects.get_or_create(user=teacher_fha)
        parent_fha = make_user("parent@febafha.org", "parent", "Sylvie", "Adjovi", "Parent@2024")

        students = []
        for index, (first, last, group) in enumerate([
            ("Naomi", "Adjovi", "french_explorers"),
            ("Kofi", "Mensah", "junior_roots"),
            ("Ama", "Diallo", "french_ambassadors"),
        ], start=1):
            user = make_user(f"eleve{index}@febafha.org", "student", first, last, "Student@2024")
            student, _ = Student.objects.get_or_create(
                user=user,
                defaults={
                    "school": fha, "first_name": first, "last_name": last,
                    "current_class": groups[group], "school_year": year,
                    "date_of_birth": datetime.date(2013 + index, 3, 12),
                },
            )
            students.append(student)

        # V8 — Le compte parent FHA existait sans profil `Parent` ni lien
        # vers les élèves : /api/parents/me/ renvoyait « profil introuvable »,
        # et le parent ne pouvait donc ni consulter ses enfants ni payer
        # par carte. C'est l'académie qui facture en dollars : le parcours
        # de paiement y était précisément intestable.
        from apps.parents.models import Parent, ParentStudent

        parent_profile, _ = Parent.objects.get_or_create(
            user=parent_fha, defaults={"profession": "Cadre"},
        )
        for index, student in enumerate(students):
            ParentStudent.objects.get_or_create(
                parent=parent_profile, student=student,
                defaults={"relationship": "mother", "is_primary_contact": index == 0},
            )
        self.stdout.write("  ✅ Comptes FHA (admin, enseignant, parent lié aux 3 élèves)")

        # Salles virtuelles : réservées aux académies en ligne.
        for key, label in groups.items():
            VirtualRoom.objects.get_or_create(
                school=fha, class_obj=groups[key],
                name=f"Cours en direct — {groups[key].name}",
                defaults={
                    "school_year": year,
                    "description": "Séance hebdomadaire en visioconférence.",
                    "scheduled_at": timezone.now() + datetime.timedelta(days=2),
                    "duration_minutes": 60,
                    "created_by": teacher_fha,
                },
            )
        self.stdout.write("  ✅ Salles virtuelles FHA (instance auto-hébergée)")

        # ── Emploi du temps FEBA FHA ─────────────────────────────────────
        # Séances en direct : heure stockée en UTC, jamais en heure locale.
        # Les créneaux ci-dessous correspondent à des fins d'après-midi
        # côte est des États-Unis — l'horaire réel reste à valider par la
        # direction (voir `pending_direction_validation.group_schedules`).
        from apps.schedule.models import OnlineSessionSchedule
        from apps.subjects.models import Subject as SubjectModel

        fha_subject, _ = SubjectModel.objects.get_or_create(
            school=fha, code="FHA-FR",
            defaults={"name": "Français langue d'héritage", "coefficient": 1, "language": "fr"},
        )
        fha_teacher = Teacher.objects.filter(user=teacher_fha).first()
        # (groupe, jour UTC, heure UTC) — mardi/jeudi/samedi.
        session_defs = [
            ("junior_roots", 1, datetime.time(22, 0), 45),
            ("french_explorers", 3, datetime.time(22, 0), 60),
            ("french_ambassadors", 5, datetime.time(15, 0), 60),
        ]
        for key, day, start_utc, duration in session_defs:
            OnlineSessionSchedule.objects.get_or_create(
                academy=fha, group=groups[key], day_of_week=day,
                start_time_utc=start_utc,
                defaults={
                    "subject": fha_subject,
                    "teacher": fha_teacher,
                    "school_year": year,
                    "duration_minutes": duration,
                    "display_timezone": "America/New_York",
                    "virtual_room": VirtualRoom.objects.filter(
                        school=fha, class_obj=groups[key],
                    ).first(),
                    "reminders_enabled": True,
                    "reminder_minutes_before": 30,
                },
            )
        self.stdout.write("  ✅ Emploi du temps FHA (3 séances en direct, heures UTC)")

        # ── Paiements FEBA FHA, en DOLLARS ───────────────────────────────
        # Sans encaissement FHA, rien ne prouvait à l'écran que l'académie
        # en ligne facture bien en USD : toutes les recettes visibles
        # étaient celles de FEBA, donc en francs CFA.
        #
        # Les montants ci-dessous sont des VALEURS DE DÉMONSTRATION. Le
        # tarif réel de FEBA FHA n'est pas validé par la direction (voir
        # `pending_direction_validation.annual_fee`) : ils ne doivent pas
        # être présentés comme une grille tarifaire.
        from apps.payments.models import Payment

        fha_admin = admin_fha
        for index, student in enumerate(students):
            for kind, amount in (("inscription", "75.00"), ("mensualite", "125.50")):
                # `exists()` plutôt que `get_or_create` : dès qu'un second
                # paiement du même type existe — saisi à la main, ou créé
                # pendant une vérification —, `get_or_create` lève
                # MultipleObjectsReturned et fait échouer TOUT le seed, qui
                # est transactionnel. Le rejeu du seed doit être inoffensif
                # sur une base déjà utilisée.
                if Payment.objects.filter(
                    student=student, payment_type=kind, school_year=year,
                ).exists():
                    continue
                Payment.objects.create(
                    student=student, payment_type=kind, school_year=year,
                    # `amount` est saisi en unité majeure ; le modèle en
                    # dérive l'entier de cents et impose la devise USD
                    # depuis l'académie.
                    amount=Decimal(amount),
                    payment_method="card",
                    payment_date=today - datetime.timedelta(days=10 + index),
                    received_by=fha_admin,
                    notes="Paiement de démonstration — montant non contractuel.",
                )
        self.stdout.write("  ✅ Paiements FHA en dollars (démonstration, montants non contractuels)")

        # ── Grille tarifaire de démonstration ────────────────────────────
        # Le paiement par carte refuse tout montant venu du navigateur : il
        # lit cette grille. Sans elle, la démonstration afficherait « aucun
        # tarif publié » — ce qui serait le comportement CORRECT, mais ne
        # montrerait pas le parcours de paiement.
        #
        # Montants NON CONTRACTUELS, identiques aux paiements ci-dessus.
        from apps.payments.fee_models import FeeSchedule

        feba_year = feba_school.years.filter(is_current=True).first()
        for academy, year_obj, tarifs in (
            (fha, year, (("inscription", 7500, "Frais d'inscription (démonstration)"),
                         ("mensualite", 12550, "Mensualité (démonstration)"))),
            (feba_school, feba_year,
             (("inscription", 25000, "Frais d'inscription (démonstration)"),
              ("mensualite", 35000, "Mensualité (démonstration)"))),
        ):
            for kind, minor, label in tarifs:
                FeeSchedule.objects.get_or_create(
                    academy=academy, school_year=year_obj, level=None,
                    payment_type=kind,
                    defaults={"amount_minor": minor, "label": label},
                )
        self.stdout.write("  ✅ Grille tarifaire des deux académies (montants non contractuels)")

        # Fiche d'inscription de démonstration.
        FHAEnrollmentApplication.objects.get_or_create(
            entity=fha,
            parent1_email="demo.parent@example.com",
            child_first_name="Élise",
            child_last_name="Kponou",
            child_birth_date=datetime.date(2015, 5, 4),
            defaults={
                "child_country": "United States", "child_state_province": "PA",
                "child_city": "Philadelphia",
                "family_origin_country": "Bénin",
                "home_main_language": "English",
                "french_levels": ["few_words", "understands_replies_english"],
                "parent_goals": ["family_conversation", "grandparents"],
                "parent1_first_name": "Marie", "parent1_last_name": "Kponou",
                "parent1_phone": "+1 215 555 0100",
                "parent1_preferred_language": "en",
                "parent1_timezone": "America/New_York",
                "family_timezone": "America/New_York",
                "available_days": [3, 6],
                "available_time_slots": [{"start": "17:00", "end": "18:30"}],
                "has_computer": True, "has_internet": True,
                "consent_rules": True, "consent_privacy": True,
                "consent_data_processing": True,
                "consent_parental_authorization": True, "consent_zoom": True,
                "consents_accepted_at": timezone.now(),
                "status": FHAEnrollmentApplication.STATUS_FORM_RECEIVED,
            },
        )

        # Demande de test de placement de démonstration.
        FHAPlacementTestRequest.objects.get_or_create(
            entity=fha,
            parent_email="demo.test@example.com",
            child_first_name="Yann",
            child_last_name="Sossou",
            child_birth_date=datetime.date(2016, 9, 20),
            defaults={
                "child_country": "Canada", "child_state_province": "QC",
                "parent_first_name": "Paul", "parent_last_name": "Sossou",
                "parent_phone": "+1 514 555 0111",
                "parent_timezone": "America/Toronto",
                "preferred_language": "en",
                "estimated_level": "few_words",
                "preferred_date": today + datetime.timedelta(days=7),
                "preferred_time": datetime.time(17, 0),
                "consent_video": True,
                "status": "requested",
            },
        )

        # Message de contact FHA (boîte séparée de celle de FEBA).
        ContactMessage.objects.get_or_create(
            entity=fha, email="demo.contact@example.com",
            subject="Question about the placement test",
            defaults={
                "name": "Grace Okafor", "message": "How do I book an assessment?",
                "consent": True, "category": "placement_test",
                "country": "United States", "state_province": "NY",
                "timezone": "America/New_York", "preferred_language": "en",
            },
        )
        self.stdout.write("  ✅ Préinscription, demande de test et contact FHA")

        # Le Super Administrateur appartient aux DEUX académies : sans
        # cela, le sélecteur ne lui proposerait qu'une seule entité.
        superadmin = CustomUser.objects.filter(role="superadmin").first()
        if superadmin is not None:
            superadmin.save()  # le signal crée les appartenances manquantes
            self.stdout.write("  ✅ Super Administrateur rattaché aux deux académies")

        self.stdout.write(self.style.SUCCESS("\n✅ Seed FEBA FHA terminé."))
        self.stdout.write("   Comptes FEBA FHA :")
        self.stdout.write("   admin@febafha.org   / Admin@2024")
        self.stdout.write("   prof@febafha.org    / Teacher@2024")
        self.stdout.write("   parent@febafha.org  / Parent@2024")
        self.stdout.write("   eleve1@febafha.org  / Student@2024")
