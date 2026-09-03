"""
tests/repo_root.py — où est la racine du dépôt, vue depuis un test.

POURQUOI CE MODULE EXISTE
-------------------------
Une partie des tests ne vérifie pas du code applicatif mais des FICHIERS
DE LIVRAISON : `.env.dev.example` doit pointer Mailpit, le Makefile doit
exposer ses cibles d'exploitation, `docker-compose.jitsi.prod.yml` doit
imposer l'authentification. Ces fichiers vivent à la racine du dépôt, un
niveau au-dessus de `backend/`.

Or `backend/` n'est pas toujours monté au même endroit. Dans le conteneur
de développement, `./backend` est monté sur `/app` et la racine du dépôt
n'existe tout simplement pas. Cinq fichiers de tests s'étaient chacun
débrouillés à leur façon :

    test_env_dev_email_config.py   parent.parent.parent, puis skipTest
    test_jitsi_production_domain.py  dirname × 3, puis échec brut
    test_production_settings.py    skipUnless(os.path.exists(...))
    test_diploma_ready_after_install.py  dirname × 3
    test_academy_identity_separation.py  remontée + montage dédié

Cinq réponses différentes à une seule question, et deux d'entre elles
répondaient en SE TAISANT. C'est le pire des deux mondes : dans le
conteneur, `pytest` affichait « 4 skipped » — vert à l'œil — alors
qu'aucune des garanties n'avait été vérifiée. Un `.env.dev.example`
revenu au backend console serait passé inaperçu.

CE QUE CE MODULE GARANTIT
-------------------------
Une seule résolution, trois chemins indépendants, et JAMAIS de silence :
si la racine est introuvable, les tests ÉCHOUENT avec un message qui dit
quoi faire. Un fichier de configuration non vérifié est un défaut, pas une
condition d'exécution acceptable.

LES TROIS CHEMINS
-----------------
1. `FEBA_REPO_ROOT` — renseigné par `docker-compose.yml` (voir le service
   `backend-dev`, qui monte le dépôt en lecture seule sur `/repo`). C'est
   le cas du conteneur, celui qui échouait.
2. Remontée de l'arborescence depuis ce fichier, jusqu'à trouver un
   répertoire qui PORTE LES MARQUEURS du dépôt. Couvre le checkout Git
   normal et GitHub Actions, sans aucune configuration.
3. `/repo`, la convention du conteneur, si la variable n'a pas été
   transmise (`docker compose run` sans le fichier d'environnement, par
   exemple).

Aucun chemin absolu propre à une machine n'apparaît ici, et aucun n'est
requis : le chemin 2 suffit à lui seul hors conteneur.
"""
from __future__ import annotations

import os
from pathlib import Path

#: Variable renseignée par docker-compose.yml pour le conteneur backend.
ENV_VAR = "FEBA_REPO_ROOT"

#: Point de montage conventionnel du dépôt dans le conteneur.
CONTAINER_MOUNT = "/repo"

#: Ce qui identifie la racine du dépôt, et rien d'autre.
#:
#: On ne teste PAS la présence de `Makefile` ou de `.git` : le premier est
#: justement l'un des fichiers dont les tests vérifient le contenu (le
#: marqueur disparaîtrait avec ce qu'il sert à trouver), et le second est
#: absent d'une archive extraite ou d'un export de livraison — deux
#: situations parfaitement légitimes.
MARKERS = (
    Path("backend") / "manage.py",
    Path("frontend") / "package.json",
)


def _is_repo_root(candidate: Path) -> bool:
    return all((candidate / marker).exists() for marker in MARKERS)


def find_repo_root() -> Path | None:
    """Racine du dépôt, ou None si elle n'est atteignable par aucun chemin."""
    declared = os.environ.get(ENV_VAR, "").strip()
    if declared:
        candidate = Path(declared)
        if _is_repo_root(candidate):
            return candidate

    here = Path(__file__).resolve()
    for candidate in here.parents:
        if _is_repo_root(candidate):
            return candidate

    mount = Path(CONTAINER_MOUNT)
    if _is_repo_root(mount):
        return mount

    return None


#: Message d'échec. Il nomme la cause ET le geste — un test qui dit
#: seulement « fichier introuvable » fait chercher au mauvais endroit.
UNREACHABLE = (
    "La racine du dépôt est introuvable depuis ce test.\n"
    "\n"
    "Ces tests vérifient des fichiers de LIVRAISON situés au-dessus de "
    "backend/ (.env.*.example, Makefile, docker-compose*.yml, scripts/). "
    "Ils ne peuvent pas être ignorés : c'est précisément quand ces "
    "fichiers deviennent invisibles qu'une régression de configuration "
    "passe inaperçue.\n"
    "\n"
    "Chemins essayés :\n"
    f"  1. ${ENV_VAR} (renseigné par docker-compose.yml)\n"
    "  2. remontée depuis backend/tests/ (checkout Git, GitHub Actions)\n"
    f"  3. {CONTAINER_MOUNT} (montage du conteneur)\n"
    "\n"
    "Dans le conteneur, le service backend-dev doit monter le dépôt :\n"
    f"    - .:{CONTAINER_MOUNT}:ro\n"
    f"    environment: {ENV_VAR}={CONTAINER_MOUNT}\n"
    "Relancez « docker compose up -d --force-recreate backend-dev » après "
    "toute modification de docker-compose.yml."
)


def repo_root() -> Path:
    """
    Racine du dépôt. Lève `AssertionError` si elle est introuvable.

    Volontairement bloquant, et volontairement une AssertionError : un
    test qui ne peut pas lire le fichier qu'il surveille doit ÉCHOUER,
    jamais être ignoré. Un « skipped » se lit comme un succès dans un
    tableau de résultats.
    """
    root = find_repo_root()
    if root is None:
        raise AssertionError(UNREACHABLE)
    return root


def repo_file(*parts) -> Path:
    """
    Chemin d'un fichier de livraison, depuis la racine du dépôt.

    Ne vérifie pas son existence : c'est au test de dire ce qu'il attend,
    avec son propre message. Ce module répond à « où est la racine », pas
    à « ce fichier est-il correct ».
    """
    return repo_root().joinpath(*parts)


def read_repo_file(*parts, encoding="utf-8") -> str:
    """Contenu d'un fichier de livraison."""
    path = repo_file(*parts)
    if not path.exists():
        raise AssertionError(
            f"{path} est introuvable alors que la racine du dépôt a bien "
            f"été résolue ({repo_root()}). Le fichier manque réellement de "
            "la livraison."
        )
    return path.read_text(encoding=encoding)


def parse_env_file(*parts) -> dict:
    """
    Affectations `CLE=valeur` d'un fichier .env, commentaires exclus.

    Les commentaires sont écartés à dessein : ces fichiers EXPLIQUENT
    pourquoi certaines valeurs sont proscrites (les instances Jitsi
    publiques, par exemple) et doivent continuer de le faire. C'est la
    valeur affectée qui engage, pas le sujet abordé.
    """
    values = {}
    for line in read_repo_file(*parts).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values
