"""
Audit de sûreté de `schools.0015_retire_legacy_institutional_phone`.

POURQUOI AUDITER UNE MIGRATION DÉJÀ APPLIQUÉE
---------------------------------------------
Cette migration réécrit des données. Elle a déjà tourné sur au moins une
base, et elle tournera sur toutes celles qui sont encore en 0014. On ne
peut donc plus la corriger « au cas où » : une migration modifiée après
application ne rejoue pas chez ceux qui l'ont déjà passée, et les deux
bases divergent en silence.

Ce qu'on peut faire, et qui manquait, c'est PROUVER ce qu'elle touche —
et surtout ce qu'elle NE touche PAS. Elle vise trois colonnes de `School`
(`phone`, `address`, `whatsapp`). Les mêmes noms de colonnes existent sur
les parents, les enseignants, les demandes d'inscription et les dossiers
FHA. Si le filtre avait été écrit un cran trop large, la migration aurait
réécrit des coordonnées de familles — irréversiblement, puisque son
inverse ne restaure rien.

Ces tests exécutent la vraie fonction de migration sur une base peuplée.
"""
from django.apps import apps as django_apps
from django.test import TestCase

from apps.schools.institution import OFFICIAL_PHONE, RETIRED_INSTITUTIONAL_PHONES
from apps.schools.models import School

RETIRED = RETIRED_INSTITUTIONAL_PHONES[0]


# Le nom du module commence par un chiffre : import explicite obligatoire.
def _load():
    import importlib
    return importlib.import_module(
        "apps.schools.migrations.0015_retire_legacy_institutional_phone")


class PerimetreDeLaMigrationTests(TestCase):
    """Ce que la migration touche, et ce qu'elle laisse strictement seul."""

    def _run(self):
        _load().retire_legacy_phone(django_apps, None)

    # ── Ce qu'elle DOIT corriger ─────────────────────────────────────────

    def test_le_numero_retire_est_remplace_sur_l_entite(self):
        ecole = School.objects.create(
            name="Test", code="T1", slug="t1", address="Cotonou",
            phone=RETIRED, currency_code="XOF")
        self._run()
        ecole.refresh_from_db()
        self.assertEqual(ecole.phone, OFFICIAL_PHONE)

    def test_le_numero_recopie_dans_l_adresse_est_retire(self):
        ecole = School.objects.create(
            name="Test", code="T2", slug="t2", currency_code="XOF",
            address=f"Akpakpa, Cotonou — Tél {RETIRED}")
        self._run()
        ecole.refresh_from_db()
        self.assertNotIn("96697363", ecole.address.replace(" ", ""))
        self.assertIn("Akpakpa", ecole.address)

    def test_le_whatsapp_hors_service_est_vide(self):
        ecole = School.objects.create(
            name="Test", code="T3", slug="t3", address="Cotonou",
            whatsapp=RETIRED, currency_code="XOF")
        self._run()
        ecole.refresh_from_db()
        self.assertEqual(ecole.whatsapp, "")

    # ── Ce qu'elle NE DOIT PAS toucher ───────────────────────────────────

    def test_un_numero_d_entite_legitime_est_conserve(self):
        ecole = School.objects.create(
            name="Test", code="T4", slug="t4", address="Cotonou",
            phone="+229 21 30 40 50", currency_code="XOF")
        self._run()
        ecole.refresh_from_db()
        self.assertEqual(ecole.phone, "+229 21 30 40 50")

    def test_une_colonne_vide_reste_vide(self):
        # La migration NE remplit PAS : elle retire. Remplir une colonne
        # vide serait inventer une donnée de gestion que personne n'a
        # saisie.
        ecole = School.objects.create(
            name="Test", code="T5", slug="t5", address="Cotonou",
            phone="", whatsapp="", currency_code="XOF")
        self._run()
        ecole.refresh_from_db()
        self.assertEqual(ecole.phone, "")
        self.assertEqual(ecole.whatsapp, "")

    def test_une_adresse_sans_numero_est_rendue_telle_quelle(self):
        adresse = "Akpakpa, Cotonou, Bénin"
        ecole = School.objects.create(
            name="Test", code="T6", slug="t6", address=adresse,
            currency_code="XOF")
        self._run()
        ecole.refresh_from_db()
        self.assertEqual(ecole.address, adresse)

    def test_aucune_coordonnee_personnelle_n_est_reecrite(self):
        """
        LE CONTRÔLE QUI COMPTE LE PLUS.

        Parents, enseignants, élèves et candidats portent les mêmes noms
        de colonnes que l'entité. On leur donne ici, délibérément, le
        numéro retiré : rien ne permet de supposer qu'une famille ne l'a
        pas légitimement, et la migration n'a aucune raison d'y toucher.
        Son inverse ne restaure rien : une réécriture serait définitive.
        """
        from apps.accounts.models import CustomUser
        from apps.website.models import ContactMessage, PreRegistration

        utilisateur = CustomUser.objects.create_user(
            username="parent-audit", email="parent-audit@test.bj",
            password="Pass1234!", role="parent", first_name="A",
            last_name="B", phone=RETIRED)
        prereg = PreRegistration.objects.create(
            parent_name="Famille Test", phone=RETIRED, whatsapp=RETIRED,
            email="f@test.bj", child_name="Enfant", desired_level="CM2")
        contact = ContactMessage.objects.create(
            name="Visiteur", email="v@test.bj", phone=RETIRED,
            subject="Question", message="Bonjour")

        self._run()

        utilisateur.refresh_from_db()
        prereg.refresh_from_db()
        contact.refresh_from_db()
        self.assertEqual(utilisateur.phone, RETIRED)
        self.assertEqual(prereg.phone, RETIRED)
        self.assertEqual(prereg.whatsapp, RETIRED)
        self.assertEqual(contact.phone, RETIRED)

    # ── Propriétés d'exécution ───────────────────────────────────────────

    def test_la_migration_est_idempotente(self):
        ecole = School.objects.create(
            name="Test", code="T7", slug="t7", phone=RETIRED,
            address=f"Cotonou — Tél {RETIRED}", currency_code="XOF")
        self._run()
        ecole.refresh_from_db()
        premier = (ecole.phone, ecole.address, ecole.whatsapp)

        self._run()
        self._run()
        ecole.refresh_from_db()
        self.assertEqual((ecole.phone, ecole.address, ecole.whatsapp), premier)

    def test_elle_traverse_une_base_vide_sans_erreur(self):
        School.objects.all().delete()
        self._run()  # ne doit pas lever

    def test_l_inverse_ne_restaure_pas_le_numero_hors_service(self):
        ecole = School.objects.create(
            name="Test", code="T8", slug="t8", address="Cotonou",
            phone=RETIRED, currency_code="XOF")
        module = _load()
        module.retire_legacy_phone(django_apps, None)
        module.noop(django_apps, None)
        ecole.refresh_from_db()
        self.assertEqual(ecole.phone, OFFICIAL_PHONE)


class DeclarationDeLaMigrationTests(TestCase):
    """La migration reste bien branchée sur l'historique attendu."""

    def test_elle_suit_la_0014_et_reste_reversible(self):
        module = _load()
        self.assertEqual(
            module.Migration.dependencies,
            [("schools", "0014_remove_school_currency_school_currency_code_and_more")])
        operation = module.Migration.operations[0]
        # Un `reverse_code` absent rendrait tout `migrate` descendant
        # impossible, y compris pour revenir d'un déploiement raté.
        self.assertIsNotNone(operation.reverse_code)
