# Comptes de démonstration

> **Développement uniquement.** Ces comptes sont créés par `make seed`.
> Ne déployez JAMAIS une base de démonstration en production, et ne
> publiez pas ce fichier dans une image publique.

## FEBA — Faith & Excellence Bilingual Academy (présentiel)

| Rôle | Identifiant | Mot de passe |
|---|---|---|
| Super Administrateur | `superadmin@feba.bj` | `SuperAdmin@2024` |
| Administrateur | `admin@feba.bj` | `Admin@2024` |
| Enseignant | `prof.math@feba.bj` | `Teacher@2024` |
| Parent | `parent1@feba.bj` | `Parent@2024` |
| Élève | `eleve1@feba.bj` | `Student@2024` |

## FEBA French Heritage Academy (en ligne)

| Rôle | Identifiant | Mot de passe |
|---|---|---|
| Administrateur | `admin@febafha.org` | `Admin@2024` |
| Enseignant | `prof@febafha.org` | `Teacher@2024` |
| Parent | `parent@febafha.org` | `Parent@2024` |
| Élève | `eleve1@febafha.org` | `Student@2024` |

Le Super Administrateur appartient aux **deux** académies : il peut donc
utiliser le sélecteur « Toutes les Académies » et basculer de l'une à
l'autre.

## Ce que le seed crée

**FEBA** : 3 années scolaires, niveaux, classes, matières, enseignants,
parents, 30 élèves avec historique, notes, moyennes, bulletins, absences,
devoirs, paiements, reçus, messages, notifications, préinscriptions.
**Aucune salle virtuelle** — la visioconférence est réservée aux académies
en ligne, et l'API la refuse à une entité présentielle.

**FEBA FHA** : académie, comptes des quatre rôles, les trois groupes de
lancement (Junior Roots, French Explorers, French Ambassadors), salles
virtuelles rattachées aux groupes, une fiche d'inscription, une demande de
test de placement et un message de contact.

Aucune donnée commerciale n'est inventée : tarifs, date de rentrée,
horaires définitifs, politique de remboursement, noms d'enseignants et
prestataire de paiement restent nuls et administrables.

## Commandes

```bash
make seed         # crée / met à jour les données (idempotent)
make seed-reset   # réinitialise puis regénère — REFUSÉ si DEBUG=False
make seed-check   # contrôle d'intégrité et d'isolation inter-académies
```

`make seed` a été rejoué deux fois de suite sur une base neuve : les
comptages sont restés identiques (2 académies, 54 comptes, 33 élèves,
1 fiche, 1 demande de test) et les 16 contrôles d'intégrité passent.
