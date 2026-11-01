"""
Classement des académies EXISTANTES par type — règle unique, sans base.

Utilisée par la migration `schools.0020` et par la commande
`academy_types_report`. Fonction pure : elle ne reçoit que des faits
(type d'entité, cycles des niveaux) et ne devine jamais.

  * académie en ligne                         → « online » ;
  * présentielle, niveaux maternelle/primaire → « physical_primary » ;
  * présentielle, niveaux collège/lycée       → « physical_secondary » ;
  * présentielle SANS niveau, ou mêlant primaire et secondaire
                                              → non classée (None), avec
                                                le motif.
"""
PRIMARY = frozenset({"maternelle", "primaire"})
SECONDARY = frozenset({"college", "lycee"})


def classify(entity_type, cycles):
    """Retourne (academy_type | None, motif lisible)."""
    cycles = {str(c).strip().lower() for c in cycles if c}
    if entity_type == "online":
        return "online", "académie en ligne"
    if not cycles:
        return None, "aucun niveau : impossible de savoir si l'enseignement est primaire ou secondaire"
    if cycles <= PRIMARY:
        return "physical_primary", "niveaux de maternelle / primaire uniquement"
    if cycles <= SECONDARY:
        return "physical_secondary", "niveaux de collège / lycée uniquement"
    return None, (
        "niveaux de primaire ET de secondaire (" + ", ".join(sorted(cycles)) + ") : "
        "aucun des trois types ne les couvre tous, classement à décider par le super administrateur"
    )
