"""
Contrôle d'intégrité des données de démonstration (make seed-check).

Vérifie qu'AUCUNE relation inter-académie invalide n'existe. Sortie non
nulle si un problème est détecté : utilisable en CI.
"""
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Vérifie l'intégrité et l'isolation des données de démonstration."

    def handle(self, *args, **options):
        from apps.accounts.models import CustomUser
        from apps.classes.models import Class
        from apps.schools.models import School
        from apps.students.models import Student
        from apps.virtualclass.models import VirtualRoom
        from apps.website.models import (
            ContactMessage, FHAEnrollmentApplication, FHAPlacementTestRequest,
            PreRegistration,
        )

        problems = []
        checks = 0

        def check(label, condition, detail=""):
            nonlocal checks
            checks += 1
            if condition:
                self.stdout.write(self.style.SUCCESS(f"  ✓ {label}"))
            else:
                problems.append(f"{label}{f' — {detail}' if detail else ''}")
                self.stdout.write(self.style.ERROR(f"  ✗ {label} {detail}"))

        self.stdout.write(self.style.MIGRATE_HEADING("Contrôle d'intégrité multi-académies"))

        # ── Les deux académies existent ─────────────────────────────────
        feba = School.objects.filter(code=School.CODE_FEBA).first()
        fha = School.objects.filter(code=School.CODE_FEBA_FHA).first()
        check("L'académie FEBA existe", feba is not None)
        check("L'académie FEBA FHA existe", fha is not None)
        if feba is None or fha is None:
            self.stdout.write(self.style.ERROR("\nAcadémies manquantes : lancez « make seed »."))
            sys.exit(1)

        check("FEBA est de type présentiel", feba.entity_type == "campus", feba.entity_type)
        check("FEBA FHA est de type en ligne", fha.entity_type == "online", fha.entity_type)

        # ── Aucun croisement d'académie ─────────────────────────────────
        mismatched = [
            s for s in Student.objects.select_related("user", "school", "current_class__school_year__school")
            if s.user_id and s.user.school_id and s.user.school_id != s.school_id
        ]
        check(
            "Aucun élève dont le compte appartient à une autre académie",
            not mismatched,
            f"{len(mismatched)} anomalie(s)",
        )

        wrong_class = [
            s for s in Student.objects.select_related("school", "current_class__school_year__school")
            if s.current_class_id
            and s.current_class.school_year.school_id != s.school_id
        ]
        check(
            "Aucun élève inscrit dans une classe d'une autre académie",
            not wrong_class,
            f"{len(wrong_class)} anomalie(s)",
        )

        # ── Salles virtuelles ───────────────────────────────────────────
        campus_rooms = VirtualRoom.objects.filter(school__entity_type="campus").count()
        check(
            "Aucune salle virtuelle rattachée à une académie présentielle",
            campus_rooms == 0,
            f"{campus_rooms} salle(s)",
        )

        wrong_room_class = [
            r for r in VirtualRoom.objects.select_related("school", "class_obj__school_year__school")
            if r.class_obj_id and r.class_obj.school_year.school_id != r.school_id
        ]
        check(
            "Aucune salle rattachée à un groupe d'une autre académie",
            not wrong_room_class,
            f"{len(wrong_room_class)} anomalie(s)",
        )

        # ── Soumissions publiques ───────────────────────────────────────
        check(
            "Aucun message de contact sans académie",
            not ContactMessage.objects.filter(entity__isnull=True).exists(),
            f"{ContactMessage.objects.filter(entity__isnull=True).count()} message(s)",
        )
        check(
            "Aucune préinscription sans académie",
            not PreRegistration.objects.filter(entity__isnull=True).exists(),
            f"{PreRegistration.objects.filter(entity__isnull=True).count()} demande(s)",
        )
        check(
            "Toutes les fiches FHA appartiennent à FEBA FHA",
            not FHAEnrollmentApplication.objects.exclude(entity=fha).exists(),
        )
        check(
            "Toutes les demandes de test appartiennent à FEBA FHA",
            not FHAPlacementTestRequest.objects.exclude(entity=fha).exists(),
        )

        # ── Comptes ─────────────────────────────────────────────────────
        check(
            "Aucun administrateur sans académie",
            not CustomUser.objects.filter(role="admin", school__isnull=True).exists(),
        )
        check("Au moins un Super Administrateur existe",
              CustomUser.objects.filter(role="superadmin").exists())

        superadmins = CustomUser.objects.filter(role="superadmin")
        both = all(
            su.memberships.filter(organization__in=[feba, fha]).count() >= 2
            for su in superadmins
        ) if superadmins.exists() else False
        check("Le Super Administrateur appartient aux deux académies", both)

        # ── Classes ─────────────────────────────────────────────────────
        orphan_classes = Class.objects.filter(school_year__isnull=True).count()
        check("Aucune classe sans année scolaire", orphan_classes == 0, f"{orphan_classes}")

        # ── Emplois du temps séparés ────────────────────────────────────
        from apps.schedule.models import ClassSchedule, OnlineSessionSchedule

        online_in_campus_timetable = ClassSchedule.objects.filter(
            school_year__school__entity_type="online",
        ).count()
        check(
            "Aucune académie en ligne dans l'emploi du temps présentiel",
            online_in_campus_timetable == 0,
            f"{online_in_campus_timetable} créneau(x)",
        )

        campus_in_online_timetable = OnlineSessionSchedule.objects.filter(
            academy__entity_type="campus",
        ).count()
        check(
            "Aucune école présentielle dans les séances en ligne",
            campus_in_online_timetable == 0,
            f"{campus_in_online_timetable} séance(s)",
        )

        # Le croisement le plus insidieux : un créneau qui relie deux
        # académies. Il ne se voit pas à l'écran mais fausse tout ce qui en
        # découle (bulletins, présences, moyennes).
        crossed_slots = [
            slot for slot in ClassSchedule.objects.select_related(
                "cls__school_year__school", "subject__school", "school_year__school",
                "teacher__user__school",
            )
            if len({
                ident for ident in (
                    slot.school_year.school_id,
                    slot.cls.school_year.school_id if slot.cls_id else None,
                    slot.subject.school_id if slot.subject_id else None,
                    slot.teacher.user.school_id if slot.teacher_id and slot.teacher.user else None,
                ) if ident is not None
            }) > 1
        ]
        check(
            "Aucun créneau FEBA reliant deux académies",
            not crossed_slots,
            f"{len(crossed_slots)} créneau(x)",
        )

        crossed_sessions = [
            session for session in OnlineSessionSchedule.objects.select_related(
                "academy", "group__school_year__school", "subject__school",
                "school_year__school", "virtual_room__school", "teacher__user__school",
            )
            if len({
                ident for ident in (
                    session.academy_id,
                    session.group.school_year.school_id if session.group_id else None,
                    session.subject.school_id if session.subject_id else None,
                    session.school_year.school_id if session.school_year_id else None,
                    session.virtual_room.school_id if session.virtual_room_id else None,
                ) if ident is not None
            }) > 1
        ]
        check(
            "Aucune séance FEBA FHA reliant deux académies",
            not crossed_sessions,
            f"{len(crossed_sessions)} séance(s)",
        )

        # ── Résumé ──────────────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(f"Académies : FEBA={CustomUser.objects.filter(school=feba).count()} compte(s) · "
                          f"FEBA_FHA={CustomUser.objects.filter(school=fha).count()} compte(s)")
        self.stdout.write(f"Élèves    : FEBA={Student.objects.filter(school=feba).count()} · "
                          f"FEBA_FHA={Student.objects.filter(school=fha).count()}")
        self.stdout.write(f"Fiches FHA : {FHAEnrollmentApplication.objects.count()} · "
                          f"Tests : {FHAPlacementTestRequest.objects.count()}")
        self.stdout.write(
            f"Emplois du temps : FEBA={ClassSchedule.objects.filter(school_year__school=feba).count()} créneau(x) · "
            f"FEBA_FHA={OnlineSessionSchedule.objects.filter(academy=fha).count()} séance(s) en ligne"
        )

        if problems:
            self.stdout.write(self.style.ERROR(
                f"\n✗ {len(problems)} problème(s) sur {checks} contrôles."
            ))
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS(f"\n✓ {checks} contrôles passés — isolation intacte."))
