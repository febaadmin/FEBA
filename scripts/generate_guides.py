#!/usr/bin/env python3
"""Génère les deux guides PDF (installation locale + déploiement production)."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle, PageBreak,
)

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1x", parent=styles["Heading1"], textColor=colors.HexColor("#1e3a8a"), spaceBefore=18)
H2 = ParagraphStyle("H2x", parent=styles["Heading2"], textColor=colors.HexColor("#1d4ed8"), spaceBefore=14)
BODY = ParagraphStyle("Bodyx", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=6)
CODE = ParagraphStyle("Codex", parent=styles["Code"], fontSize=8.2, leading=11,
                      backColor=colors.HexColor("#f1f5f9"), borderPadding=6,
                      leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=8)
TITLE = ParagraphStyle("Titlex", parent=styles["Title"], textColor=colors.HexColor("#0f172a"))
SUB = ParagraphStyle("Subx", parent=styles["Normal"], fontSize=11, textColor=colors.HexColor("#64748b"), spaceAfter=20)


def build(path, title, subtitle, sections):
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm, title=title, author="FEBA ERP")
    story = [Paragraph(title, TITLE), Paragraph(subtitle, SUB)]
    for item in sections:
        kind = item[0]
        if kind == "h1":
            story.append(Paragraph(item[1], H1))
        elif kind == "h2":
            story.append(Paragraph(item[1], H2))
        elif kind == "p":
            story.append(Paragraph(item[1], BODY))
        elif kind == "code":
            story.append(Preformatted(item[1], CODE))
        elif kind == "table":
            t = Table(item[1], colWidths=item[2] if len(item) > 2 else None)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(Spacer(1, 4)); story.append(t); story.append(Spacer(1, 8))
        elif kind == "pb":
            story.append(PageBreak())
    doc.build(story)
    print("OK:", path)


# ═══════════════════ GUIDE 1 : INSTALLATION LOCALE ═══════════════════
local = [
("h1", "1. Prérequis"),
("p", "L'installation locale s'appuie entièrement sur Docker : aucun besoin d'installer Python, Node.js, PostgreSQL ou Redis sur votre machine."),
("table", [
    ["Outil", "Version minimale", "Vérification"],
    ["Docker Engine", "24+", "docker --version"],
    ["Docker Compose", "v2 (plugin)", "docker compose version"],
    ["Git (optionnel)", "2.30+", "git --version"],
    ["RAM disponible", "4 Go minimum, 8 Go recommandé", "—"],
], [5*cm, 6*cm, 5*cm]),

("h1", "2. Récupération et configuration du projet"),
("p", "Décompressez l'archive du projet puis placez-vous à sa racine :"),
("code", "unzip feba_v1.zip\ncd feba_v1"),
("p", "Le fichier <b>.env.dev</b> est fourni prêt à l'emploi pour le développement (base PostgreSQL, Redis, JWT, CORS, domaine Jitsi). Aucune modification n'est nécessaire pour un premier lancement. En cas de besoin :"),
("code", "# .env.dev — principales variables\nDJANGO_ENV=dev\nDATABASE_URL=postgresql://feba_user:feba_dev_pass@postgres-dev:5432/feba_dev\nREDIS_URL=redis://redis-dev:6379/0\nCORS_ALLOWED_ORIGINS=http://localhost:5173\nJITSI_DOMAIN=            # renseigné par « make jitsi-up » (instance auto-hébergée)"),

("h1", "3. Démarrage de la pile complète"),
("code", "docker compose up --build -d"),
("p", "Cette commande construit et démarre 6 services : PostgreSQL 16, Redis 7, le backend Django (migrations appliquées automatiquement par l'entrypoint), Celery worker, Celery beat et le frontend Vite."),
("p", "Suivre les journaux du backend jusqu'à voir le serveur démarrer :"),
("code", "docker compose logs -f backend-dev"),

("h1", "4. Création du premier compte super-administrateur"),
("code", "docker compose exec backend-dev python manage.py createsuperuser"),
("p", "Renseignez e-mail et mot de passe. Ce compte donne accès à l'espace plateforme (gestion des établissements/tenants)."),

("h1", "5. Données de démonstration (fortement recommandé)"),
("p", "Une installation propre est vide. Le seeder intégré génère un établissement complet et immédiatement exploitable : 3 années scolaires (N-2, N-1, N active), 10 niveaux, classes par année, matières FR/EN, salles, enseignants, élèves avec <b>historique réaliste sur 3 ans</b> (progression de niveau, redoublants), parents liés, notes des 3 années, absences/retards, paiements, bulletins avec moyennes réelles, emplois du temps, devoirs, annonces, notifications et salles virtuelles. Idempotent : relancer la commande ne duplique rien."),
("code", "docker compose exec backend-dev python manage.py seed_demo_data\n# ou : make seed"),
("table", [
    ["Compte de démonstration", "Email", "Mot de passe"],
    ["Super Admin", "superadmin@feba.bj", "SuperAdmin@2024"],
    ["Administrateur", "admin@feba.bj", "Admin@2024"],
    ["Enseignant", "prof.math@feba.bj", "Teacher@2024"],
    ["Parent", "parent1@feba.bj", "Parent@2024"],
    ["Élève", "eleve1@feba.bj", "Student@2024"],
], [5*cm, 6*cm, 5*cm]),

("h1", "6. Accès à l'application"),
("table", [
    ["Service", "URL"],
    ["Frontend (interface FEBA)", "http://localhost:5173"],
    ["API backend (DRF)", "http://localhost:8000/api/"],
    ["Admin Django", "http://localhost:8000/django-admin/"],
    ["Healthcheck", "http://localhost:8000/api/health/"],
], [8*cm, 8*cm]),
("p", "Connectez-vous sur http://localhost:5173 avec le compte superadmin, créez un établissement, une année scolaire, des niveaux, des classes, puis les comptes admin/enseignants/élèves/parents."),

("h1", "7. Salles virtuelles (visioconférence)"),
("p", "Le module « Salles virtuelles » (menu latéral, tous les rôles) utilise une instance <b>Jitsi Meet auto-hébergée par FEBA</b>. Il n'existe AUCUN repli vers une instance publique : les cours concernent des mineurs, et un flux transitant chez un tiers sans authentification n'est pas une option de secours. Tant que l'instance n'est pas démarrée (<b>make jitsi-up</b>), la page affiche un bandeau de diagnostic et aucune salle ne s'ouvre. Les enseignants/administrateurs créent les salles ; élèves et parents ne voient que les salles de leur classe ou les salles générales."),

("h2", "7.1 Instance Jitsi auto-hébergée en local (JWT)"),
("p", "Pour démarrer la pile locale (authentification JWT, caméra, micro, partage d'écran, permissions) :"),
("code", "cp .env.jitsi.example .env.jitsi\n# Renseigner JITSI_APP_SECRET, JICOFO_AUTH_PASSWORD, JVB_AUTH_PASSWORD (openssl rand -hex 32)\ndocker compose -f docker-compose.jitsi.yml --env-file .env.jitsi up -d\n# Interface Jitsi : http://localhost:8443"),
("p", "« make jitsi-up » renseigne lui-même .env.jitsi et .env.dev (JITSI_DOMAIN=localhost:8443, JITSI_APP_ID et JITSI_APP_SECRET identiques des deux côtés) ; il reste à redémarrer le backend. Dès lors, chaque « Rejoindre » émet un jeton signé de 15 minutes, nommant la salle : seuls les utilisateurs autorisés par FEBA ouvrent une salle, et les enseignants/admins y sont modérateurs. Sans ces variables, la visioconférence reste INDISPONIBLE et le bandeau de diagnostic explique laquelle manque — vérifiez avec « make jitsi-health »."),

("h1", "8. Lancer les tests"),
("code", "docker compose exec backend-dev python manage.py test tests -v 2"),
("p", "La suite couvre notamment : sécurité multi-tenant, anti-escalade de privilèges, relations parents-élèves et le module salles virtuelles."),

("h1", "9. Commandes utiles (Makefile)"),
("code", "make up        # démarrer\nmake down      # arrêter\nmake logs      # journaux\nmake migrate   # appliquer les migrations\nmake shell     # shell Django\nmake test      # tests"),

("h1", "10. Dépannage rapide"),
("table", [
    ["Symptôme", "Cause probable / solution"],
    ["Port 5432/6379/8000/5173 déjà utilisé", "Arrêter le service local en conflit ou modifier le mapping de ports dans docker-compose.yml"],
    ["Page blanche sur :5173", "docker compose logs frontend-dev — vérifier une erreur de build ; relancer avec --build"],
    ["Erreur 502/connexion refusée API", "Backend pas encore healthy : attendre la fin des migrations (logs backend-dev)"],
    ["Visioconférence ne se charge pas", "Instance auto-hébergée non démarrée ou mal configurée — lancer « make jitsi-health » : le rapport nomme le contrôle en échec (configuration, DNS, TLS, HTTP)"],
    ["Réinitialiser complètement la base", "docker compose down -v && docker compose up --build -d (efface toutes les données)"],
], [7*cm, 9*cm]),

("h1", "11. Guide de validation fonctionnelle"),
("p", "Après le seed, dérouler cette check-list (compte superadmin puis admin) pour confirmer que chaque fonctionnalité est opérationnelle :"),
("table", [
    ["#", "Scénario", "Résultat attendu"],
    ["1", "Connexion / déconnexion avec chaque compte démo", "Accès au tableau de bord du rôle, déconnexion propre"],
    ["2", "Tous les utilisateurs → Nouvel utilisateur (rôle Élève)", "Le champ Établissement apparaît ; création sans erreur"],
    ["3", "Élèves → sélectionner l'année N-1 puis N-2", "Les élèves apparaissent avec la CLASSE DE CETTE ANNÉE-LÀ"],
    ["4", "Inscriptions → Passage de niveau (année N-1 → N)", "Listes d'années remplies ; rapport inscrits/ignorés/échecs"],
    ["5", "Inscriptions → Passage par classe", "Classe source + année cible sélectionnables ; passage OK"],
    ["6", "Inscriptions → Inscription individuelle", "Élève réinscrit ; ancienne inscription intacte"],
    ["7", "Inscriptions → Assistant fin d'année", "Décisions par élève (passage, redoublement, départ) appliquées"],
    ["8", "Inscriptions → Historique élève", "3 années listées ; badge 'Année active' UNIQUEMENT sur l'année en cours ; moyenne, absences, paiements par année"],
    ["9", "Notes / Bulletins / Absences / Paiements / Devoirs", "Données de démo visibles, filtrables par année"],
    ["10", "Emploi du temps → Nouveau créneau", "Liste des salles remplie (Salle 101…, Bibliothèque)"],
    ["11", "Salles virtuelles → Rejoindre", "Réunion Jitsi s'ouvre (caméra/micro/partage)"],
    ["12", "Export Excel de la liste élèves", "Fichier téléchargé avec l'année sélectionnée"],
    ["13", "Paramètres → Nouvelle année scolaire (nom, début, fin)", "Année créée ; doublon de nom ou fin ≤ début → message clair (pas d'erreur 500)"],
    ["14", "Paramètres → Activer / Clôturer une année", "Une seule année active à la fois ; clôture possible"],
    ["15", "Notes → cliquer une ligne (desktop)", "« Détail de la note » s'ouvre en modale CENTRÉE ; en mobile, panneau bas conservé"],
    ["16", "Notes → moyennes", "Une matière sans note affiche « — » et n'entre PAS dans la moyenne (plus de 0 automatiques)"],
    ["17", "Bulletins → Générer puis ouvrir le PDF", "Le PDF s'ouvre via localhost:5173/media/... (plus jamais backend-dev:8000)"],
    ["18", "Élèves/Parents → photos, reçus, justificatifs", "Tous les fichiers s'ouvrent (URLs relatives, valables dev et prod)"],
    ["19", "Inscriptions → Passage par classe (classe déjà promue)", "Message clair « X élève(s) inscrit(s) » ou « tous déjà inscrits » — plus de faux « 0 »"],
    ["20", "Inscriptions → tout menu déroulant (élève, classe, année)", "Champ de recherche intégré, insensible aux accents, navigable au clavier"],
    ["21", "Notes → Résumé par élève / Bilingue (superadmin)", "Chargement correct (plus « indisponible » / « erreur de chargement »)"],
    ["22", "Notes → supprimer une note depuis le Détail", "Le panneau se ferme, la liste se rafraîchit, aucune erreur « ressource introuvable »"],
    ["23", "Nouvel élève → choisir une année scolaire", "La liste Classe ne montre QUE les classes de cette année (plus de CP1/CP1/CP1)"],
    ["24", "Salles virtuelles / Emploi du temps / Devoirs → sélecteur Classe", "Uniquement les classes de l'année active, sans doublons"],
    ["25", "Classes → puces d'années", "Chaque année liste ses propres classes ; « Année active » par défaut"],
    ["26", "Élèves (année N-1 sélectionnée) → Supprimer", "3 choix : retirer de l'année N-1 / désactiver (toutes années) / définitif ; l'historique des autres années reste intact"],
    ["27", "Supprimer définitivement un élève ayant des notes", "Refus explicite (409) listant les dépendances"],
    ["28", "Retirer un élève de son année courante", "Son pointeur bascule sur son inscription restante la plus récente"],
    ["29", "Supprimer un parent", "Désactivation : liens familiaux et historique conservés ; définitif refusé si liens"],
    ["30", "Élèves (année X) → tout sélectionner → bouton « Retirer de X »", "Seules les inscriptions de X disparaissent ; les autres années affichent toujours tous leurs élèves"],
    ["31", "Salle virtuelle avec instance Jitsi locale (JWT configuré)", "Accès uniquement via FEBA (jeton signé) ; enseignant = modérateur ; leave enregistre la durée"],
    ["32", "scripts/backup_database.sh puis restore_backup.sh db", "Dump + checksum créés ; restauration validée sur environnement jetable"],
    ["33", "Salles virtuelles sans instance configurée", "Bandeau ambre « Mode démonstration — 5 minutes » avec la procédure make jitsi-up"],
    ["34", "make jitsi-up puis Rejoindre une salle", "Réunion illimitée sur l'instance locale, jeton JWT émis, bandeau démo disparu"],
    ["35", "Élèves / Parents sur une année sans données", "Message contextuel expliquant pourquoi la liste est vide et comment la remplir (make seed / inscriptions)"],
    ["36", "Nouvel élève → Compte utilisateur", "Seuls les comptes NON liés sont proposés ; un compte déjà lié soumis → message clair orientant vers la réinscription (plus d'erreur 500)"],
    ["37", "Parents → tout sélectionner → Désactiver la sélection", "Désactivation réversible ; liens familiaux et historique intacts (plus de destruction en masse)"],
    ["38", "Classes d'une année passée", "Effectifs réels affichés (via les inscriptions), plus de 0/30 systématique"],
    ["39", "Supprimer une classe portant des inscriptions", "Refus explicite (409) listant les dépendances, à l'unité comme en masse"],
    ["40", "Classes → « Copier depuis une année » (ex: 2025-2026 → 2026-2027)", "Classes dupliquées avec niveaux, capacités et matières FR/EN ; relance = doublons ignorés"],
    ["41", "Classes → Nouvelle classe", "L'année scolaire est pré-sélectionnée (année filtrée ou active)"],
    ["42", "Classes → année sans classes", "Message contextuel proposant la création ou la copie depuis une année précédente"],
    ["43", "Classes → puce « Année active » puis puces d'années", "La puce surlignée et le contenu du tableau désignent TOUJOURS la même année (plus de puce 2026-2027 active avec contenu 2023-2024)"],
    ["44", "Paramètres → activer une autre année", "Une seule année active à la fois, partout dans l'application"],
    ["45", "Classes → éditer/supprimer une classe d'une année NON active", "Opération réussie (plus de 404 en boucle dans la console)"],
    ["46", "Console navigateur au chargement", "Aucun avertissement React Router (future flags v7 activés) ; pas de salve de 404"],
    ["47", "Connexion élève → Accueil et Mes notes", "Aucune erreur 500 sur /grades/averages/ ; moyennes affichées ou « — » proprement"],
    ["48", "Cloche de notifications (tous rôles)", "Compteur chargé sans 404 sur /notifications/unread-count/"],
    ["49", "Notes → Bilingue (élève sans matières FR/EN dans l'année)", "Message clair « Pas de calcul bilingue pour cette sélection », jamais d'erreur serveur"],
    ["50", "Paramètres → Salles", "Salles physiques éditables ; salles de classe automatiques listées à part, clairement expliquées"],
    ["51", "Notes → Bilingue (élève d'une classe FR+EN)", "Le calcul s'affiche (plus de 404 : la route n'est plus masquée par le routeur)"],
    ["52", "Photos de profil (parent, enseignant, élève, logo école)", "S'affichent correctement (URLs relatives, plus de backend-dev:8000 / ERR_NAME_NOT_RESOLVED)"],
    ["53", "Notes → Bilingue : filtres période/classe", "Absents dans la vue Bilingue (redondants) ; seuls Année, Élève et Trimestre subsistent"],
    ["54", "Élèves → réinscrire → Nouvelle classe", "La liste ne montre que les classes de l'année cible (plus de « 3ème-A » en triple)"],
    ["55", "Paramètres → créer une matière déjà existante", "Refus explicite (doublon même nom + langue) ; plus de « test / test »"],
    ["56", "Backend : make test", "Toute la suite passe (…, bilingue, avatars relatifs, dédoublonnage matières)"],
], [0.8*cm, 7.2*cm, 8*cm]),
]

build("guide_installation_local.pdf",
      "FEBA — Guide d'installation locale",
      "ERP de gestion scolaire · Environnement de développement et de test · Docker Compose",
      local)

# ═══════════════════ GUIDE 2 : DÉPLOIEMENT PRODUCTION ═══════════════════
prod = [
("h1", "1. Architecture de production"),
("p", "La pile de production (docker-compose.prod.yml) comprend : PostgreSQL 16 (volume persistant), Redis 7, backend Django servi par Gunicorn, Celery worker + beat, frontend compilé (build Vite) servi par Nginx, et Nginx en frontal (reverse-proxy, TLS, fichiers statiques/médias)."),

("h1", "2. Prérequis serveur"),
("table", [
    ["Élément", "Recommandation"],
    ["Serveur", "VPS/dédié Linux (Ubuntu 22.04/24.04 LTS), 2 vCPU / 4 Go RAM minimum, 8 Go recommandé"],
    ["Docker + Compose v2", "Installés et fonctionnels"],
    ["Nom de domaine", "ex: erp.mon-ecole.bj pointant (A/AAAA) vers le serveur"],
    ["Ports ouverts", "80 et 443 uniquement (pare-feu : bloquer 5432, 6379, 8000)"],
    ["Certificat TLS", "Let's Encrypt via certbot"],
], [5*cm, 11*cm]),

("h1", "3. Configuration de l'environnement"),
("p", "Copier le modèle puis renseigner TOUTES les valeurs — ne jamais réutiliser les valeurs de développement :"),
("code", "cp .env.prod.example .env.prod\nnano .env.prod"),
("code", "DJANGO_ENV=prod\nSECRET_KEY=<64+ caractères aléatoires — openssl rand -base64 64>\nALLOWED_HOSTS=globalfeba.com,www.globalfeba.com\nCORS_ALLOWED_ORIGINS=https://globalfeba.com\nCSRF_TRUSTED_ORIGINS=https://globalfeba.com,https://www.globalfeba.com\nDATABASE_URL=postgresql://feba:<MOT_DE_PASSE_FORT>@postgres:5432/feba\nREDIS_URL=redis://redis:6379/0\nJWT_ACCESS_TOKEN_LIFETIME_MINUTES=30\nEMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend\nEMAIL_HOST=smtp.votre-fournisseur.com\nJITSI_DOMAIN=meet.globalfeba.com   # instance auto-hébergée — JAMAIS une instance publique\nJITSI_APP_ID=<openssl rand -hex 8>\nJITSI_APP_SECRET=<openssl rand -hex 32>"),
("p", "<b>Sécurité impérative :</b> SECRET_KEY unique et long ; mot de passe PostgreSQL fort ; DEBUG reste à False (imposé par settings/prod.py) ; HTTPS obligatoire."),

("h1", "4. TLS / HTTPS (Let's Encrypt)"),
("code", "sudo apt install certbot\nsudo certbot certonly --standalone -d erp.mon-ecole.bj\n# Certificats dans /etc/letsencrypt/live/erp.mon-ecole.bj/"),
("p", "Monter les certificats dans le conteneur Nginx (volume dans docker-compose.prod.yml) et référencer ssl_certificate / ssl_certificate_key dans nginx/nginx.conf. Renouvellement automatique : certbot renew via cron/systemd timer + rechargement Nginx."),

("h1", "5. Déploiement"),
("code", "docker compose -f docker-compose.prod.yml --env-file .env.prod up --build -d\ndocker compose -f docker-compose.prod.yml logs -f backend"),
("p", "L'entrypoint de production applique les migrations, collecte les fichiers statiques puis démarre Gunicorn. Créer ensuite le superadmin :"),
("code", "docker compose -f docker-compose.prod.yml exec backend \\\n    python manage.py createsuperuser"),

("p", "<b>Note :</b> la commande seed_demo_data génère des données de DÉMONSTRATION — ne l'exécutez jamais sur une base de production réelle."),

("h1", "6. Vérifications post-déploiement"),
("table", [
    ["Contrôle", "Attendu"],
    ["https://erp.mon-ecole.bj", "Interface de connexion FEBA (cadenas TLS valide)"],
    ["https://erp.mon-ecole.bj/api/health/", "Réponse 200 (healthcheck)"],
    ["Connexion superadmin", "Accès espace plateforme, création d'un établissement"],
    ["Ports 5432/6379/8000 depuis l'extérieur", "Fermés (pare-feu)"],
    ["Salle virtuelle de test", "Réunion Jitsi accessible caméra/micro/partage d'écran"],
], [8*cm, 8*cm]),

("h1", "7. Sauvegardes automatisées (rotation 7/4/12) et restauration"),
("p", "Quatre scripts prêts à l'emploi dans scripts/ — base PostgreSQL, médias, configuration Jitsi (Prosody/JWT inclus), restauration — avec checksum SHA-256, rotation automatique (7 quotidiennes, 4 hebdomadaires, 12 mensuelles) et copie hors site via RCLONE_REMOTE (S3 compatible, NAS, serveur secondaire) : les sauvegardes ne restent jamais uniquement sur le serveur principal."),
("code", "# Cron (sauvegarde complète chaque nuit a 02h00)\n0 2 * * *  cd /opt/feba && RCLONE_REMOTE=s3feba:feba-backups ./scripts/backup_database.sh /backups/feba >> /var/log/feba-backup.log 2>&1\n15 2 * * * cd /opt/feba && RCLONE_REMOTE=s3feba:feba-backups ./scripts/backup_files.sh    /backups/feba >> /var/log/feba-backup.log 2>&1\n30 2 * * 0 cd /opt/feba && RCLONE_REMOTE=s3feba:feba-backups ./scripts/backup_jitsi.sh    /backups/feba >> /var/log/feba-backup.log 2>&1"),
("code", "# Restauration (verifie le checksum, arrete/redemarre les services)\n./scripts/restore_backup.sh db    /backups/feba/daily/feba_db_2026-07-06.sql.gz\n./scripts/restore_backup.sh media /backups/feba/daily/feba_media_2026-07-06.tar.gz"),
("p", "Test de restauration MENSUEL obligatoire sur un environnement jetable (procédure complète, y compris reconstruction de serveur : docs/SECURITE_RGPD_DISASTER_RECOVERY.md). Une sauvegarde non testée n'est pas une sauvegarde."),

("h1", "8. Mises à jour applicatives"),
("code", "git pull   # ou remplacement de l'archive\ndocker compose -f docker-compose.prod.yml --env-file .env.prod up --build -d\n# Les migrations s'appliquent automatiquement au démarrage du backend"),
("p", "Toujours effectuer une sauvegarde complète avant mise à jour. En cas de problème : redéployer la version précédente puis restaurer la base."),

("h1", "9. Visioconférence en production — Jitsi auto-hébergé (OBLIGATOIRE)"),
("p", "<b>meet.jit.si est proscrit en production</b>, et le backend le REFUSE (JITSI_FORBIDDEN_DOMAINS) : flux transitant chez un tiers, aucune authentification, cours de mineurs. Il n'existe aucun repli silencieux — une configuration incomplète produit une erreur d'infrastructure explicite. La pile fournie (docker-compose.jitsi.yml + docker-compose.jitsi.prod.yml : jitsi-web, prosody, jicofo, jvb) est un service INDÉPENDANT de FEBA, protégé par JWT : seuls les jetons signés par le backend ouvrent une salle. Voir JITSI_PRODUCTION_GUIDE.md pour le déploiement de meet.globalfeba.com."),
("code", "# 1. DNS : meet.mon-ecole.bj -> IP du serveur (ou d'un serveur dédié 4 Go RAM)\n# 2. Secrets partagés\ncp .env.jitsi.example .env.jitsi   # openssl rand -hex 32 pour chaque valeur\n# 3. Pare-feu : ouvrir TCP 443 + UDP 10000 ; JVB_ADVERTISE_IPS=<IP publique>\n#    JITSI_PUBLIC_URL=https://meet.mon-ecole.bj (TLS : Let's Encrypt sur le reverse proxy)\ndocker compose -f docker-compose.jitsi.yml --env-file .env.jitsi up -d\n# 4. Cote FEBA (.env.prod) :\nJITSI_DOMAIN=meet.mon-ecole.bj\nJITSI_APP_ID=feba\nJITSI_APP_SECRET=<identique a .env.jitsi>"),
("p", "Vérifications : rejoindre une salle depuis FEBA (jeton émis automatiquement), caméra/micro/partage d'écran fonctionnels, un utilisateur NON connecté à FEBA ne peut pas ouvrir la salle, enseignant = modérateur. Réseaux d'établissement restrictifs : ajouter un serveur TURN (coturn) et le déclarer dans la configuration Jitsi."),

("h1", "10. Supervision et maintenance"),
("table", [
    ["Tâche", "Fréquence"],
    ["Consultation des journaux (docker compose logs)", "Quotidienne / sur alerte"],
    ["Vérification de l'espace disque (df -h, volumes Docker)", "Hebdomadaire"],
    ["Mises à jour de sécurité du serveur (apt upgrade)", "Hebdomadaire"],
    ["Test de restauration d'une sauvegarde", "Mensuelle"],
    ["Renouvellement TLS (automatisé, à vérifier)", "Mensuelle"],
    ["Sentry (optionnel, requirements/prod.txt)", "Alertes temps réel sur erreurs"],
], [11*cm, 5*cm]),
]

build("guide_deploiement_production.pdf",
      "FEBA — Guide de déploiement en production",
      "ERP de gestion scolaire · Serveur Linux · Docker Compose · Nginx · HTTPS",
      prod)
