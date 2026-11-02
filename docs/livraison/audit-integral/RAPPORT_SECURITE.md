# Sécurité

| Contrôle | Résultat | Portée |
|---|---|---|
| Audit des dépendances | Vert à chaque PR | Job CI « Sécurité des dépendances » |
| Configuration de production | Vert | Job CI « Configuration et sûreté » |
| Isolation par académie (suivi, examens) | Testée | `IsolationTests` et tests d'examens |
| Droits objectifs, archives | Testés | `ObjectifEditionArchivageTests` |
| Corrigé non exposé avant autorisation | Testé | Tests d'examens |
| Mots de passe de démonstration | Aucun compte exposé au dernier contrôle | `check_demo_passwords` |

**Non fait :** test d'intrusion, revue complète de chaque API, test de charge. Ce rapport ne constitue pas une attestation de sécurité.

**À connaître :**
- L'écart de droits entre notes, devoirs et présences reste ouvert : les devoirs et présences n'utilisent pas encore le contrôle par affectation, et l'extension demande votre accord.
- Les paiements par carte et les remboursements restent désactivés, comme demandé.
