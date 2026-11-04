# Matrice des fonctionnalités et de l'aide

Générée par `node frontend/scripts/generer_matrice.mjs` à partir des menus, du routeur, des écrans et de `src/aide/articles.js`.
Le test `src/aide/aide.test.js` échoue si un écran de menu n'a pas d'article.

## superadmin

| Menu | Route | Écran | Module activable | API utilisées par l'écran | Articles d'aide |
|---|---|---|---|---|---|
| Tableau de bord | `/superadmin/dashboard` | SuperAdminDashboard |  | authAPI.listUsers | tableau-de-bord, graphique-paiements |
| Tous les utilisateurs | `/superadmin/users` | SuperAdminUsers |  | authAPI.createUser, authAPI.deleteUser, authAPI.listUsers, authAPI.toggleActive, authAPI.updateUser, schoolsAPI.list | utilisateurs-creer, utilisateurs-gerer, reinitialiser-mdp |
| Académies | `/superadmin/academies` | SuperAdminAcademies |  | schoolsAPI.createAcademy, schoolsAPI.deleteAcademy, schoolsAPI.languageDiagnostic, schoolsAPI.list, schoolsAPI.setupStatus, schoolsAPI.update | academies |
| Gestion Admins | `/superadmin/admins` | SuperAdminAdmins |  | authAPI.createUser, authAPI.deleteUser, authAPI.listUsers, authAPI.toggleActive, authAPI.updateUser, schoolsAPI.list | administrateurs |
| Messages | `/superadmin/messages` | AdminMessages |  | authAPI.recipients, conversationsAPI.create, conversationsAPI.get, conversationsAPI.list, conversationsAPI.markRead, conversationsAPI.reply | messagerie |
| E-mails groupés | `/superadmin/emails` | MassEmail |  | massEmailAPI.campaign, massEmailAPI.campaigns, massEmailAPI.create, massEmailAPI.options, massEmailAPI.preview, massEmailAPI.recipients | emails-groupes |
| Boîte d'envoi | `/superadmin/outbox` | Outbox |  | outboxAPI.attachment, outboxAPI.config, outboxAPI.detail, outboxAPI.list, outboxAPI.retry, outboxAPI.testSend | boite-envoi |
| Incidents techniques | `/superadmin/incidents` | SuperAdminIncidents |  | incidentsAPI.detail, incidentsAPI.list, incidentsAPI.reopen, incidentsAPI.resolve, incidentsAPI.stats, incidentsAPI.update | incidents |
| Mon profil | `/superadmin/profile` | SuperAdminProfile |  |  | mon-profil |
| Élèves | `/superadmin/students` | AdminStudents |  | authAPI.listUsers, classesAPI.list, schoolsAPI.levels, schoolsAPI.years, studentsAPI.bulkDelete, studentsAPI.bulkRemoveFromYear | eleves |
| Enseignants | `/superadmin/teachers` | AdminTeachers |  | authAPI.listUsers, classesAPI.list, subjectsAPI.list, teachersAPI.bulkDelete, teachersAPI.create, teachersAPI.delete | enseignants |
| Parents | `/superadmin/parents` | AdminParents |  | authAPI.listUsers, parentsAPI.bulkDelete, parentsAPI.checkChildAssignment, parentsAPI.create, parentsAPI.delete, parentsAPI.linkStudent | parents |
| Inscriptions | `/superadmin/enrollments` | AdminEnrollments |  | classesAPI.list, schoolsAPI.years, studentsAPI.endOfYearAssistant, studentsAPI.enroll, studentsAPI.enrollAllFromYear, studentsAPI.enrollClass | inscriptions |
| Classes | `/superadmin/classes` | AdminClasses |  | classesAPI.copyFromYear, classesAPI.create, classesAPI.delete, classesAPI.list, classesAPI.setSubjects, classesAPI.update | classes |
| Niveaux | `/superadmin/levels` | AdminLevels |  | schoolsAPI.createLevel, schoolsAPI.deleteLevel, schoolsAPI.levels, schoolsAPI.updateLevel | niveaux |
| Notes | `/superadmin/grades` | AdminGrades |  | classesAPI.list, gradesAPI.allHistory, gradesAPI.bilingual, gradesAPI.bulkDelete, gradesAPI.create, gradesAPI.delete | notes-saisir, notes-modifier |
| Bulletins | `/superadmin/bulletins` | AdminBulletins |  | bulletinsAPI.bulkDelete, bulletinsAPI.commentPreview, bulletinsAPI.createOperation, bulletinsAPI.generateAll, bulletinsAPI.generateClass, bulletinsAPI.list | bulletins-generer |
| Centre d'analyse | `/superadmin/analyses` | Analyses |  | analyticsAPI.filtres | centre-analyse |
| Appréciations | `/superadmin/appreciations` | AdminAppreciations |  | appreciationsAPI.get, appreciationsAPI.preview, appreciationsAPI.reset, appreciationsAPI.save | appreciations |
| Paiements | `/superadmin/payments` | AdminPayments |  | paymentsAPI.bulkDelete, paymentsAPI.cancel, paymentsAPI.create, paymentsAPI.delete, paymentsAPI.generateReceipt, paymentsAPI.history | paiements |
| Transactions carte | `/superadmin/card-transactions` | AdminCardTransactions |  | cardPaymentsAPI.refund, cardPaymentsAPI.transactions | transactions-carte |
| Tarifs et échéances | `/superadmin/tarifs` | Tarifs |  | feeSchedulesAPI.create, feeSchedulesAPI.historique, feeSchedulesAPI.list, feeSchedulesAPI.update, schoolsAPI.levels, schoolsAPI.years | tarifs |
| Situation financière | `/superadmin/situation-financiere` | SituationFinanciere |  | paymentsAPI.situation | situation-financiere |
| Relances de paiement | `/superadmin/payment-reminders` | PaymentReminders |  | feeSchedulesAPI.arrangements, feeSchedulesAPI.create, feeSchedulesAPI.createArrangement, feeSchedulesAPI.delete, feeSchedulesAPI.deleteArrangement, feeSchedulesAPI.list | relances |
| Documents officiels | `/superadmin/official-documents` | AdminOfficialDocuments |  | classesAPI.list, documentTemplatesAPI.list, documentsAPI.batch, documentsAPI.batchIssue, documentsAPI.check, documentsAPI.create | documents-officiels |
| Gabarits des documents | `/superadmin/document-templates` | AdminDocumentTemplates |  | documentTemplatesAPI.action, documentTemplatesAPI.list, documentTemplatesAPI.original, documentTemplatesAPI.preview, documentTemplatesAPI.remove, documentTemplatesAPI.upload | gabarits |
| Absences | `/superadmin/attendance` | AdminAttendance |  | attendanceAPI.create, attendanceAPI.delete, attendanceAPI.list, attendanceAPI.update, schoolsAPI.years, studentsAPI.list | absences |
| Devoirs | `/superadmin/homework` | AdminHomework |  | classesAPI.list, homeworkAPI.bulkDelete, homeworkAPI.create, homeworkAPI.delete, homeworkAPI.list, homeworkAPI.update | devoirs |
| Emploi du temps | `/superadmin/schedule` | AdminSchedule |  |  | emploi-du-temps |
| Salles virtuelles | `/superadmin/virtual` | VirtualRooms |  | classesAPI.list, subjectsAPI.list, virtualAPI.create, virtualAPI.delete, virtualAPI.end, virtualAPI.join | salles-virtuelles |
| Annonces | `/superadmin/announcements` | AdminAnnouncements |  | announcementsAPI.bulkDelete, announcementsAPI.create, announcementsAPI.delete, announcementsAPI.list, announcementsAPI.update, schoolsAPI.years | annonces |
| Paramètres | `/superadmin/settings` | AdminSettings |  | classesAPI.list, schoolsAPI.activateYear, schoolsAPI.closeYear, schoolsAPI.createRoom, schoolsAPI.createRoomType, schoolsAPI.createYear | parametres |
| Fichiers | `/superadmin/user-files` | AdminUserFiles |  | authAPI.listUsers, userFilesAPI.create, userFilesAPI.delete, userFilesAPI.download, userFilesAPI.list, userFilesAPI.replace | fichiers |
| Admissions en ligne | `/superadmin/fha-admissions` | FhaAdmissions | online_admissions | websiteAdminAPI.exportFhaApplications, websiteAdminAPI.fhaApplication, websiteAdminAPI.fhaApplicationSheet, websiteAdminAPI.fhaApplications, websiteAdminAPI.fhaBulkResendConfirmation, websiteAdminAPI.fhaChangeStatus | admissions-en-ligne |
| Modules pédagogiques | `/superadmin/modules` | ModulesPedagogiques |  | suiviAPI.activation, suiviAPI.activer | modules-pedagogiques |
| Suivi pédagogique | `/superadmin/suivi` | SuiviEleves | suivi_pedagogique | suiviAPI.eleves | suivi-eleve, rapports-pedagogiques |
| Compétences | `/superadmin/suivi/referentiels` | SuiviReferentiels | suivi_pedagogique | classesAPI.list, schoolsAPI.levels, subjectsAPI.list, suiviAPI.competences, suiviAPI.creerCompetence, suiviAPI.creerReferentiel | referentiels |
| Examens et évaluations | `/superadmin/evaluations` | EvalEpreuves | evaluations_en_ligne | classesAPI.list, evaluationsAPI.creerEpreuve, evaluationsAPI.epreuves, subjectsAPI.list | epreuves |
| Aide | `/superadmin/aide` | AideGuides |  |  | (cette page) |
| Rapports mensuels | `/superadmin/monthly-reports` | MonthlyReports | monthly_reports | monthlyReportsAPI.generateMonth, monthlyReportsAPI.get, monthlyReportsAPI.list, monthlyReportsAPI.pdf, monthlyReportsAPI.update | rapports-mensuels |
| Site vitrine | `/superadmin/website` | AdminWebsite |  | websiteAdminAPI.contactMessages, websiteAdminAPI.createNews, websiteAdminAPI.deleteContact, websiteAdminAPI.deleteNews, websiteAdminAPI.deletePrereg, websiteAdminAPI.exportPreregs | site-vitrine |
| Logo & Branding | `/superadmin/branding` | AdminBranding |  | schoolsAPI.activateBranding, schoolsAPI.activeBranding, schoolsAPI.deleteBranding, schoolsAPI.listBranding, schoolsAPI.uploadBranding | branding |

## admin

| Menu | Route | Écran | Module activable | API utilisées par l'écran | Articles d'aide |
|---|---|---|---|---|---|
| Tableau de bord | `/admin/dashboard` | AdminDashboard |  | announcementsAPI.list, dashboardAPI.admin | tableau-de-bord |
| Élèves | `/admin/students` | AdminStudents |  | authAPI.listUsers, classesAPI.list, schoolsAPI.levels, schoolsAPI.years, studentsAPI.bulkDelete, studentsAPI.bulkRemoveFromYear | eleves |
| Enseignants | `/admin/teachers` | AdminTeachers |  | authAPI.listUsers, classesAPI.list, subjectsAPI.list, teachersAPI.bulkDelete, teachersAPI.create, teachersAPI.delete | enseignants |
| Parents | `/admin/parents` | AdminParents |  | authAPI.listUsers, parentsAPI.bulkDelete, parentsAPI.checkChildAssignment, parentsAPI.create, parentsAPI.delete, parentsAPI.linkStudent | parents |
| Inscriptions | `/admin/enrollments` | AdminEnrollments |  | classesAPI.list, schoolsAPI.years, studentsAPI.endOfYearAssistant, studentsAPI.enroll, studentsAPI.enrollAllFromYear, studentsAPI.enrollClass | inscriptions |
| Classes | `/admin/classes` | AdminClasses |  | classesAPI.copyFromYear, classesAPI.create, classesAPI.delete, classesAPI.list, classesAPI.setSubjects, classesAPI.update | classes |
| Niveaux | `/admin/levels` | AdminLevels |  | schoolsAPI.createLevel, schoolsAPI.deleteLevel, schoolsAPI.levels, schoolsAPI.updateLevel | niveaux |
| Notes | `/admin/grades` | AdminGrades |  | classesAPI.list, gradesAPI.allHistory, gradesAPI.bilingual, gradesAPI.bulkDelete, gradesAPI.create, gradesAPI.delete | notes-saisir, notes-modifier |
| Bulletins | `/admin/bulletins` | AdminBulletins |  | bulletinsAPI.bulkDelete, bulletinsAPI.commentPreview, bulletinsAPI.createOperation, bulletinsAPI.generateAll, bulletinsAPI.generateClass, bulletinsAPI.list | bulletins-generer |
| Centre d'analyse | `/admin/analyses` | Analyses |  | analyticsAPI.filtres | centre-analyse |
| Appréciations | `/admin/appreciations` | AdminAppreciations |  | appreciationsAPI.get, appreciationsAPI.preview, appreciationsAPI.reset, appreciationsAPI.save | appreciations |
| Absences | `/admin/attendance` | AdminAttendance |  | attendanceAPI.create, attendanceAPI.delete, attendanceAPI.list, attendanceAPI.update, schoolsAPI.years, studentsAPI.list | absences |
| Emploi du temps | `/admin/schedule` | AdminSchedule |  |  | emploi-du-temps |
| Salles virtuelles | `/admin/virtual` | VirtualRooms | virtual_classrooms | classesAPI.list, subjectsAPI.list, virtualAPI.create, virtualAPI.delete, virtualAPI.end, virtualAPI.join | salles-virtuelles |
| Devoirs | `/admin/homework` | AdminHomework |  | classesAPI.list, homeworkAPI.bulkDelete, homeworkAPI.create, homeworkAPI.delete, homeworkAPI.list, homeworkAPI.update | devoirs |
| Paiements | `/admin/payments` | AdminPayments |  | paymentsAPI.bulkDelete, paymentsAPI.cancel, paymentsAPI.create, paymentsAPI.delete, paymentsAPI.generateReceipt, paymentsAPI.history | paiements |
| Transactions carte | `/admin/card-transactions` | AdminCardTransactions |  | cardPaymentsAPI.refund, cardPaymentsAPI.transactions | transactions-carte |
| Tarifs et échéances | `/admin/tarifs` | Tarifs |  | feeSchedulesAPI.create, feeSchedulesAPI.historique, feeSchedulesAPI.list, feeSchedulesAPI.update, schoolsAPI.levels, schoolsAPI.years | tarifs |
| Situation financière | `/admin/situation-financiere` | SituationFinanciere |  | paymentsAPI.situation | situation-financiere |
| Relances de paiement | `/admin/payment-reminders` | PaymentReminders |  | feeSchedulesAPI.arrangements, feeSchedulesAPI.create, feeSchedulesAPI.createArrangement, feeSchedulesAPI.delete, feeSchedulesAPI.deleteArrangement, feeSchedulesAPI.list | relances |
| Documents officiels | `/admin/official-documents` | AdminOfficialDocuments |  | classesAPI.list, documentTemplatesAPI.list, documentsAPI.batch, documentsAPI.batchIssue, documentsAPI.check, documentsAPI.create | documents-officiels |
| Gabarits des documents | `/admin/document-templates` | AdminDocumentTemplates |  | documentTemplatesAPI.action, documentTemplatesAPI.list, documentTemplatesAPI.original, documentTemplatesAPI.preview, documentTemplatesAPI.remove, documentTemplatesAPI.upload | gabarits |
| Messages | `/admin/messages` | AdminMessages |  | authAPI.recipients, conversationsAPI.create, conversationsAPI.get, conversationsAPI.list, conversationsAPI.markRead, conversationsAPI.reply | messagerie |
| E-mails groupés | `/admin/emails` | MassEmail |  | massEmailAPI.campaign, massEmailAPI.campaigns, massEmailAPI.create, massEmailAPI.options, massEmailAPI.preview, massEmailAPI.recipients | emails-groupes |
| Boîte d'envoi | `/admin/outbox` | Outbox |  | outboxAPI.attachment, outboxAPI.config, outboxAPI.detail, outboxAPI.list, outboxAPI.retry, outboxAPI.testSend | boite-envoi |
| Annonces | `/admin/announcements` | AdminAnnouncements |  | announcementsAPI.bulkDelete, announcementsAPI.create, announcementsAPI.delete, announcementsAPI.list, announcementsAPI.update, schoolsAPI.years | annonces |
| Utilisateurs | `/admin/users` | AdminUsers |  | authAPI.createUser, authAPI.deleteUser, authAPI.listUsers, authAPI.toggleActive, authAPI.updateUser | utilisateurs-creer, utilisateurs-gerer, reinitialiser-mdp |
| Fichiers | `/admin/user-files` | AdminUserFiles |  | authAPI.listUsers, userFilesAPI.create, userFilesAPI.delete, userFilesAPI.download, userFilesAPI.list, userFilesAPI.replace | fichiers |
| Admissions en ligne | `/admin/fha-admissions` | FhaAdmissions | online_admissions | websiteAdminAPI.exportFhaApplications, websiteAdminAPI.fhaApplication, websiteAdminAPI.fhaApplicationSheet, websiteAdminAPI.fhaApplications, websiteAdminAPI.fhaBulkResendConfirmation, websiteAdminAPI.fhaChangeStatus | admissions-en-ligne |
| Suivi pédagogique | `/admin/suivi` | SuiviEleves | suivi_pedagogique | suiviAPI.eleves | suivi-eleve, rapports-pedagogiques |
| Compétences | `/admin/suivi/referentiels` | SuiviReferentiels | suivi_pedagogique | classesAPI.list, schoolsAPI.levels, subjectsAPI.list, suiviAPI.competences, suiviAPI.creerCompetence, suiviAPI.creerReferentiel | referentiels |
| Examens et évaluations | `/admin/evaluations` | EvalEpreuves | evaluations_en_ligne | classesAPI.list, evaluationsAPI.creerEpreuve, evaluationsAPI.epreuves, subjectsAPI.list | epreuves |
| Aide | `/admin/aide` | AideGuides |  |  | (cette page) |
| Rapports mensuels | `/admin/monthly-reports` | MonthlyReports | monthly_reports | monthlyReportsAPI.generateMonth, monthlyReportsAPI.get, monthlyReportsAPI.list, monthlyReportsAPI.pdf, monthlyReportsAPI.update | rapports-mensuels |
| Site vitrine | `/admin/website` | AdminWebsite |  | websiteAdminAPI.contactMessages, websiteAdminAPI.createNews, websiteAdminAPI.deleteContact, websiteAdminAPI.deleteNews, websiteAdminAPI.deletePrereg, websiteAdminAPI.exportPreregs | site-vitrine |
| Branding & Logo | `/admin/branding` | AdminBranding |  | schoolsAPI.activateBranding, schoolsAPI.activeBranding, schoolsAPI.deleteBranding, schoolsAPI.listBranding, schoolsAPI.uploadBranding | branding |
| Paramètres | `/admin/settings` | AdminSettings |  | classesAPI.list, schoolsAPI.activateYear, schoolsAPI.closeYear, schoolsAPI.createRoom, schoolsAPI.createRoomType, schoolsAPI.createYear | parametres |
| Mon profil | `/admin/profile` | AdminProfile |  |  | mon-profil |

## teacher

| Menu | Route | Écran | Module activable | API utilisées par l'écran | Articles d'aide |
|---|---|---|---|---|---|
| Tableau de bord | `/teacher/dashboard` | TeacherDashboard |  | announcementsAPI.list, dashboardAPI.teacher | tableau-de-bord |
| Mes classes | `/teacher/classes` | TeacherClasses |  | classesAPI.list, classesAPI.students | tableau-de-bord |
| Notes | `/teacher/grades` | TeacherGrades |  | classesAPI.list, gradesAPI.create, gradesAPI.delete, gradesAPI.history, gradesAPI.list, gradesAPI.listDeleted | notes-saisir, notes-modifier |
| Analyses de mes classes | `/teacher/analyses` | Analyses |  | analyticsAPI.filtres | centre-analyse |
| Suivi pédagogique | `/teacher/suivi` | SuiviEleves | suivi_pedagogique | suiviAPI.eleves | suivi-eleve, rapports-pedagogiques |
| Compétences | `/teacher/suivi/referentiels` | SuiviReferentiels | suivi_pedagogique | classesAPI.list, schoolsAPI.levels, subjectsAPI.list, suiviAPI.competences, suiviAPI.creerCompetence, suiviAPI.creerReferentiel | referentiels |
| Examens et évaluations | `/teacher/evaluations` | EvalEpreuves | evaluations_en_ligne | classesAPI.list, evaluationsAPI.creerEpreuve, evaluationsAPI.epreuves, subjectsAPI.list | epreuves |
| Aide | `/teacher/aide` | AideGuides |  |  | (cette page) |
| Absences | `/teacher/attendance` | TeacherAttendance |  | attendanceAPI.create, attendanceAPI.delete, attendanceAPI.list, attendanceAPI.update, schoolsAPI.years, studentsAPI.list | absences |
| Devoirs | `/teacher/homework` | TeacherHomework |  | homeworkAPI.create, homeworkAPI.delete, homeworkAPI.list, homeworkAPI.update, schoolsAPI.years, teachersAPI.myClasses | devoirs |
| Emploi du temps | `/teacher/schedule` | TeacherSchedule |  | scheduleAPI.list | emploi-du-temps |
| Salles virtuelles | `/teacher/virtual` | VirtualRooms | virtual_classrooms | classesAPI.list, subjectsAPI.list, virtualAPI.create, virtualAPI.delete, virtualAPI.end, virtualAPI.join | salles-virtuelles |
| Messages | `/teacher/messages` | TeacherMessages |  | authAPI.recipients, conversationsAPI.create, conversationsAPI.get, conversationsAPI.list, conversationsAPI.markRead, conversationsAPI.reply | messagerie |
| Annonces | `/teacher/announcements` | SharedAnnouncements |  | announcementsAPI.list | annonces |
| Mon profil | `/teacher/profile` | TeacherProfile |  | authAPI.changePassword, authAPI.me, authAPI.updateMe | mon-profil |

## parent

| Menu | Route | Écran | Module activable | API utilisées par l'écran | Articles d'aide |
|---|---|---|---|---|---|
| Accueil | `/parent/home` | ParentHome |  | announcementsAPI.list, dashboardAPI.parent | famille-vie |
| Mes enfants | `/parent/children` | ParentChildren |  | parentsAPI.me | famille-vie |
| Notes | `/parent/grades` | ParentGrades |  | gradesAPI.averages, gradesAPI.bilingual, gradesAPI.list, parentsAPI.me, schoolsAPI.years | famille-notes |
| Analyse des résultats | `/parent/analyses` | MesAnalyses |  | analyticsAPI.eleve, analyticsAPI.mesEleves | analyses-famille |
| Suivi pédagogique | `/parent/suivi` | SuiviEleves | suivi_familles | suiviAPI.eleves | famille-suivi |
| Résultats des épreuves | `/parent/evaluations` | EvalMes | evaluations_en_ligne | evaluationsAPI.mesEpreuves, evaluationsAPI.resultats | famille-suivi |
| Aide | `/parent/aide` | AideGuides |  |  | (cette page) |
| Absences | `/parent/attendance` | ParentAttendance |  | attendanceAPI.list, parentsAPI.me | famille-vie |
| Emploi du temps | `/parent/schedule` | ParentSchedule |  | parentsAPI.me, scheduleAPI.byClass | emploi-du-temps |
| Salles virtuelles | `/parent/virtual` | VirtualRooms | virtual_classrooms | classesAPI.list, subjectsAPI.list, virtualAPI.create, virtualAPI.delete, virtualAPI.end, virtualAPI.join | salles-virtuelles |
| Devoirs | `/parent/homework` | ParentHomework |  | homeworkAPI.list | famille-vie |
| Paiements | `/parent/payments` | ParentPayments |  | parentsAPI.me, paymentsAPI.list, schoolsAPI.years | famille-paiements |
| Bulletins | `/parent/bulletins` | ParentBulletins |  | bulletinsAPI.list, schoolsAPI.years | famille-notes |
| Messages | `/parent/messages` | ParentMessages |  | authAPI.recipients, conversationsAPI.create, conversationsAPI.get, conversationsAPI.list, conversationsAPI.markRead, conversationsAPI.reply | messagerie |
| Mon profil | `/parent/profile` | ParentProfile |  | authAPI.changePassword, authAPI.me, authAPI.updateMe, parentsAPI.list, schoolsAPI.years | mon-profil |
| Annonces | `/parent/announcements` | SharedAnnouncements |  | announcementsAPI.list | annonces |

## student

| Menu | Route | Écran | Module activable | API utilisées par l'écran | Articles d'aide |
|---|---|---|---|---|---|
| Accueil | `/student/home` | StudentHome |  | announcementsAPI.list, dashboardAPI.student | famille-vie |
| Mes notes | `/student/grades` | StudentGrades |  | gradesAPI.averages, gradesAPI.list, schoolsAPI.years | famille-notes |
| Analyse des résultats | `/student/analyses` | MesAnalyses |  | analyticsAPI.eleve, analyticsAPI.mesEleves | analyses-famille |
| Mon suivi | `/student/suivi` | SuiviEleves | suivi_familles | suiviAPI.eleves | famille-suivi |
| Mes épreuves | `/student/evaluations` | EvalMes | evaluations_en_ligne | evaluationsAPI.mesEpreuves, evaluationsAPI.resultats | passer-epreuve |
| Aide | `/student/aide` | AideGuides |  |  | (cette page) |
| Absences | `/student/attendance` | StudentAttendance |  | attendanceAPI.list | famille-vie |
| Devoirs | `/student/homework` | StudentHomework |  | homeworkAPI.list | famille-vie |
| Emploi du temps | `/student/schedule` | StudentSchedule |  | scheduleAPI.list | emploi-du-temps |
| Salles virtuelles | `/student/virtual` | VirtualRooms | virtual_classrooms | classesAPI.list, subjectsAPI.list, virtualAPI.create, virtualAPI.delete, virtualAPI.end, virtualAPI.join | salles-virtuelles |
| Bulletins | `/student/bulletins` | StudentBulletins |  | bulletinsAPI.list, schoolsAPI.years | famille-notes |
| Messages | `/student/messages` | StudentMessages |  | authAPI.recipients, conversationsAPI.create, conversationsAPI.get, conversationsAPI.list, conversationsAPI.markRead, conversationsAPI.reply | messagerie |
| Annonces | `/student/announcements` | SharedAnnouncements |  | announcementsAPI.list | annonces |
| Mon profil | `/student/profile` | StudentProfile |  | attendanceAPI.list, authAPI.changePassword, authAPI.me, gradesAPI.list, homeworkAPI.list, schoolsAPI.years | mon-profil |

Écrans sans article : 0.
