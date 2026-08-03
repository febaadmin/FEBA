# Audit de la chaîne des champs
Ce fichier est **produit par `manage.py field_mapping_audit`**, pas rédigé à la main. Un tableau écrit reste juste le jour où on l'écrit et devient faux au premier champ ajouté — c'est exactement ainsi que le numéro WhatsApp a disparu : présent dans le modèle et dans le formulaire, absent du serializer.
Colonnes : **Saisi** (le serializer public l'accepte) · **Relu** (l'administration le voit) · **Liste** (visible sans ouvrir le détail) · **Export** (présent dans le CSV).

## Fiche d'inscription FEBA FHA
| Champ | Saisi | Relu | Liste | Export | Remarque |
|---|:-:|:-:|:-:|:-:|---|
| `id` | — | ✅ | ✅ | — | Identifiant technique. |
| `entity` | — | ✅ | — | — | Imposée par le serveur d'après la route — jamais lue du client. |
| `reference` | — | ✅ | ✅ | ✅ | Attribuée par le serveur. |
| `status` | — | ✅ | ✅ | ✅ | Piloté par le parcours d'admission, pas par le formulaire. |
| `child_last_name` | ✅ | ✅ | ✅ | ✅ |  |
| `child_first_name` | ✅ | ✅ | ✅ | ✅ |  |
| `child_birth_date` | ✅ | ✅ | — | ✅ |  |
| `child_city` | ✅ | ✅ | — | ✅ |  |
| `child_state_province` | ✅ | ✅ | — | ✅ |  |
| `child_country` | ✅ | ✅ | ✅ | ✅ |  |
| `child_current_school` | ✅ | ✅ | — | ✅ |  |
| `child_grade` | ✅ | ✅ | — | ✅ |  |
| `child_photo` | ✅ | ✅ | — | — | Fichier binaire — servi par une vue dédiée, pas dans un CSV. |
| `family_origin_country` | ✅ | ✅ | — | ✅ |  |
| `home_main_language` | ✅ | ✅ | — | ✅ |  |
| `other_languages` | ✅ | ✅ | — | ✅ |  |
| `french_speakers_with_child` | ✅ | ✅ | — | ✅ |  |
| `french_speakers_relation` | ✅ | ✅ | — | ✅ |  |
| `french_levels` | ✅ | ✅ | — | ✅ |  |
| `french_level_notes` | ✅ | ✅ | — | ✅ |  |
| `previous_courses` | ✅ | ✅ | — | ✅ |  |
| `bilingual_school` | ✅ | ✅ | — | ✅ |  |
| `stay_in_francophone_country` | ✅ | ✅ | — | ✅ |  |
| `certifications_obtained` | ✅ | ✅ | — | ✅ |  |
| `experience_duration` | ✅ | ✅ | — | ✅ |  |
| `experience_comments` | ✅ | ✅ | — | ✅ |  |
| `parent_goals` | ✅ | ✅ | — | ✅ |  |
| `parent_goals_other` | ✅ | ✅ | — | ✅ |  |
| `parent1_last_name` | ✅ | ✅ | ✅ | ✅ |  |
| `parent1_first_name` | ✅ | ✅ | ✅ | ✅ |  |
| `parent1_relation` | ✅ | ✅ | — | ✅ |  |
| `parent1_phone` | ✅ | ✅ | ✅ | ✅ |  |
| `parent1_whatsapp` | ✅ | ✅ | ✅ | ✅ |  |
| `parent1_email` | ✅ | ✅ | ✅ | ✅ |  |
| `parent1_address` | ✅ | ✅ | — | ✅ |  |
| `parent1_city` | ✅ | ✅ | — | ✅ |  |
| `parent1_state_province` | ✅ | ✅ | — | ✅ |  |
| `parent1_country` | ✅ | ✅ | — | ✅ |  |
| `parent1_postal_code` | ✅ | ✅ | — | ✅ |  |
| `parent1_preferred_language` | ✅ | ✅ | — | ✅ |  |
| `parent1_timezone` | ✅ | ✅ | — | ✅ |  |
| `parent2_last_name` | ✅ | ✅ | — | ✅ |  |
| `parent2_first_name` | ✅ | ✅ | — | ✅ |  |
| `parent2_relation` | ✅ | ✅ | — | ✅ |  |
| `parent2_phone` | ✅ | ✅ | — | ✅ |  |
| `parent2_whatsapp` | ✅ | ✅ | — | ✅ |  |
| `parent2_email` | ✅ | ✅ | — | ✅ |  |
| `parent2_address` | ✅ | ✅ | — | ✅ |  |
| `parent2_city` | ✅ | ✅ | — | ✅ |  |
| `parent2_state_province` | ✅ | ✅ | — | ✅ |  |
| `parent2_country` | ✅ | ✅ | — | ✅ |  |
| `parent2_postal_code` | ✅ | ✅ | — | ✅ |  |
| `parent2_preferred_language` | ✅ | ✅ | — | ✅ |  |
| `parent2_timezone` | ✅ | ✅ | — | ✅ |  |
| `emergency_name` | ✅ | ✅ | — | ✅ |  |
| `emergency_relation` | ✅ | ✅ | — | ✅ |  |
| `emergency_phone` | ✅ | ✅ | — | ✅ |  |
| `emergency_email` | ✅ | ✅ | — | ✅ |  |
| `emergency_contact_authorized` | ✅ | ✅ | — | ✅ |  |
| `available_days` | ✅ | ✅ | — | ✅ |  |
| `available_time_slots` | ✅ | ✅ | — | ✅ |  |
| `family_timezone` | ✅ | ✅ | ✅ | ✅ |  |
| `weekday_or_weekend` | ✅ | ✅ | — | ✅ |  |
| `availability_notes` | ✅ | ✅ | — | ✅ |  |
| `has_computer` | ✅ | ✅ | — | ✅ |  |
| `has_tablet` | ✅ | ✅ | — | ✅ |  |
| `has_camera` | ✅ | ✅ | — | ✅ |  |
| `has_microphone` | ✅ | ✅ | — | ✅ |  |
| `has_headset` | ✅ | ✅ | — | ✅ |  |
| `has_internet` | ✅ | ✅ | — | ✅ |  |
| `can_print` | ✅ | ✅ | — | ✅ |  |
| `equipment_notes` | ✅ | ✅ | — | ✅ |  |
| `special_needs` | ✅ | ✅ | — | ✅ |  |
| `consent_rules` | ✅ | ✅ | — | ✅ |  |
| `consent_zoom` | ✅ | ✅ | — | ✅ |  |
| `consent_privacy` | ✅ | ✅ | — | ✅ |  |
| `consent_data_processing` | ✅ | ✅ | — | ✅ |  |
| `consent_photo_video` | ✅ | ✅ | — | ✅ |  |
| `consent_communications` | ✅ | ✅ | — | ✅ |  |
| `consent_payment_policy` | ✅ | ✅ | — | ✅ |  |
| `consent_annual_commitment` | ✅ | ✅ | — | ✅ |  |
| `consent_parental_authorization` | ✅ | ✅ | — | ✅ |  |
| `consents_version` | — | ✅ | — | ✅ | Fixée par le serveur au moment de l'acceptation. |
| `consents_accepted_at` | — | ✅ | — | ✅ | Horodatée par le serveur. |
| `recommended_group` | — | ✅ | ✅ | ✅ | Renseigné après le test de placement. |
| `submitted_ip` | — | ✅ | — | — | Donnée technique de traçabilité — jamais sur un document remis. |
| `sheet_path` | — | ✅ | — | — | Chemin de stockage interne — le publier faciliterait un accès direct. |
| `sheet_sha256` | — | ✅ | — | — | Empreinte technique du fichier. |
| `sheet_size` | — | ✅ | — | ✅ | Métadonnée technique. |
| `sheet_generated_at` | — | ✅ | ✅ | ✅ | Métadonnée technique. |
| `sheet_version` | — | ✅ | — | ✅ | Métadonnée technique. |
| `sheet_error` | — | ✅ | — | ✅ | Diagnostic interne, affiché à l'administration seule. |
| `created_at` | — | ✅ | ✅ | ✅ | Horodatage serveur. |
| `updated_at` | — | ✅ | — | ✅ | Horodatage serveur. |

63 libellés répartis en sections sur la fiche PDF ; le test `test_la_fiche_contient_toutes_les_sections` vérifie qu'aucune ne manque au rendu.

## Message de contact (FEBA et FEBA FHA)
| Champ | Saisi | Relu | Liste | Export | Remarque |
|---|:-:|:-:|:-:|:-:|---|
| `id` | — | ✅ | ✅ | ✅ | Identifiant technique. |
| `entity` | — | ✅ | ✅ | ✅ | Imposée par le serveur d'après la route — jamais lue du client. |
| `name` | ✅ | ✅ | ✅ | ✅ |  |
| `email` | ✅ | ✅ | ✅ | ✅ |  |
| `phone` | ✅ | ✅ | ✅ | ✅ |  |
| `subject` | ✅ | ✅ | ✅ | ✅ |  |
| `message` | ✅ | ✅ | ✅ | ✅ |  |
| `consent` | ✅ | ✅ | ✅ | ✅ |  |
| `is_read` | — | ✅ | ✅ | ✅ | État de lecture interne, pas une saisie du visiteur. |
| `created_at` | — | ✅ | ✅ | ✅ | Horodatage serveur. |
| `whatsapp` | ✅ | ✅ | ✅ | ✅ |  |
| `country` | ✅ | ✅ | ✅ | ✅ |  |
| `state_province` | ✅ | ✅ | ✅ | ✅ |  |
| `timezone` | ✅ | ✅ | ✅ | ✅ |  |
| `preferred_language` | ✅ | ✅ | ✅ | ✅ |  |
| `category` | ✅ | ✅ | ✅ | ✅ |  |

## Préinscription FEBA
| Champ | Saisi | Relu | Liste | Export | Remarque |
|---|:-:|:-:|:-:|:-:|---|
| `id` | — | ✅ | ✅ | ✅ | Identifiant technique. |
| `entity` | — | ✅ | ✅ | ✅ | Imposée par le serveur d'après la route — jamais lue du client. |
| `parent_name` | ✅ | ✅ | ✅ | ✅ |  |
| `phone` | ✅ | ✅ | ✅ | ✅ |  |
| `whatsapp` | ✅ | ✅ | ✅ | ✅ |  |
| `email` | ✅ | ✅ | ✅ | ✅ |  |
| `child_name` | ✅ | ✅ | ✅ | ✅ |  |
| `child_age` | ✅ | ✅ | ✅ | ✅ |  |
| `desired_level` | ✅ | ✅ | ✅ | ✅ |  |
| `school_year` | ✅ | ✅ | ✅ | ✅ |  |
| `message` | ✅ | ✅ | ✅ | ✅ |  |
| `status` | — | ✅ | ✅ | ✅ | Piloté par le parcours d'admission, pas par le formulaire. |
| `created_at` | — | ✅ | ✅ | ✅ | Horodatage serveur. |

## Résultat
Aucun champ saisi ne reste invisible : chaque valeur acceptée par un formulaire public est relue par l'administration.
