# FHA_PUBLIC_PAGE_REPORT — formules et flyer

**Priorité n°4.** Page : `/feba-fha`. Statut : **livré.**

## 1. Formules annuelles

Source unique : `frontend/src/site/fhaPlans.js`. Les tarifs sont utilisés par
la page publique, par le formulaire d'inscription et par le récapitulatif —
les dupliquer par écran les aurait fait diverger, ce qu'une famille lit comme
une erreur de facturation.

| Formule | Prix | Rythme |
|---|---|---|
| Standard | 699 $ / an | 2 cours/semaine, 1 h 15, ≈ 8/mois, ≈ 72/an |
| Premium | 999 $ / an | 3 cours/semaine, 1 h 15, ≈ 12/mois, ≈ 108/an |
| Excellence | 1 299 $ / an | 3 cours/semaine, 1 h 15, ≈ 108/an, Club de conversation |

Le contenu détaillé de chaque formule (14 lignes pour Standard, 13 pour
Premium, 14 pour Excellence) est repris intégralement, en FR et EN, tel que
spécifié. La section est rendue dans `FhaPage.jsx` sous l'ancre `#formules`.

### Cohérence corrigée

La section « Tarifs » affichait encore *« Le tarif annuel n'est pas encore
publié »*. Laissée telle quelle, elle aurait contredit frontalement les trois
formules affichées plus haut sur la même page. Elle renvoie désormais vers
les formules et conserve la seule réserve légitime : les modalités de
paiement (une, deux ou trois fois), qui relèvent de la direction.

## 2. Flyer

| Élément | Valeur |
|---|---|
| Source Drive | `FEBA FHA fliyer.jpeg` (id `1kXipzovN9hsB9DJ1hkoIlDVAeCPPwc94`) |
| Destination | `frontend/public/images/feba-fha/feba-fha-flyer.jpeg` |
| Taille | 332 810 octets |
| Dimensions | 1122 × 1402, JPEG progressif |
| SHA-256 | `4dedb347991c2e2972904a3a60651c06be118f48d5b41656898da7d9eec45ceb` |

L'empreinte du fichier livré est **identique** à celle de l'original Drive :
le fichier n'a été ni recompressé ni retouché. Vérifié également après
`npm run build` dans `frontend/dist/images/feba-fha/` — même empreinte.

Affichage : vignette cliquable, bouton « Voir en grand » (nouvel onglet) et
bouton « Télécharger le flyer » (`download="feba-fha-flyer.jpeg"`). Servi
depuis `public/`, donc avec le type MIME `image/jpeg` déterminé par le
serveur, taille non nulle, contenu exact.

Un lien vers le détail des formules est présent dans l'étape 12 du formulaire
d'inscription, avant le récapitulatif.

## 3. Choix de formule

**Backend**

- `FHAEnrollmentApplication.desired_plan` — `CharField(max_length=12)`,
  choix `STANDARD` / `PREMIUM` / `EXCELLENCE` / `UNDECIDED`, défaut
  `UNDECIDED`.
- Migration `website/0011_fhaenrollmentapplication_desired_plan.py`. Créée
  parce qu'aucun champ équivalent n'existait sur le modèle réel — vérifié
  avant écriture.
- `FHAApplicationCreateSerializer` : `desired_plan` accepté en écriture.
- `FHAApplicationListSerializer` : `desired_plan` **et** `desired_plan_display`
  exposés, donc visibles et exportables depuis FHA Admissions sans ouvrir
  chaque dossier.
- `FHAApplicationDetailSerializer` : `fields = '__all__'`, le champ y figure
  automatiquement.

`UNDECIDED` est un choix pleinement valable : forcer une décision à ce stade
fausserait la statistique d'admission.

**Frontend**

Sélecteur radio dans l'étape 12, groupé en `<fieldset>` / `<legend>`,
alimenté par `PLAN_OPTIONS`. Valeur incluse dans `EMPTY`, donc enregistrée
dans le brouillon `localStorage` et restaurée à la reprise, puis transmise au
backend avec le reste du formulaire.

## 4. Récapitulatif enrichi

Le récapitulatif affiche désormais : enfant, âge, ville, pays, langue
principale, autres langues, niveau de français (libellés lisibles), objectifs
des parents (libellés lisibles), parent, e-mail, téléphone, WhatsApp, fuseau
horaire, jours disponibles, **formule souhaitée** et besoins particuliers.

## 5. Vérifications

- **Build** : `npm run build` réussit ; le flyer est présent dans `dist`.
- **EXÉCUTION** : `manage.py makemigrations --check --dry-run` →
  « No changes detected » (la migration 0011 couvre bien le champ ajouté).
- **TEST AUTOMATISÉ** : 1 112 tests backend et 179 tests frontend passent.
- **VALIDATION DOCKER LOCALE REQUISE** : le téléchargement effectif du flyer
  (en-têtes HTTP, type MIME servi par Nginx) et l'affichage de la formule dans
  l'écran FHA Admissions n'ont pas été observés dans un navigateur réel.
