# Parcours d'inscription FEBA FHA — de la soumission au dossier traitable

## Ce qui est atomique, et ce qui ne doit pas l'être

C'est la décision centrale de cette itération.

**Indissociable** (une transaction) : valider, numéroter, enregistrer les
champs, dater les consentements, ouvrir l'historique d'état. Si l'une
échoue, rien n'est écrit. Un dossier sans numéro ou sans historique n'est
pas un dossier à moitié créé — c'est un dossier dont on ne pourra rien dire.

**Volontairement hors transaction** : produire le PDF, notifier
l'administration, envoyer l'accusé de réception. Un serveur SMTP
injoignable ne doit pas faire perdre une inscription.

Vérifié par `test_un_echec_d_envoi_ne_fait_pas_perdre_l_inscription` : avec
un backend d'envoi qui lève, la fiche est enregistrée, l'échec est visible,
et l'écran ne promet rien.

## Les dix-huit étapes

| # | Étape | Où | Vérifié par |
|---|---|---|---|
| 1 | Validation complète | `FHAEnrollmentCreateSerializer` | `test_1_la_soumission_est_acceptee` |
| 2 | Transaction atomique | `create_application` | `test_10_une_fiche_invalide_n_ecrit_rien` |
| 3 | Numéro unique `FHA-2026-0002` | `generate_reference` | `test_2` / `test_3` |
| 4 | Doublon refusé | contrainte + validation | `test_4_un_double_clic_ne_cree_pas_deux_dossiers` |
| 5 | Tous les champs stockés | modèle | `test_6_tous_les_champs_saisis_sont_enregistres` |
| 6 | Académie conservée | route, jamais le client | `test_5_l_academie_est_imposee_par_la_route` |
| 7 | Groupe suggéré calculé | `suggested_group` | `test_9` |
| 8 | Consentements datés et versionnés | `consents_accepted_at` | `test_7` |
| 9 | PDF complet produit | `generate_and_store_sheet` | `test_la_fiche_est_produite_a_la_soumission` |
| 10 | Stockage privé | `PRIVATE_MEDIA_ROOT` | `test_la_fiche_est_hors_du_stockage_public` |
| 11 | PDF associé au dossier | `sheet_path` + empreinte | `test_la_fiche_porte_une_empreinte_et_une_taille` |
| 12 | Admins de l'académie prévenus | `academy_admin_emails` | `test_les_admins_de_l_academie_…` |
| 13 | Super administrateurs prévenus | `superadmin_emails` | idem |
| 14 | Accusé au responsable | `parent_ack_bodies` | `test_un_accuse_de_reception_est_envoye_au_parent` |
| 15 | PDF joint à l'accusé | pièce jointe | `test_l_accuse_porte_la_fiche_en_piece_jointe` |
| 16 | Écran de confirmation exact | vue publique | `test_l_ecran_public_ne_promet_pas_…` |
| 17 | Journalisation sans secret | `logger.info` | revue |
| 18 | Visibilité immédiate | liste d'admission | parcours navigateur 2 |

## L'écran public ne promet que ce qui s'est produit

Il annonçait « Vous recevrez un e-mail de confirmation » avant même que la
couche d'envoi ait répondu.

Désormais, le numéro de dossier est mis en avant — lui est acquis — et
l'e-mail n'est annoncé que si le fournisseur l'a accepté. Voir
`EMAIL_DELIVERY_REPORT.md`.

## La fiche PDF

Dix-huit sections, tout ce que la famille a saisi. Un champ vide est écrit
« — » plutôt que supprimé : l'absence de réponse est elle-même une
information, et une cellule vide se confond avec une section qu'on aurait
oublié d'imprimer.

| Propriété | Valeur |
|---|---|
| Nom de fichier | `FHA-2026-0009-fiche-inscription.pdf` — stable, déductible du numéro |
| Stockage | `private_media/fha_applications/<académie>/` — hors du répertoire servi |
| Permissions | `0600` |
| Empreinte | SHA-256 enregistrée |
| Versions | conservées — une copie a peut-être déjà été envoyée |
| Identité | celle de l'académie destinataire, jamais l'autre |

Téléchargement par une vue authentifiée qui applique le filtrage par
académie : un admin FEBA reçoit **404** sur un dossier FHA, y compris en
devinant l'identifiant. En-tête `Cache-Control: private, no-store` — un
poste utilisé par plusieurs agents ne doit pas resservir le dossier d'un
autre enfant.

## Ce que l'administration voit et peut faire

**Dans la liste** : numéro, académie, enfant, âge, groupe suggéré,
responsable avec son WhatsApp, statut, **état de la fiche PDF**, **état de
l'e-mail au parent**, date. Trois actions par ligne : télécharger la fiche,
renvoyer l'e-mail, ouvrir le détail complet.

**Dans le détail** : tous les champs, avec les libellés lisibles
(« Comprend quelques mots », pas `few_words`), l'état de la fiche et des
envois, l'historique d'état, et les besoins particuliers rendus sans
troncature.

**Export CSV** : tous les champs du modèle, construits depuis `_meta` pour
qu'un champ ajouté demain n'y manque pas. Même filtrage par académie que la
liste — un export plus permissif que l'écran serait un moyen discret de
contourner l'isolation.

## Un défaut trouvé en chemin

La liste cherchait `parent_first_name`, `parent_last_name`, `parent_email`.
Le serializer expose `parent1_*`. La recherche par nom de parent lisait donc
`undefined` et ne trouvait jamais rien ; l'export sortait ces colonnes
vides. Sans erreur, sans signe.

C'est exactement la classe de défaut que `manage.py field_mapping_audit`
existe pour trouver.

## Tests

`backend/tests/test_fha_enrollment_workflow.py` — 43 tests, 194 sous-tests.
Parcours navigateur : `e2e/parcours-v9.mjs`, journeys 1 et 2.
