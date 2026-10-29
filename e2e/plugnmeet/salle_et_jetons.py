"""
Salle et jetons plugNmeet produits par le code FEBA (apps.virtualclass.plugnmeet),
pour le test navigateur deux-participants.mjs. Aucune écriture en base FEBA :
la salle et l'académie sont des instances non enregistrées.

    PLUGNMEET_TEST_URL     URL de l'API, vue depuis ce processus
    PLUGNMEET_PUBLIC_URL   URL du client, vue depuis le navigateur (défaut : TEST_URL)
    PLUGNMEET_TEST_KEY / PLUGNMEET_TEST_SECRET
    FEBA_PUBLIC_URL        base du retour en fin de réunion (logout_url)

    python salle_et_jetons.py          → JSON {room_id, enseignant, eleve}
    python salle_et_jetons.py --fin    → JSON {actif_avant, end_room, actif_apres}

Les jetons sont à usage unique : relancer pour chaque essai.
"""
import json
import os
import sys
import types

import django

django.setup()

from django.test.utils import override_settings  # noqa: E402

from apps.schools.models import School  # noqa: E402
from apps.virtualclass import plugnmeet  # noqa: E402
from apps.virtualclass.models import VirtualRoom  # noqa: E402

ROOM_CODE = os.environ.get("PNM_E2E_ROOM_CODE", "feba-essai-e2e-plugnmeet-0000000001")


def participant(pk, nom, role):
    user = types.SimpleNamespace(pk=pk, username=nom, role=role)
    user.get_full_name = lambda: nom
    return user


with override_settings(
    PLUGNMEET_SERVER_URL=os.environ.get("PLUGNMEET_PUBLIC_URL") or os.environ["PLUGNMEET_TEST_URL"],
    PLUGNMEET_INTERNAL_URL=os.environ["PLUGNMEET_TEST_URL"],
    PLUGNMEET_API_KEY=os.environ["PLUGNMEET_TEST_KEY"],
    PLUGNMEET_API_SECRET=os.environ["PLUGNMEET_TEST_SECRET"],
    PLUGNMEET_WEBHOOK_URL="",
    PUBLIC_BASE_URL=os.environ.get("FEBA_PUBLIC_URL", "http://localhost:18000"),
):
    room = VirtualRoom(pk=990001, room_code=ROOM_CODE, name="Essai E2E plugNmeet",
                       description="Test automatisé", lobby_enabled=False)
    room.school = School(pk=990, name="FEBA Essai", code="FEBA", slug="feba")

    if "--fin" in sys.argv:
        avant = plugnmeet.is_room_active(room)
        json.dump({"actif_avant": avant, "end_room": plugnmeet.end_room(room),
                   "actif_apres": plugnmeet.is_room_active(room)}, sys.stdout)
    else:
        plugnmeet.create_room(room)
        out = {"room_id": plugnmeet.room_id_for(room)}
        for cle, (user, admin) in {"enseignant": (participant(990101, "Prof Essai", "teacher"), True),
                                   "eleve": (participant(990201, "Élève Essai", "student"), False)}.items():
            out[cle] = plugnmeet.join_url(plugnmeet.join_token(room, user, is_admin=admin))
        json.dump(out, sys.stdout)
