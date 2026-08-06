# PREVIOUS_USAGE_MODELS_AUDIT — classement des modèles

Audit conduit sur les modèles réellement présents dans l'archive source, via
introspection Django (`apps.get_model`), et non d'après une liste supposée.
Chaque chemin d'académie a été validé en construisant la requête ORM
correspondante : sept chemins initialement erronés ont été détectés et
corrigés de cette façon.

## Modèles structurels — CONSERVÉS, identifiants vérifiés après suppression

`schools.School` · `subjects.Subject` · `classes.Class` · `schools.Level`

Une divergence d'identifiants sur l'un d'eux annule toute la transaction.

## Modèles conservés sans contrôle d'identifiants

`schools.SchoolBranding` · `schools.SchoolYear` · `schools.RoomType` ·
`schools.Room` · `teachers.Teacher` · `students.StudentMatriculeSequence` ·
`documents.DocumentNumberSequence` · `website.SiteSettings` ·
`website.GalleryAlbum`

Les deux séquences sont conservées pour que les futurs matricules et numéros
de document ne repartent pas à zéro et n'entrent pas en collision avec des
documents déjà émis.

## Modèles d'usage — SUPPRIMÉS

Ordre de suppression conçu pour que les dépendances partent avant leurs
cibles, et pour que les cascades restent lisibles dans le rapport.

| Modèle | Chemin vers l'académie |
|---|---|
| `grades.GradeHistory` | `grade__student__school` |
| `grades.Grade` | `student__school` |
| `bulletins.Bulletin` | `student__school` |
| `attendance.Attendance` | `student__school` |
| `payments.PaymentHistory` | `payment__student__school` |
| `payments.Payment` | `student__school` |
| `monthly_reports.MonthlyReportAttempt` | `report__student__school` |
| `monthly_reports.MonthlyStudentReport` | `student__school` |
| `homework.HomeworkAttachment` | `homework__cls__school_year__school` |
| `homework.Homework` | `cls__school_year__school` |
| `documents.DocumentEvent` | `document__student__school` |
| `documents.GeneratedDocument` | `student__school` |
| `virtualclass.VirtualRoomAttendance` | `room__school` |
| `virtualclass.VirtualRoom` | `school` |
| `messaging.Message` | `sender__school` |
| `messaging.Conversation` | **aucun** — voir ci-dessous |
| `notifications.Notification` | `user__school` |
| `notifications.EmailDelivery` | `entity` |
| `announcements.Announcement` | `author__school` |
| `parents.ParentStudent` | `student__school` |
| `students.StudentEnrollment` | `student__school` |
| `students.Student` | `school` |
| `parents.Parent` | `user__school` |
| `website.FHAApplicationStatusHistory` | `application__entity` |
| `website.FHAPlacementTestResult` | `request__application__entity` |
| `website.FHAPlacementTestRequest` | `application__entity` |
| `website.FHAEnrollmentApplication` | `entity` |
| `website.ContactMessage` | `entity` |
| `website.PreRegistration` | `entity` |
| `schools.EntitySwitchLog` | aucun |
| `accounts.PasswordResetLog` | aucun |
| `incidents.TechnicalIncident` | aucun |
| `user_files.UserFile` | aucun |
| `token_blacklist.BlacklistedToken` | aucun |
| `token_blacklist.OutstandingToken` | aucun |
| `sessions.Session` | aucun (sauf `--keep-sessions`) |
| `accounts.CustomUser` (rôles `student`, `parent`) | `school` |

### Erreurs de chemin détectées et corrigées

L'écriture initiale supposait des noms de champs plausibles mais inexistants.
La validation par construction de requête les a tous fait apparaître :

| Modèle | Chemin supposé | Chemin réel |
|---|---|---|
| `homework.Homework` | `school_class__school` | `cls__school_year__school` |
| `homework.HomeworkAttachment` | `homework__school_class__school` | `homework__cls__school_year__school` |
| `virtualclass.VirtualRoom` | `school_class__school` | `school` (FK directe) |
| `virtualclass.VirtualRoomAttendance` | `room__school_class__school` | `room__school` |
| `messaging.Message` | `conversation__school` | `sender__school` |
| `messaging.Conversation` | `school` | aucun champ d'académie |
| `announcements.Announcement` | `school` | `author__school` |

### Cas particuliers

- **`messaging.Conversation`** n'a aucun rattachement d'académie : elle est
  définie par ses participants, qui peuvent relever d'académies différentes.
  La rattacher arbitrairement à l'une d'elles serait faux. En mode
  `--academy`, elle est donc **ignorée** et l'omission est consignée dans
  `anomalies` ; elle est bien nettoyée en mode global.

- **`students.Student`** doit être supprimé explicitement : `Student.user` est
  en `on_delete=SET_NULL`, donc supprimer le compte laisse le profil orphelin
  avec `user=NULL`. Ce point a été révélé par un test, pas par relecture.

- **`parents.Parent`** part en cascade avec son compte (`CASCADE`), mais reste
  listé pour couvrir les profils déjà orphelins.

## Modèles techniques Django — intouchés

`auth.Group` · `auth.Permission` · `contenttypes.ContentType` ·
`django_migrations` · `admin.LogEntry`
