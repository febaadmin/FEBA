"""
P2 — Aucun champ saisi ne reste invisible.

Le test le plus utile de cette itération, et le plus court. Il fait tourner
l'audit et refuse le moindre champ accepté par un formulaire public que
l'administration ne relit pas.

C'est la seule protection qui survit à la prochaine évolution : ajouter un
champ au modèle et au formulaire sans l'ajouter au serializer est une
omission d'une ligne, invisible en revue, invisible à l'écran, et
définitive pour la donnée. C'est exactement ce qui est arrivé au numéro
WhatsApp.
"""
from django.test import SimpleTestCase

from apps.core.management.commands.field_mapping_audit import (
    AUDITS, DELIBERATE_OMISSIONS,
)


class FieldMappingAuditTests(SimpleTestCase):

    def test_aucun_champ_saisi_n_est_perdu(self):
        problems = []
        for audit in AUDITS:
            title, rows, _ = audit()
            for row in rows:
                if row["write"] and not row["read"] and not row["note"]:
                    problems.append(
                        f"{title} · « {row['field']} » est accepté par le "
                        f"formulaire public mais n'est relu nulle part : la "
                        f"donnée entre en base et n'en ressort jamais."
                    )
        self.assertEqual(problems, [], "\n".join(problems))

    def test_le_whatsapp_traverse_toute_la_chaine(self):
        """Le champ par lequel le défaut a été signalé."""
        for audit in AUDITS:
            title, rows, _ = audit()
            for row in rows:
                if "whatsapp" not in row["field"]:
                    continue
                with self.subTest(formulaire=title, champ=row["field"]):
                    self.assertTrue(row["write"], "non accepté à la saisie")
                    self.assertTrue(row["read"], "non relu par l'administration")
                    self.assertTrue(row["export"], "absent de l'export")

    def test_chaque_omission_est_motivee(self):
        """
        Une omission sans raison écrite est une omission oubliée.

        Le dictionnaire des omissions délibérées sert à distinguer un choix
        d'un défaut. Une entrée vide ferait passer un défaut pour un choix.
        """
        for field, reason in DELIBERATE_OMISSIONS.items():
            with self.subTest(champ=field):
                self.assertTrue(reason.strip(),
                                f"« {field} » est exclu sans raison écrite.")

    def test_les_besoins_particuliers_restent_lisibles_par_l_administration(self):
        """Donnée sensible, mais qui doit atteindre celui qui décide."""
        from apps.core.management.commands.field_mapping_audit import (
            audit_fha_enrollment,
        )

        _title, rows, _ = audit_fha_enrollment()
        row = next(r for r in rows if r["field"] == "special_needs")
        self.assertTrue(row["write"])
        self.assertTrue(row["read"])
        # Absent de la LISTE, à dessein : une donnée de santé d'un mineur
        # n'a pas à s'afficher dans un tableau que tout le monde survole.
        self.assertFalse(row["list"])

    def test_chaque_champ_saisi_de_la_preinscription_sort_dans_l_export(self):
        """
        P2 — Un champ que la famille remplit doit se retrouver dans le CSV.

        L'export est la seule sortie exploitable hors de l'application :
        un champ absent du CSV est un champ que le secrétariat ne peut ni
        trier, ni transmettre, ni archiver. Ce test lit les colonnes
        RÉELLEMENT écrites par l'export, pas l'intention du serializer.
        """
        for audit in AUDITS:
            title, rows, _ = audit()
            if "Préinscription" not in title:
                continue
            for row in rows:
                if not row["write"] or row["note"]:
                    continue
                with self.subTest(champ=row["field"]):
                    self.assertTrue(
                        row["export"],
                        f"« {row['field'] } » est saisi par la famille mais "
                        f"n'apparaît pas dans l'export CSV.",
                    )

    def test_l_export_ne_publie_aucun_chemin_de_fichier_serveur(self):
        """
        Un chemin de stockage privé ou une empreinte dans un tableur
        diffusé n'aide personne et renseigne un attaquant sur
        l'arborescence du serveur.
        """
        from apps.website.views import _prereg_export_columns

        exportees = {key for _, key in _prereg_export_columns()}
        for interdit in ("sheet_path", "sheet_sha256"):
            self.assertNotIn(interdit, exportees)
