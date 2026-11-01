#!/usr/bin/env python3
"""
Applique traductions-fr.json (« chemin.de.la.cle » -> texte) à la traduction
française du client plugNmeet. Sans effet sur les clés absentes du client : une
nouvelle version du client ne se retrouve pas avec des clés inventées.

    appliquer_traductions.py traductions-fr.json .../fr-FR/translation.json
"""
import json
import sys


def main(source, cible):
    with open(source, encoding="utf-8") as f:
        corrections = json.load(f)
    with open(cible, encoding="utf-8") as f:
        traduction = json.load(f)
    appliquees = 0
    for cle, texte in corrections.items():
        noeud = traduction
        parties = cle.split(".")
        for partie in parties[:-1]:
            noeud = noeud.get(partie) if isinstance(noeud, dict) else None
        if isinstance(noeud, dict) and parties[-1] in noeud:
            noeud[parties[-1]] = texte
            appliquees += 1
    with open(cible, "w", encoding="utf-8") as f:
        json.dump(traduction, f, ensure_ascii=False, indent=2)
    print(f"{appliquees}/{len(corrections)} traductions appliquées")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
