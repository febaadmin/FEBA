"""
apps/website/private_storage.py — Racine du stockage privé des fiches FHA.

Les fiches d'inscription contiennent l'adresse, le téléphone, la photo et
les besoins particuliers d'un mineur. Elles ne vont JAMAIS dans
`MEDIA_ROOT` : ce répertoire est servi statiquement, et une URL devinée ou
partagée suffirait à les exposer. Elles vont dans `PRIVATE_MEDIA_ROOT`, que
le serveur web ne publie pas, et ne sortent que par une vue authentifiée
qui vérifie l'académie du demandeur.
"""
import os

from django.conf import settings


def private_root():
    return getattr(
        settings, "PRIVATE_MEDIA_ROOT",
        os.path.join(settings.BASE_DIR, "private_media"),
    )


def fha_sheet_root():
    return os.path.join(private_root(), "fha_applications")


def prereg_sheet_root():
    """
    P2 — Racine des fiches de préinscription FEBA.

    Répertoire distinct de celui des fiches FHA : deux académies, deux
    jeux de dossiers. Un même répertoire aurait suffi techniquement, mais
    la séparation rend une erreur de portée VISIBLE sur le disque au lieu
    de la laisser dépendre d'un filtre en base.
    """
    return os.path.join(private_root(), "feba_preregistrations")


def private_storage():
    """
    Stockage de fichiers HORS du répertoire servi publiquement.

    Passé en CALLABLE à `storage=` : Django n'inscrit alors pas le chemin
    absolu dans une migration, et le même code fonctionne sur une machine
    de développement comme en production, où les chemins diffèrent.
    """
    from django.core.files.storage import FileSystemStorage

    return FileSystemStorage(location=private_root())
