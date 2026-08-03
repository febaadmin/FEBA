"""
P3 — Ce que le mois a réellement contenu.

LA RÈGLE, ET LA RAISON
----------------------
Aucune donnée n'est inventée, estimée, arrondie « pour faire joli » ni
remplacée par une moyenne de classe. Quand une rubrique est vide, elle
le DIT :

    Aucune donnée enregistrée pour cette période.

C'est plus honnête qu'un tiret, et surtout plus utile : un parent qui
lit cette phrase sait que rien n'a été saisi. Un parent qui lit « 0
absence » croit que la présence a été relevée et qu'elle était parfaite.
Les deux affirmations sont incompatibles, et seule la première est
vérifiable.

Chaque rubrique renvoie donc `{"has_data": bool, ...}` : le rendu décide
de la formulation, l'agrégation décide de la vérité.
"""
import calendar
from datetime import date

from django.db.models import Avg, Count, Q

#: La phrase exacte, en un seul endroit. Répétée dans quinze fichiers,
#: elle finirait par exister en quatre variantes légèrement différentes.
EMPTY_SECTION = "Aucune donnée enregistrée pour cette période."

#: DEUX ABSENCES DIFFÉRENTES, DEUX PHRASES DIFFÉRENTES.
#:
#: `EMPTY_SECTION` parle des données SAISIES par les enseignants : rien
#: n'a été relevé ce mois-ci. `NOT_WRITTEN` parle des textes que
#: l'administration rédige elle-même : le champ existe, il attend une
#: plume. Les confondre laissait croire à un défaut de saisie des
#: enseignants là où c'est l'administration qui n'a pas encore écrit.
NOT_WRITTEN = "Non renseigné par l'administration."


def month_bounds(year, month):
    """Premier et dernier jour du mois, inclus."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _section(has_data, **payload):
    return {"has_data": bool(has_data), **payload}


# ── Présence ─────────────────────────────────────────────────────────


def attendance_section(student, start, end):
    from apps.attendance.models import Attendance

    rows = Attendance.objects.filter(student=student, date__gte=start,
                                     date__lte=end)
    total = rows.count()
    if not total:
        return _section(False)

    counts = rows.aggregate(
        present=Count("pk", filter=Q(status="present")),
        absent=Count("pk", filter=Q(status="absent")),
        late=Count("pk", filter=Q(status="late")),
        excused=Count("pk", filter=Q(status="excused")),
    )
    # Le taux est calculé sur les jours RELEVÉS, pas sur les jours
    # ouvrés du mois : diviser par un nombre de jours théorique
    # fabriquerait un pourcentage qu'aucune saisie ne soutient.
    presence_rate = round(
        100 * (counts["present"] + counts["excused"]) / total, 1)
    justifications = [
        {"date": row.date.isoformat(), "statut": row.get_status_display(),
         "motif": row.justification}
        for row in rows.exclude(justification="").order_by("date")
    ]
    return _section(
        True, total_days=total, **counts, presence_rate=presence_rate,
        justifications=justifications,
    )


# ── Cours et séances en ligne ────────────────────────────────────────


def sessions_section(student, start, end):
    """
    Séances suivies : salles virtuelles réellement rejointes, et
    créneaux inscrits à l'emploi du temps du groupe.
    """
    from apps.virtualclass.models import VirtualRoomAttendance

    joined = VirtualRoomAttendance.objects.filter(
        user=getattr(student, "user", None),
        joined_at__date__gte=start, joined_at__date__lte=end,
    ).select_related("room") if getattr(student, "user_id", None) else []

    seances = [
        {
            "salle": getattr(attendance.room, "name", ""),
            "date": attendance.joined_at.date().isoformat(),
            "duree_minutes": round((attendance.duration_seconds or 0) / 60),
        }
        for attendance in joined
    ]
    total_minutes = sum(s["duree_minutes"] for s in seances)

    scheduled = _scheduled_sessions(student)
    if not seances and not scheduled:
        return _section(False)
    return _section(True, seances=seances, total_minutes=total_minutes,
                    creneaux=scheduled)


def _scheduled_sessions(student):
    """Créneaux hebdomadaires du groupe de l'élève, s'il en a un."""
    from apps.schedule.models import OnlineSessionSchedule

    group = getattr(student, "current_class", None)
    if group is None:
        return []
    rows = OnlineSessionSchedule.objects.filter(
        group=group).select_related("subject", "teacher")
    jours = ["", "lundi", "mardi", "mercredi", "jeudi", "vendredi",
             "samedi", "dimanche"]
    return [
        {
            "jour": jours[row.day_of_week] if 1 <= row.day_of_week <= 7 else "",
            "heure_utc": row.start_time_utc.strftime("%H:%M")
            if row.start_time_utc else "",
            "matiere": getattr(row.subject, "name", ""),
        }
        for row in rows
    ]


# ── Devoirs ──────────────────────────────────────────────────────────


def homework_section(student, start, end):
    from apps.homework.models import Homework

    klass = getattr(student, "current_class", None)
    if klass is None:
        return _section(False)

    rows = Homework.objects.filter(
        cls=klass, due_date__gte=start, due_date__lte=end,
    ).select_related("subject").order_by("due_date")
    if not rows.exists():
        return _section(False)

    return _section(
        True,
        total=rows.count(),
        devoirs=[
            {
                "titre": row.title,
                "matiere": getattr(row.subject, "name", ""),
                "echeance": row.due_date.isoformat(),
                "consigne": row.description,
            }
            for row in rows
        ],
    )


# ── Notes et évaluations ─────────────────────────────────────────────


def grades_section(student, start, end):
    from apps.grades.models import Grade

    rows = Grade.objects.filter(
        student=student, created_at__date__gte=start,
        created_at__date__lte=end, is_deleted=False,
    ).select_related("subject", "teacher").order_by("created_at")
    if not rows.exists():
        return _section(False)

    notes = [
        {
            "matiere": getattr(row.subject, "name", ""),
            "type": row.get_note_type_display(),
            "valeur": float(row.value) if row.value is not None else None,
            "bareme": float(getattr(row, "max_value", 20) or 20),
            "coefficient": row.note_coefficient,
            "date": row.created_at.date().isoformat(),
            # Le commentaire de l'enseignant est repris MOT POUR MOT.
            # Le résumer serait réécrire une appréciation signée.
            "commentaire": row.comment or "",
        }
        for row in rows
    ]
    chiffrees = [n for n in notes if n["valeur"] is not None]
    moyenne = None
    if chiffrees:
        # Moyenne pondérée, ramenée sur 20 : mélanger des notes sur 10 et
        # sur 20 sans conversion donnerait un chiffre faux et crédible.
        total_poids = sum(n["coefficient"] for n in chiffrees) or 1
        moyenne = round(sum(
            (n["valeur"] / n["bareme"]) * 20 * n["coefficient"]
            for n in chiffrees) / total_poids, 2)

    commentaires = [n["commentaire"] for n in notes if n["commentaire"]]
    return _section(True, notes=notes, moyenne_sur_20=moyenne,
                    commentaires_enseignants=commentaires)


# ── Assemblage ───────────────────────────────────────────────────────

#: L'ordre dans lequel le rapport se lit. Le titre est ici, avec la
#: fonction qui le remplit : ajouter une rubrique sans l'afficher, ou
#: l'afficher sans la remplir, devient visible d'un coup d'œil.
SECTIONS = [
    ("attendance", "Présence et assiduité", attendance_section),
    ("sessions", "Cours et séances en ligne", sessions_section),
    ("homework", "Devoirs et travaux", homework_section),
    ("grades", "Évaluations et résultats", grades_section),
]


def build_report_data(student, year, month):
    """
    Relève le mois d'un élève. Ne décide de rien, n'invente rien.

    Le résultat est stocké tel quel dans `generated_data` : le rapport
    reste lisible tel qu'il a été envoyé, même si une note est corrigée
    le mois suivant.
    """
    start, end = month_bounds(year, month)
    data = {
        "periode": {"annee": year, "mois": month,
                    "debut": start.isoformat(), "fin": end.isoformat()},
        "eleve": {
            "nom": f"{student.first_name} {student.last_name}".strip(),
            "matricule": getattr(student, "matricule", "") or "",
            "groupe": str(getattr(student, "current_class", "") or ""),
        },
        "sections": {},
    }
    for key, title, builder in SECTIONS:
        section = builder(student, start, end)
        section["title"] = title
        data["sections"][key] = section

    renseignees = sum(1 for s in data["sections"].values() if s["has_data"])
    data["resume"] = {
        "rubriques_renseignees": renseignees,
        "rubriques_totales": len(SECTIONS),
        # Un mois entièrement vide n'est PAS une erreur : c'est une
        # information, et le rapport doit pouvoir la porter sans
        # prétendre le contraire.
        "mois_sans_donnee": renseignees == 0,
    }
    return data
