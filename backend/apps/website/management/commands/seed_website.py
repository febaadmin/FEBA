"""
Contenu par défaut du site vitrine (idempotent).

Charge : paramètres (identité réelle FEBA issue de la charte), 5 slides du
carrousel et les albums de la galerie — tous construits à partir des VRAIS
médias fournis (frontend/public/site/, voir MEDIA_INVENTORY.md).

NE CRÉE AUCUNE donnée fictive : pas de fausses actualités, pas de faux
chiffres, pas de coordonnées inventées (téléphone/email restent vides tant
que l'administration ne les a pas renseignés — le site masque ces blocs).

Usage : python manage.py seed_website
"""
from django.core.management.base import BaseCommand

from apps.website.models import (
    SiteSettings, HeroSlide, GalleryAlbum, GalleryItem,
)

IMG = "/site/img/{}-1600.webp"

# Points focaux (V5) : position du sujet principal de chaque visuel, en %
# (object-position). Modifiables ensuite depuis l'admin sans toucher au code.
HERO_SLIDES = [
    {
        "order": 1, "title": "Bienvenue à FEBA",
        "subtitle": "Faith & Excellence Bilingual Academy — école bilingue à Akpakpa, Cotonou.",
        "cta_label": "Découvrir l'école", "cta_url": "/a-propos",
        # V6.1 : bâtiment principal avec panneau « Faith & Excellence » lisible.
        "image_path": IMG.format("campus-logo"),
        "focal_x": 50, "focal_y": 48,
    },
    {
        "order": 2, "title": "Grandir dans l'excellence",
        "subtitle": "Un encadrement de qualité, des valeurs et un suivi personnalisé.",
        "cta_label": "Nos programmes", "cta_url": "/academique",
        "image_path": IMG.format("hero-excellence"),
        "focal_x": 50, "focal_y": 38,
    },
    {
        "order": 3, "title": "Français et anglais au quotidien",
        "subtitle": "Un enseignement bilingue dès le plus jeune âge.",
        "cta_label": "Le bilinguisme à FEBA", "cta_url": "/academique",
        "image_path": IMG.format("hero-bilingue"),
        "focal_x": 50, "focal_y": 38,
    },
    {
        # Ronde d'enfants en bas de l'image, grande zone crème en haut :
        # le focal descend le cadrage pour garder le groupe entier visible.
        "order": 4, "title": "Apprendre, grandir et s'épanouir",
        "subtitle": "Musique, arts, sport et jeux éducatifs dans un cadre sécurisé.",
        "cta_label": "La vie à FEBA", "cta_url": "/vie-scolaire",
        "image_path": IMG.format("hero-vie-scolaire"),
        "focal_x": 55, "focal_y": 78,
    },
    {
        # Famille accueillie à droite, crème à gauche : le texte du slide
        # occupe la zone libre (gauche), le focal protège la scène.
        "order": 5, "title": "Admissions ouvertes",
        "subtitle": "Rejoignez la famille FEBA : la préinscription ne prend que quelques minutes.",
        "cta_label": "Inscrire mon enfant", "cta_url": "/admissions",
        "image_path": IMG.format("hero-admissions"),
        "focal_x": 72, "focal_y": 45,
    },
]

# Point focal des médias de la galerie, par slug packagé (défaut : 50/50).
GALLERY_FOCALS = {
    "academique-participation": (26, 64),  # V6 : enseignante en bas-gauche (pas le mur crème)
    "academique-classe": (50, 35),
    "valeurs-projet": (50, 40),
    "activite-ronde": (72, 62),
    "campus-cour": (50, 74),
    "academique-carte": (50, 35),
    "niveau-primaire": (50, 30),
    "niveau-primaire-lecture": (50, 36),
    "academique-lecture": (50, 42),
    "academique-bibliotheque": (50, 40),
    "academique-sciences": (50, 40),
    "academique-numerique": (50, 42),
    # V6.1 — recadrages individuels (sujets décentrés / trop bas + fond crème)
    "galerie-ecriture": (66, 46),   # 2 élèves à droite, crème à gauche
    "galerie-etude": (66, 46),      # 2 élèves à droite, crème à gauche
    "galerie-devoirs": (50, 66),    # portrait : élèves en bas, mur crème en haut
    "galerie-soutien": (50, 68),    # portrait : trio en bas, mur crème en haut
    "accompagnement-duo": (52, 64), # trio centré, grand mur crème en haut
    "activite-musique-groupe": (50, 40),
    "activite-musique-atelier": (58, 45),
    "activite-musique-scene": (50, 42),
    "activite-percussions": (50, 45),
    "activite-arts": (50, 38),
    "activite-football": (50, 45),
    "activite-football-cour": (50, 45),
    "activite-expression": (45, 32),
    "activite-ronde": (62, 72),
    "niveau-maternelle-cour": (50, 60),
    "hero-campus": (50, 55),
    "campus-batiment": (50, 55),
    "campus-facade": (50, 45),
    "campus-garderie-maternelle": (50, 58),
    "campus-cour": (50, 74),
    "niveau-garderie": (50, 42),
    "niveau-garderie-jeux": (50, 45),
    "niveau-maternelle": (50, 42),
    "online-visio": (45, 45),
    "online-cours-francais": (62, 48),
    "online-lecon": (42, 45),
    "valeurs-equipe": (50, 32),
    "valeurs-projet": (50, 35),
    "galerie-projet": (50, 38),
    "apropos-equipe": (50, 32),
    # V6.1 — nouveaux médias fournis
    "campus-logo": (50, 48),               # bâtiment principal + panneau logo
    "campus-fresque": (50, 52),            # (V6.1 — non retenu en V6.2)
    "petite-enfance-creche": (50, 52),     # crèche : lits + tout-petits
    "apropos-equipe-pedagogique": (50, 38),# équipe (7 personnes), visages hauts
    # V6.2 — « Bonne image » validées + photo directeur restaurée
    "campus-facade-logo": (50, 48),        # façade FEBA logo + fresques
    "campus-devise": (50, 50),             # façade « Here will change the world »
    "apropos-direction-2": (50, 30),       # directeur au bureau (carte « La direction »)
}

ALBUMS = [
    ("Vie de classe", "Apprentissages quotidiens, lecture et travaux de groupe.", [
        ("academique-classe", "Cours en classe"),
        ("academique-carte", "Découverte du monde"),
        ("academique-participation", "Participation en classe"),
        ("niveau-primaire", "Travail en primaire"),
        ("niveau-primaire-lecture", "Lecture en classe"),
        ("academique-lecture", "Lecture accompagnée"),
        ("academique-bibliotheque", "À la bibliothèque"),
        ("academique-sciences", "Atelier sciences"),
        ("academique-numerique", "Initiation au numérique"),
        ("galerie-ecriture", "Travaux d'écriture"),
        ("galerie-etude", "Temps d'étude"),
        ("galerie-devoirs", "Devoirs en classe"),
        ("galerie-soutien", "Soutien individualisé"),
        ("accompagnement-duo", "Accompagnement personnalisé"),
    ]),
    ("Activités et épanouissement", "Musique, arts, sport et expression.", [
        ("activite-musique-groupe", "Groupe de musique"),
        ("activite-musique-atelier", "Atelier musique"),
        ("activite-musique-scene", "Répétition musicale"),
        ("activite-percussions", "Percussions et héritage culturel"),
        ("activite-arts", "Arts plastiques"),
        ("activite-football", "Football"),
        ("activite-football-cour", "Sport dans la cour"),
        ("activite-expression", "Expression orale"),
        ("activite-ronde", "Jeux dans la cour"),
        ("niveau-maternelle-cour", "Marelle en maternelle"),
    ]),
    # V6.2 — cartes « Bonne image » validées d'après les captures annotées :
    # campus-facade (« Façade de l'école ») et campus-fresque (« Façade aux
    # fresques ») étaient « Mauvaise image » → retirées ; on utilise la façade
    # au logo/fresques et la façade à la devise. Ordre identique au fallback.
    ("Notre campus", "Les espaces de l'école à Akpakpa.", [
        ("campus-logo", "Le bâtiment principal"),
        ("campus-facade-logo", "Façade FEBA — logo et fresques"),
        ("campus-devise", "La devise de l'école"),
        ("campus-cour", "La cour de récréation"),
    ]),
    ("Petite enfance", "Garderie et maternelle : éveil et jeux éducatifs.", [
        ("petite-enfance-creche", "La crèche FEBA"),
        ("niveau-garderie", "Éveil en garderie"),
        ("niveau-garderie-jeux", "Jeux de construction"),
        ("niveau-maternelle", "Activités en maternelle"),
    ]),
    ("FEBA Online", "Cours en ligne pour les enfants de la diaspora.", [
        ("online-visio", "Cours en visioconférence"),
        ("online-cours-francais", "Cours de français en ligne"),
        ("online-lecon", "Leçon interactive"),
    ]),
    ("Moments FEBA", "Instantanés de la vie de l'école.", [
        # V6 : valeurs-projet retiré (désormais carte de niveau CM1·CM2).
        # V6.1 : galerie-mosaique-3 (« Mosaïque de l'école ») retirée — elle
        # incrustait un portrait de bureau désormais banni du site.
        ("valeurs-equipe", "Esprit d'équipe"),
        ("galerie-projet", "Travail de groupe"),
        ("apropos-equipe", "L'équipe pédagogique"),
        ("admissions-visite", "Accueil des familles"),
        ("galerie-mosaique-1", "Mosaïque de la vie scolaire"),
        ("galerie-mosaique-2", "Mosaïque des apprentissages"),
    ]),
]


class Command(BaseCommand):
    help = "Contenu par défaut du site vitrine (idempotent, aucune donnée fictive)."

    def handle(self, *args, **options):
        SiteSettings.load()  # crée la ligne de paramètres avec l'identité réelle
        self.stdout.write("✅ Paramètres du site (identité FEBA, coordonnées à compléter)")

        for data in HERO_SLIDES:
            HeroSlide.objects.update_or_create(
                order=data["order"], defaults={**data, "is_active": True},
            )
        self.stdout.write(f"✅ {len(HERO_SLIDES)} slides du carrousel")

        for order, (title, description, items) in enumerate(ALBUMS, start=1):
            album, _ = GalleryAlbum.objects.update_or_create(
                title=title,
                defaults={"description": description, "order": order, "is_active": True},
            )
            wanted_paths = []
            for i, (slug, caption) in enumerate(items, start=1):
                fx, fy = GALLERY_FOCALS.get(slug, (50, 50))
                path = f"/site/img/{slug}-800.webp"
                wanted_paths.append(path)
                GalleryItem.objects.update_or_create(
                    album=album, image_path=path,
                    defaults={
                        "kind": "image", "caption": caption, "alt_text": caption,
                        "order": i, "is_active": True,
                        "focal_x": fx, "focal_y": fy,
                    },
                )
            # V6 : élagage — retire les images qui ne font plus partie de la
            # définition de l'album (ex. doublons supprimés en V6), en
            # préservant la vidéo institutionnelle (kind="video").
            pruned, _ = album.items.filter(kind="image").exclude(
                image_path__in=wanted_paths,
            ).delete()
            note = f" (−{pruned} obsolète·s)" if pruned else ""
            self.stdout.write(f"✅ Album « {title} » ({len(items)} médias){note}")

        # Vidéo institutionnelle dans l'album Moments FEBA (chargée au clic).
        moments = GalleryAlbum.objects.get(title="Moments FEBA")
        GalleryItem.objects.update_or_create(
            album=moments, kind="video",
            video_url="/site/video/feba-presentation.mp4",
            defaults={
                "caption": "FEBA en vidéo",
                "alt_text": "Vidéo de présentation de l'école",
                "image_path": "/site/video/feba-presentation-poster.webp",
                "order": 99, "is_active": True,
            },
        )
        self.stdout.write("✅ Vidéo de présentation (affiche + lecture à la demande)")
        self.stdout.write(self.style.SUCCESS("Site vitrine : contenu par défaut en place."))
