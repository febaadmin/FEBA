# Limitations connues — V5 (correctifs P0 à P7)

## 1. Les huit anomalies : état réel

| | Anomalie | État | Vérification |
|---|---|---|---|
| P0 | Mode démo Jitsi | **Corrigé** | Pile auto-hébergée démarrée, HTTP 200, JWT obligatoire côté Prosody, `make jitsi-health` → OPÉRATIONNEL |
| P1 | Sélecteur FR/EN limité à FHA | **Corrigé** | Navigateur : présent sur les 15 pages publiques testées, persistant après navigation |
| P2 | Préinscriptions FHA invisibles | **Corrigé** | API : Admin FHA voit 1 fiche + 1 test ; Admin FEBA en voit 0 |
| P3 | Deux boutons, un seul formulaire | **Corrigé** | Navigateur : `/enroll` multi-étapes, `/placement-test` court — formulaires distincts |
| P4 | Filtre sans rafraîchissement | **Corrigé** | API : bascule FEBA→FHA fait passer les élèves de 30 à 3 |
| P5 | « Toutes les entités » | **Corrigé** | Libellés FR/EN remplacés |
| P6 | Données mélangées | **Corrigé** | Listes groupées par académie, badge et compteur par section |
| P7 | `make seed` obsolète | **Corrigé** | Seed rejoué : comptages identiques, 16/16 contrôles d'intégrité |

## 2. Jitsi — ce qui est prouvé et ce qui ne l'est pas

### Prouvé
- Les quatre conteneurs démarrent et l'instance répond en HTTP 200
  (page, `external_api.js`, `config.js`).
- Prosody est en `authentication = "token"` avec `allow_empty_token = false`
  et le module `token_verification` chargé : **aucune salle anonyme**.
- `make jitsi-health` renvoie OPÉRATIONNEL contre l'instance réelle.
- Le backend refuse tout repli public : domaine sur liste noire, 503
  explicite si la configuration est incomplète.

### Non prouvé
- **Aucune réunion à deux participants réels n'a été tenue.** Vérifier
  qu'un jeton signé ouvre effectivement une salle exige deux navigateurs
  avec caméra et microphone, ce que cet environnement n'a pas.
- Le média (UDP 10000, JVB) n'a donc pas été validé de bout en bout.
- **Aucun déploiement en production n'a été réalisé** : pas de domaine
  public, pas de certificat Let's Encrypt émis.

Le pointage DNS reste la seule étape non automatisable depuis
l'application.

## 3. Correctif d'infrastructure notable

Sur un hôte sans pile IPv6, `jitsi/web` échouait sur
`socket() [::]:80 failed` et redémarrait en boucle : le conteneur
paraissait « running » sans jamais répondre. `ENABLE_IPV6=0` est
désormais la valeur par défaut, et le health check Docker porte sur une
vraie réponse HTTP plutôt que sur la présence du process.

## 4. Périmètre toujours non livré

Inchangé depuis la V4 — voir `KNOWN_LIMITATIONS_V4.md` :

- **Zoom n'est pas intégré.** L'intégration est **Jitsi auto-hébergé**.
  Les documents de cadrage mentionnent Zoom ; si la direction y tient,
  le connecteur reste entièrement à écrire.
- Espaces parent / élève / enseignant spécifiques à FHA : non livrés.
- Messagerie cloisonnée par académie, paiements et documents FHA : non
  livrés.
- Rappels de cours 24 h / 1 h : non implémentés.
- Rôles internes (admissions / finance / support / direction) : non
  livrés ; les rôles restent admin, teacher, parent, student, superadmin.

## 5. Tests non réalisés

- **Tests visuels multi-résolutions** (320 → 1920 px) : non réalisés.
  Les composants sont écrits en mobile-first Tailwind, mais aucune
  capture ni vérification de débordement n'a été faite.
- **Captures d'écran avant/après** : non fournies.
- Suite end-to-end complète : seules les vérifications ciblées P1 et P3
  ont été automatisées en navigateur.

## 6. P4 — nature de la correction

La cause racine était double : les `queryKey` ne portaient pas l'académie,
et les écrans montés ne se réinitialisaient pas.

Plutôt que de modifier 335 clés une par une — approche fragile, où un
oubli passe inaperçu — le sous-arbre routé est **remonté** via une `key`
dérivée de l'académie active, ce qui relance mécaniquement toutes les
requêtes. Les écrans nouvellement écrits portent en plus l'académie dans
leur clé.

Contrepartie assumée : la bascule provoque un remontage complet, donc une
brève phase de chargement et la perte des états locaux non persistés
(filtres de tableau, onglet ouvert). C'est le prix de la garantie
qu'aucune donnée de l'académie précédente ne reste affichée.

## 7. SQLite

`settings/test_sqlite.py` ne fonctionne toujours pas : cinq migrations
V29 antérieures utilisent `ADD COLUMN IF NOT EXISTS`, syntaxe PostgreSQL.
Défaut antérieur à ces travaux, non corrigé — le risque de régression
dépassait le bénéfice. PostgreSQL est la cible de test du projet.

## 8. CORS en développement

Les vérifications navigateur ont été menées sur le port 5174 (le 5173
étant occupé), ce qui a produit des erreurs CORS dans la console pour les
appels API. Ce n'est pas un défaut applicatif : la configuration de
développement autorise le port 5173 par défaut. Aucune erreur CORS
n'apparaît sur le port standard.
