#!/usr/bin/env python3
"""
Remplace le seul tiret cadratin affiché que le client plugNmeet code en dur :
le titre de l'état de connexion. Sans effet si le texte n'y est plus.

    retirer_tiret_client.py .../assets/js/main-module.*.js
"""
import sys

AVANT = "${t?` \u2014 ${t}`:``}"
APRES = "${t?` - ${t}`:``}"


def main(chemin):
    with open(chemin, encoding="utf-8") as f:
        contenu = f.read()
    print(f"{contenu.count(AVANT)} remplacement(s) dans {chemin}")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu.replace(AVANT, APRES))


if __name__ == "__main__":
    main(sys.argv[1])
