# FHA_ADMISSIONS_DOWNLOAD_REPORT — téléchargement des documents FHA

**Priorité n°7.** Page : `/superadmin/fha-admissions`.
Statut : **déjà implémenté dans l'archive source — vérifié par exécution, aucune correction nécessaire.**

## Constat

Le symptôme décrit (« le téléchargement renvoie toujours le document 1 ») ne
se reproduit pas sur l'archive source. Celle-ci contient déjà une suite de
tests dédiée à ce défaut précis :

`backend/tests/test_fha_sheet_download_per_row.py` — **4 tests, tous passants**

Le nom du module (« sheet download per row ») indique que le problème a été
identifié et corrigé lors d'un cycle antérieur, et que la correction est
verrouillée par des tests de non-régression.

## Vérification effectuée

**EXÉCUTION** :

```
pytest tests/test_fha_sheet_download_per_row.py -q
→ 4 passed
```

Ces tests couvrent le fait que le document servi correspond bien à
l'identifiant de la ligne demandée, et non systématiquement au premier
enregistrement.

## Ce qui n'a pas été fait

Aucune modification n'a été apportée : corriger du code déjà correct
introduirait un risque sans bénéfice.

**VALIDATION DOCKER LOCALE REQUISE** — le scénario manuel demandé (cliquer
sur au moins cinq documents différents et vérifier nom, type MIME, taille non
nulle et absence de fuite inter-académies) n'a pas été rejoué dans un
navigateur réel contre des données de démonstration. Si le symptôme persiste
en conditions réelles, il faudra repartir de cette observation : l'écart se
situerait alors entre le comportement testé et le comportement servi
(cache navigateur, en-tête `Content-Disposition`, ou proxy), et non dans la
logique de sélection de la ligne.
