"""
Identités d'académie fabriquées pour les tests de mise en page.

Les tests de mise en page (débordement, cachet, pagination) n'ont pas
besoin de la base : ils appellent directement les constructeurs de PDF.
Il leur faut en revanche une identité d'académie complète, puisque c'est
désormais elle — et non plus des constantes de module — qui fournit nom,
couleurs, cachet et pied de page.

Ces valeurs sont des DONNÉES DE TEST déclarées ici explicitement. Aucun
test ne dépend d'un repli implicite du code de production : c'est
précisément le repli implicite que P0 a supprimé.
"""
import os

from apps.schools.branding import STATIC_FILES_DIR, AcademyBranding


def _asset(filename):
    path = os.path.join(STATIC_FILES_DIR, filename)
    return path if os.path.exists(path) else None


def make_branding(**overrides) -> AcademyBranding:
    """Identité d'académie complète, surchargeable champ par champ."""
    base = dict(
        academy_id=1,
        academy_code="FEBA",
        legal_name="Faith & Excellence Bilingual Academy",
        display_name="Faith & Excellence Bilingual Academy",
        short_name="FEBA",
        group_name="GROUPE ÉDUCATIF FEBA",
        logo=_asset("logo_feba.jpeg"),
        document_logo=_asset("logo_feba.jpeg"),
        stamp=_asset("cachet_feba.png"),
        director_signature=_asset("signature_direction.png"),
        secretary_stamp=_asset("cachet_secretariat.png"),
        primary_color="#071D49",
        secondary_color="#0E2A63",
        accent_color="#D89B16",
        background_color="#F7F2E8",
        postal_address="Akpakpa, Cotonou",
        city="Cotonou",
        country="Bénin",
        phone="",
        whatsapp="",
        email="",
        website="",
        currency_code="XOF",
        currency_symbol="FCFA",
        locale="fr-BJ",
        language="fr",
        timezone="Africa/Porto-Novo",
        footer_text="Faith & Excellence Bilingual Academy — Akpakpa, Cotonou, Bénin",
        document_prefix="FEBA",
    )
    base.update(overrides)
    return AcademyBranding(**base)


def make_fha_branding(**overrides) -> AcademyBranding:
    """Identité de l'académie en ligne — distincte sur chaque champ testé."""
    defaults = dict(
        academy_id=2,
        academy_code="FEBA_FHA",
        legal_name="FEBA French Heritage Academy",
        display_name="FEBA French Heritage Academy",
        short_name="FEBA FHA",
        secondary_color="#1F6B36",
        background_color="#FFFFFF",
        postal_address="Programme 100 % en ligne",
        city="",
        country="",
        whatsapp="+1 (215) 715-5406",
        currency_code="USD",
        currency_symbol="$",
        locale="en-US",
        language="en",
        timezone="America/New_York",
        footer_text="FEBA French Heritage Academy — programme en ligne pour la diaspora",
        document_prefix="FHA",
    )
    defaults.update(overrides)
    return make_branding(**defaults)


def make_palette(**overrides):
    """`Palette` de bulletin construite sur une identité fabriquée."""
    from apps.bulletins.pdf_generator import Palette
    return Palette(make_branding(**overrides))
