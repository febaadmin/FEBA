# Envoi des e-mails — ce qui est vrai, et ce qui ne l'est pas

## La réserve, d'abord

**Aucun e-mail n'est parti sur Internet pendant ces vérifications.** Le
backend configuré sur cette instance est
`django.core.mail.backends.console.EmailBackend` : les messages sont
composés, journalisés, horodatés — et écrits dans la console du serveur.

Ce rapport ne présente donc **aucun envoi comme réel**. Ce qui est vérifié :
la composition des messages, leurs pièces jointes, leurs deux formats,
leurs deux langues, le journal d'acheminement, les états d'échec et la
relance. Ce qui ne l'est pas : la distribution effective, qui suppose un
fournisseur et des identifiants.

`manage.py email_check` sort en erreur dans cet état, exprès :

```
AUCUN fournisseur d'envoi réel : le backend est
« django.core.mail.backends.console.EmailBackend ». Les messages sont
enregistrés et visibles dans l'administration, mais ils NE PARTENT PAS
sur Internet. Ne présentez aucun envoi comme réel dans cet état.
```

Et l'écran d'administration affiche **« Sans fournisseur »**, jamais
« Envoyé », tant que `used_real_provider` est faux.

## Le défaut corrigé

L'écran public affichait *« Vous recevrez un e-mail de confirmation »*
avant même que la couche d'envoi ait répondu. L'envoi lui-même passait par
`send_mail(..., fail_silently=True)`.

Serveur SMTP injoignable, authentification refusée, adresse rejetée : rien
ne remontait. La famille attendait un message qui n'arriverait jamais, et
l'administration n'avait aucun moyen de le savoir.

## Les cinq états

| État | Signification | Ce que l'écran montre |
|---|---|---|
| `pending` | Enregistré, pas encore remis | « En attente d'envoi » |
| `accepted` | Le fournisseur l'a accepté | « Accepté par le fournisseur » |
| `sent` | Remis au backend sans erreur | « Envoyé » |
| `failed` | Refusé, avec l'erreur exacte | « Échec » + le message du fournisseur |
| `retry` | Nouvel essai programmé | « Nouvel essai » + l'heure prévue |

`accepted` et `sent` restent **distincts à dessein**. Un serveur qui
accepte un message ne promet pas de le distribuer ; confondre les deux,
c'est réinventer le « e-mail envoyé » qui ne veut rien dire.

Aucun état ne signifie « reçu ». Aucune couche logicielle ne peut le
savoir sans accusé de lecture, et un accusé de lecture n'est pas fiable.

## Politique de reprise

| Tentative | Délai avant la suivante |
|---|---|
| 1 (immédiate) | 5 minutes |
| 2 | 30 minutes |
| 3 | 3 heures |
| 4 | aucune — passage en `failed` |

Au-delà, l'application cesse d'essayer. Une adresse mal saisie ne deviendra
jamais correcte toute seule : c'est un humain qui doit la corriger, et
l'administration dispose d'une action **« Renvoyer l'e-mail de
confirmation »** qui repart de zéro sur le compteur — la relance est une
décision prise après avoir corrigé quelque chose.

## Ce que la famille voit

L'écran public ne promet plus que ce qui s'est produit.

**Envoi accepté :**
> Merci ! Votre fiche est enregistrée sous le numéro de dossier
> FHA-2026-0009. Un e-mail de confirmation vient de vous être envoyé à
> ahouefa@example.test.

**Envoi impossible :**
> Merci ! Votre fiche est enregistrée sous le numéro de dossier
> FHA-2026-0009. Notez-le : l'envoi de l'e-mail de confirmation n'a pas pu
> être effectué pour l'instant, notre équipe a été prévenue et vous
> recontactera.

Dans les deux cas, le numéro de dossier est mis en avant : lui est acquis.
Une promesse non tenue coûte plus cher qu'une information manquante.

## Messages produits

| Message | Destinataire | Formats | Langues | Pièce jointe |
|---|---|---|---|---|
| Accusé de réception | Responsable 1 | texte + HTML | fr / en | fiche PDF |
| Alerte admission | Admins de l'académie | texte + HTML | fr | fiche PDF |
| Alerte admission | Super administrateurs | texte + HTML | fr | fiche PDF |

Les administrateurs de l'AUTRE académie ne sont jamais destinataires —
vérifié par `test_les_admins_de_l_academie_et_les_super_admins_sont_prevenus`.

Exemples livrés dans `dist-livraison/exemples-v9/` :
`email-accuse-parent.txt` / `.html`, `email-accuse-parent-en.txt` / `.html`,
`email-alerte-admin.txt` / `.html`.

## Configuration

| Variable | Rôle |
|---|---|
| `EMAIL_BACKEND` | Backend d'envoi. Console = les messages ne partent pas. |
| `EMAIL_HOST` / `EMAIL_PORT` | Serveur SMTP |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Authentification (le mot de passe reste VIDE dans `.env.example`) |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | Chiffrement |
| `EMAIL_TIMEOUT` | Délai maximal — sans lui, un serveur injoignable bloquait la requête d'un parent |
| `DEFAULT_FROM_EMAIL` | Expéditeur par défaut |
| `FEBA_FROM_EMAIL` / `FHA_FROM_EMAIL` | Expéditeur **par académie** |
| `EMAIL_REPLY_TO` | Adresse de réponse |

Un parent de l'académie en ligne ne doit pas recevoir un message venant de
l'adresse de l'école présentielle : il répondrait au mauvais secrétariat.

Vérification :

```bash
python manage.py email_check                    # diagnostic
python manage.py email_check --to vous@test     # envoi RÉEL
```

## Tests

| Vérification | Test |
|---|---|
| L'accusé part au responsable | `test_un_accuse_de_reception_est_envoye_au_parent` |
| La fiche est jointe | `test_l_accuse_porte_la_fiche_en_piece_jointe` |
| Texte ET HTML | `test_l_accuse_existe_en_texte_et_en_html` |
| Langue du parent respectée | `test_l_accuse_suit_la_langue_declaree_par_le_parent` |
| Chaque envoi journalisé | `test_chaque_envoi_laisse_une_ligne_de_journal` |
| Identifiant de suivi dans l'en-tête | `test_l_envoi_porte_un_identifiant_de_suivi` |
| Bons destinataires internes | `test_les_admins_de_l_academie_et_les_super_admins_sont_prevenus` |
| **Un échec ne perd pas l'inscription** | `test_un_echec_d_envoi_ne_fait_pas_perdre_l_inscription` |
| **Aucun e-mail promis s'il n'est pas parti** | `test_l_ecran_public_ne_promet_pas_un_e_mail_qui_n_est_pas_parti` |
| L'erreur exacte est conservée | `test_l_erreur_exacte_du_fournisseur_est_conservee` |
| Relance depuis l'administration | `test_l_administration_peut_relancer_l_accuse_de_reception` |

Les trois tests marqués en gras branchent un backend qui **lève** au lieu
d'avaler — exactement ce que faisait un vrai serveur injoignable, et que
`fail_silently=True` masquait.
