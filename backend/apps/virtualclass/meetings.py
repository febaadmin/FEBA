"""
apps/virtualclass/meetings.py — cycle de vie des réunions plugNmeet.

Les VUES contrôlent les permissions FEBA (académie, rôle, classe, état de
la salle — voir services.assert_can_join) ; ce module fait le reste :
ouvrir ou retrouver la réunion, émettre le jeton d'adhésion, suivre les
présences, fermer la réunion, et garder le statut FEBA aligné sur l'état
réel de plugNmeet.

PRÉSENCES
---------
Une ligne VirtualRoomAttendance par (salle, utilisateur, réunion). La
source de vérité est la liste des événements plugNmeet reçus
(VirtualRoomEvent) : à chaque événement, la ligne est RECALCULÉE à partir
de tous les événements de cet utilisateur pour cette réunion, triés par
date. D'où :
  - un webhook reçu deux fois est ignoré (event_id unique) ;
  - des événements reçus dans le désordre donnent le même résultat ;
  - une reconnexion (sortie puis entrée) est comptée, et seules les
    périodes de présence effective entrent dans la durée ;
  - une déconnexion brutale est close par l'événement de sortie émis par
    plugNmeet, ou par la fin de la réunion.
"""
import logging
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import plugnmeet
from .models import VirtualRoom, VirtualRoomAttendance, VirtualRoomEvent

logger = logging.getLogger("apps")

JOIN_EVENTS = {"participant_joined"}
LEAVE_EVENTS = {"participant_left"}
#: Seuls ces événements sont conservés : plugNmeet en émet bien d'autres
#: (track_published à chaque micro ou caméra, artifact_created…), dont
#: l'archivage ferait grossir la base sans rien apporter aux présences.
STORED_EVENTS = JOIN_EVENTS | LEAVE_EVENTS | {"room_started", "room_finished"}


def provider():
    return (getattr(settings, "VIDEO_PROVIDER", "plugnmeet") or "plugnmeet").lower()


def _enrollment_for(user, room):
    student = getattr(user, "student_profile", None)
    if student is None or not room.school_year_id:
        return None
    return student.enrollments.filter(school_year_id=room.school_year_id).first()


def _mark_meeting_started(room, sid, started_at=None):
    fields = []
    if sid and room.meeting_sid != sid:
        room.meeting_sid = sid
        room.meeting_started_at = started_at or timezone.now()
        room.meeting_ended_at = None
        fields += ["meeting_sid", "meeting_started_at", "meeting_ended_at"]
    if room.status in ("scheduled", "ended"):
        room.status = "live"
        fields.append("status")
    if fields:
        room.save(update_fields=fields + ["updated_at"])


def open_meeting(room, user, *, moderator, lang="fr"):
    """
    Crée (ou retrouve) la réunion, enregistre la participation et renvoie
    l'URL d'adhésion. Lève plugnmeet.PlugNmeetUnavailable / PlugNmeetError.

    Le jeton est à USAGE UNIQUE : il n'est ni stocké ni journalisé.
    """
    info = plugnmeet.create_room(room)
    sid = (info or {}).get("sid") or ""
    _mark_meeting_started(room, sid)
    token = plugnmeet.join_token(room, user, is_admin=moderator, lang=lang)

    attendance = None
    if sid:
        try:
            with transaction.atomic():
                attendance, created = VirtualRoomAttendance.objects.get_or_create(
                    room=room, user=user, session_sid=sid,
                    defaults={"enrollment": _enrollment_for(user, room)},
                )
        except IntegrityError:  # deux onglets simultanés : la ligne existe
            attendance = VirtualRoomAttendance.objects.get(room=room, user=user, session_sid=sid)
    else:  # pragma: no cover — plugNmeet renvoie toujours un sid
        attendance = VirtualRoomAttendance.objects.create(
            room=room, user=user, enrollment=_enrollment_for(user, room))
    return {"join_url": plugnmeet.join_url(token), "attendance": attendance, "session_sid": sid}


def close_open_attendances(room, at=None, session_sid=None):
    """Clôt les présences encore ouvertes (fin de réunion)."""
    at = at or timezone.now()
    qs = room.attendances.filter(left_at__isnull=True)
    if session_sid:
        qs = qs.filter(session_sid=session_sid)
    closed = 0
    for attendance in qs:
        if attendance.source == VirtualRoomAttendance.SOURCE_WEBHOOK:
            recompute_attendance(attendance, finished_at=at)
        elif attendance.session_sid and room.events.filter(
                session_sid=attendance.session_sid, event__in=JOIN_EVENTS).exists():
            # Les webhooks fonctionnent pour cette séance, mais aucune entrée
            # de ce participant : il a demandé le lien sans jamais se
            # connecter. Sans ce cas, il recevait toute la durée de la réunion.
            attendance.left_at = attendance.joined_at
            attendance.duration_seconds = 0
            attendance.save(update_fields=["left_at", "duration_seconds"])
        else:
            attendance.left_at = max(at, attendance.joined_at)
            attendance.duration_seconds = int((attendance.left_at - attendance.joined_at).total_seconds())
            attendance.save(update_fields=["left_at", "duration_seconds"])
        closed += 1
    return closed


def end_meeting(room):
    """
    Ferme RÉELLEMENT la réunion côté plugNmeet, puis aligne FEBA.

    Si plugNmeet est injoignable, l'exception remonte : FEBA ne déclare pas
    terminée une réunion qui continue peut-être.
    """
    if provider() == "plugnmeet":
        plugnmeet.end_room(room)
    now = timezone.now()
    room.status = "ended"
    room.meeting_ended_at = now
    room.save(update_fields=["status", "meeting_ended_at", "updated_at"])
    close_open_attendances(room, at=now)
    return room


def record_api_leave(room, user):
    """
    Départ signalé par le navigateur. Les présences suivies par webhook ne
    sont PAS modifiées : l'événement de plugNmeet fait foi (un onglet fermé
    n'est pas forcément une sortie de la réunion, s'il en reste un autre).
    """
    attendance = (room.attendances.filter(user=user, left_at__isnull=True)
                  .order_by("-joined_at").first())
    if attendance is None or attendance.source == VirtualRoomAttendance.SOURCE_WEBHOOK:
        return attendance
    attendance.left_at = timezone.now()
    attendance.duration_seconds = int((attendance.left_at - attendance.joined_at).total_seconds())
    attendance.save(update_fields=["left_at", "duration_seconds"])
    return attendance


# ── Webhooks ──────────────────────────────────────────────────────────

def _event_time(event):
    raw = event.get("created_at")
    try:
        return datetime.fromtimestamp(int(raw), tz=dt_timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return timezone.now()


def _resolve_room(room_payload):
    """La salle FEBA d'un événement, y compris pour une salle de sous-groupe."""
    import json

    external_id = (room_payload or {}).get("room_id") or ""
    if not external_id:
        return None, external_id, False
    candidates = VirtualRoom.objects.filter(room_code=external_id)
    room = candidates.first()
    if room is None and len(external_id) == plugnmeet.MAX_ROOM_ID:
        # identifiant raccourci (room_code > 64 caractères)
        for candidate in VirtualRoom.objects.filter(room_code__startswith=external_id[:plugnmeet.MAX_ROOM_ID - 17]):
            if plugnmeet.room_id_for(candidate) == external_id:
                room = candidate
                break
    if room is not None:
        return room, external_id, False
    # Salle de SOUS-GROUPE : sa métadonnée désigne la salle principale. La
    # présence en sous-groupe est une présence au cours.
    try:
        metadata = json.loads((room_payload or {}).get("metadata") or "{}")
    except ValueError:
        metadata = {}
    parent = metadata.get("parent_room_id") or ""
    if parent:
        room = VirtualRoom.objects.filter(room_code=parent).first()
        if room is not None:
            return room, external_id, True
    return None, external_id, False


def handle_webhook(event):
    """
    Enregistre et applique un événement vérifié. Idempotent.
    Renvoie (VirtualRoomEvent | None, créé: bool).
    """
    from django.contrib.auth import get_user_model

    name = (event.get("event") or "").lower()
    event_id = event.get("id") or ""
    if not event_id:
        logger.warning("Webhook plugNmeet sans identifiant (%s) : ignoré.", name)
        return None, False
    if name not in STORED_EVENTS:
        return None, False
    if VirtualRoomEvent.objects.filter(event_id=event_id).exists():
        return VirtualRoomEvent.objects.get(event_id=event_id), False

    room, external_id, is_breakout = _resolve_room(event.get("room"))
    participant = event.get("participant") or {}
    identity = participant.get("identity") or ""
    user = None
    user_pk = plugnmeet.user_pk_from_identity(identity)
    if user_pk is not None and room is not None:
        # Uniquement un utilisateur de l'ACADÉMIE de la salle.
        user = get_user_model().objects.filter(pk=user_pk, school_id=room.school_id).first() or (
            get_user_model().objects.filter(pk=user_pk, role="superadmin").first())
    sid = ((event.get("room") or {}).get("sid") or "")
    if is_breakout and room is not None:
        sid = room.meeting_sid or sid  # rattachée à la réunion principale
    note = "salle de sous-groupe" if is_breakout else ""
    if room is None:
        note = "salle inconnue de FEBA"

    try:
        with transaction.atomic():
            record = VirtualRoomEvent.objects.create(
                event_id=event_id[:64], event=name[:40], room=room, external_room_id=external_id[:128],
                session_sid=sid[:64], identity=identity[:128], user=user,
                occurred_at=_event_time(event), payload=event, note=note,
            )
    except IntegrityError:  # même événement reçu en parallèle
        return VirtualRoomEvent.objects.get(event_id=event_id[:64]), False

    if room is None:
        return record, True

    if name == "room_started" and not is_breakout:
        _mark_meeting_started(room, sid, record.occurred_at)
    elif name == "room_finished" and not is_breakout:
        if room.meeting_sid in ("", sid) and room.status != "cancelled":
            room.status = "ended"
            room.meeting_ended_at = record.occurred_at
            room.save(update_fields=["status", "meeting_ended_at", "updated_at"])
        close_open_attendances(room, at=record.occurred_at, session_sid=sid)
    elif name in JOIN_EVENTS | LEAVE_EVENTS and user is not None and sid:
        attendance, _ = VirtualRoomAttendance.objects.get_or_create(
            room=room, user=user, session_sid=sid,
            defaults={"enrollment": _enrollment_for(user, room), "joined_at": record.occurred_at},
        )
        recompute_attendance(attendance)
    return record, True


def recompute_attendance(attendance, finished_at=None):
    """
    Recalcule entrée, sortie, durée et reconnexions à partir des événements.

    `finished_at` : fin de réunion — une présence encore ouverte est close à
    cette heure (déconnexion brutale sans événement de sortie).
    """
    events = list(
        VirtualRoomEvent.objects.filter(
            room=attendance.room, user=attendance.user, session_sid=attendance.session_sid,
            event__in=JOIN_EVENTS | LEAVE_EVENTS,
        ).order_by("occurred_at", "id")
    )
    if not events and finished_at is None:
        return attendance
    joins = 0
    first_join = None
    open_since = None
    last_left = None
    total = 0
    if events and events[0].event in LEAVE_EVENTS and events[0].occurred_at >= attendance.joined_at:
        # Événement d'ENTRÉE perdu (webhook refusé, plugNmeet a renoncé) :
        # la présence court depuis l'adhésion enregistrée par FEBA. Constaté
        # pendant l'essai réel ; sans ce repli, la durée valait 0.
        open_since = attendance.joined_at
        joins = 1
    for item in events:
        if item.event in JOIN_EVENTS:
            joins += 1
            first_join = first_join or item.occurred_at
            if open_since is None:
                open_since = item.occurred_at
        elif open_since is not None:  # sortie appariée à une entrée
            total += max(0, int((item.occurred_at - open_since).total_seconds()))
            open_since = None
            last_left = item.occurred_at
    if open_since is not None and finished_at is not None:
        total += max(0, int((finished_at - open_since).total_seconds()))
        open_since = None
        last_left = finished_at
    if first_join is not None:
        attendance.joined_at = first_join
    attendance.reconnections = max(0, joins - 1)
    attendance.source = VirtualRoomAttendance.SOURCE_WEBHOOK if events else attendance.source
    if open_since is None and (last_left or finished_at):
        attendance.left_at = last_left or finished_at
        attendance.duration_seconds = total if events else max(
            0, int((attendance.left_at - attendance.joined_at).total_seconds()))
    else:
        attendance.left_at = None
        attendance.duration_seconds = total or None
    attendance.save(update_fields=["joined_at", "left_at", "duration_seconds", "reconnections", "source"])
    return attendance


def reconcile_live_rooms():
    """
    Filet de sécurité : une salle « en cours » côté FEBA dont la réunion
    n'existe plus côté plugNmeet (webhook perdu, serveur redémarré) est
    déclarée terminée et ses présences sont closes. Une panne de plugNmeet
    ne termine RIEN : on ne conclut pas sur une absence de réponse.
    """
    if provider() != "plugnmeet" or not plugnmeet.is_configured():
        return 0
    ended = 0
    for room in VirtualRoom.objects.filter(status="live", is_active=True):
        try:
            active = plugnmeet.is_room_active(room)
        except plugnmeet.PlugNmeetUnavailable:
            logger.warning("Réconciliation des salles : plugNmeet injoignable, arrêt.")
            break
        except plugnmeet.PlugNmeetError as exc:
            logger.warning("Réconciliation de la salle %s impossible : %s", room.pk, exc)
            continue
        if not active:
            now = timezone.now()
            room.status = "ended"
            room.meeting_ended_at = room.meeting_ended_at or now
            room.save(update_fields=["status", "meeting_ended_at", "updated_at"])
            close_open_attendances(room, at=now)
            ended += 1
    return ended
