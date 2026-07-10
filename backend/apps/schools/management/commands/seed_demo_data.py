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

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

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

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)  # données reproductibles

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
        school, _ = School.objects.get_or_create(
            name="Groupe Scolaire FEBA",
            defaults={
                "address": "Rue des Cocotiers, Akpakpa",
                "city": "Cotonou", "country": "Bénin",
                "phone": "+229 97 00 00 00", "email": "contact@feba.bj",
                "matricule_prefix": "FEBA",  # BUG N°8 : matricules FEBA_26_0001
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
                                note_coefficient=random.choice([1, 1, 2]),
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
                        appreciation = ("Excellent travail" if avg >= 16 else
                                        "Bon travail" if avg >= 14 else
                                        "Travail satisfaisant" if avg >= 12 else
                                        "Peut mieux faire" if avg >= 10 else
                                        "Efforts insuffisants")
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

        # ── SALLES VIRTUELLES (visioconférence) ──────────────────────────
        if not VirtualRoom.objects.filter(school=school).exists():
            VirtualRoom.objects.create(
                school=school, school_year=year_curr, created_by=admin_user,
                name="Réunion générale des enseignants",
                description="Salle permanente de coordination pédagogique.",
            )
            VirtualRoom.objects.create(
                school=school, school_year=year_curr, created_by=admin_user,
                name=f"Cours en ligne — {demo_levels[2]}-A",
                description="Cours de soutien hebdomadaire.",
                class_obj=classes[(year_curr.id, demo_levels[2])],
                subject=subjects["MATH"],
                scheduled_at=timezone.now() + datetime.timedelta(days=2),
                duration_minutes=90,
            )
            self.stdout.write("  ✅ Salles virtuelles (Jitsi)")

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
