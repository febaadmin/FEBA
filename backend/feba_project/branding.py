"""
Source de vérité des identités officielles FEBA (V7).

Un seul endroit pour le nom officiel de l'école et le nom du groupe, réutilisé
par les modèles (valeurs par défaut), les seeders, les documents PDF
(bulletins, reçus) et l'API. Évite la duplication du nom en dur dans de
nombreux fichiers.

- OFFICIAL_SCHOOL_NAME : nom officiel EXACT (avec « & »).
- SCHOOL_GROUP_NAME    : entité de rattachement affichée sur les documents.
"""

OFFICIAL_SCHOOL_NAME = "Faith & Excellence Bilingual Academy"
SCHOOL_GROUP_NAME = "GROUPE ÉDUCATIF FEBA"
