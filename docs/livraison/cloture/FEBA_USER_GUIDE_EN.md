# FEBA user guide

This guide mirrors the help centre built into FEBA ("Help" menu), generated from the same source.

## Contents

- **Getting started**
  - [How do I sign in to FEBA?](#connexion)
  - [What happens at first sign-in or after a password reset?](#premiere-connexion)
  - [How do I update my details or change my password?](#mon-profil)
  - [How do I switch academy or language?](#academie-langue)
  - [How do I search, sort and export a list?](#recherche-listes)
- **Administration**
  - [What is the dashboard for?](#tableau-de-bord)
  - [How do I create a user account?](#utilisateurs-creer)
  - [How do I edit, disable or delete a user?](#utilisateurs-gerer)
  - [How do I reset a user's password?](#reinitialiser-mdp)
  - [How do I manage an academy's administrators?](#administrateurs)
  - [How do I create and configure an academy?](#academies)
  - [How do I enable an optional module for an academy?](#modules-pedagogiques)
  - [How do I configure the school: years, subjects and rooms?](#parametres)
  - [How do I change an academy's logo?](#branding)
  - [How do I handle a technical incident?](#incidents)
  - [How do I send an email to a group?](#emails-groupes)
  - [How do I check that an email was sent?](#boite-envoi)
- **School management**
  - [How do I add a student?](#eleves)
  - [How do I assign a teacher to a class and subjects?](#enseignants)
  - [How do I link a parent to their children?](#parents)
  - [How do I enrol students in a new year or promote them?](#inscriptions)
  - [How do I create a new class?](#classes)
  - [How do I create school levels?](#niveaux)
- **Teaching and learning**
  - [How do I record an official grade?](#notes-saisir)
  - [How do I edit, delete or restore a grade?](#notes-modifier)
  - [How do I generate a report card?](#bulletins-generer)
  - [How do I customise report card appreciations?](#appreciations)
  - [How do I create a competency framework?](#referentiels)
  - [How do I follow a student's progress?](#suivi-eleve)
  - [How do I generate and publish a follow-up report?](#rapports-pedagogiques)
  - [How do I create questions in the bank?](#banque-questions)
  - [How do I create, publish and mark an online test?](#epreuves)
  - [How do I take an online test?](#passer-epreuve)
  - [How do I produce and send monthly reports?](#rapports-mensuels)
- **School life**
  - [How do I record an absence or late arrival?](#absences)
  - [How do I give homework to a class?](#devoirs)
  - [How do I build the timetable?](#emploi-du-temps)
  - [How do I publish an announcement?](#annonces)
  - [How do I send a message?](#messagerie)
  - [How do I hold or join an online class?](#salles-virtuelles)
- **Payments**
  - [How do I record a payment and produce a receipt?](#paiements)
  - [How do I refund a card payment?](#transactions-carte)
  - [How do I configure payment reminders?](#relances)
- **Documents and files**
  - [How do I produce a certificate or diploma?](#documents-officiels)
  - [How do I prepare a diploma or certificate template?](#gabarits)
  - [How do I upload a file for a user?](#fichiers)
- **Public website and admissions**
  - [How do I handle website messages and pre-registrations?](#site-vitrine)
  - [How do I process an online application?](#admissions-en-ligne)
- **Family area**
  - [How do I view grades and download a report card?](#famille-notes)
  - [How do I follow competencies and test results?](#famille-suivi)
  - [How do I view my payments and receipts?](#famille-paiements)
  - [Where do I see homework, attendance, timetable and announcements?](#famille-vie)

## Getting started

<a id="connexion"></a>
### How do I sign in to FEBA?

**What it is for.** Access your area with the email address and password provided by the school.

**Who can use it.** Super administrator, Administrator, Teacher, Parent, Student

**Prerequisites.**

- An account created by the school administration.

**Where to find it.** Menu « Sign-in »

**Steps.**

1. Open the sign-in page (the website's "User area" button, or /login).
2. Enter your email address and password.
3. Click "Se connecter / Sign in" or press Enter.
4. You land on the dashboard or home page of your profile.

**Important fields.**

- Email address, password (the eye icon shows it).

**Expected result.** Your area opens according to your profile.

**Common errors.**

- *"Invalid credentials"* : Check the address and password (capital letters). After several attempts, ask the administration for a reset.
- *"This account is disabled"* : Only the administration can reactivate the account.
- *Message saying the server cannot be reached* : Your network or the server is unavailable: your credentials are not at fault. Try again a little later.

**Effects on other modules.** Clicking the logo on the sign-in page takes you back to the public website home page.

**Permissions.** Any active account.

<a id="premiere-connexion"></a>
### What happens at first sign-in or after a password reset?

**What it is for.** Replace the temporary password given by the administration with a personal password.

**Who can use it.** Super administrator, Administrator, Teacher, Parent, Student

**Prerequisites.**

- The temporary password received from the administration.

**Where to find it.** Menu « Sign-in »

**Steps.**

1. Sign in with the temporary password.
2. The "New password required" screen appears.
3. Enter the temporary password, then the new one twice.
4. Click "Set my new password".

**Important fields.**

- At least 8 characters, not only digits, different from your name and email, not a common password.

**Expected result.** Your area opens; the temporary password no longer works.

**Common errors.**

- *"Passwords do not match"* : Type exactly the same password in both fields.

**Effects on other modules.** Until the password is changed, no other page is accessible.

**Permissions.** Any account whose password was reset.

<a id="mon-profil"></a>
### How do I update my details or change my password?

**What it is for.** Update your contact details and choose a new password.

**Who can use it.** Super administrator, Administrator, Teacher, Parent, Student

**Prerequisites.**

- Know your current password.

**Where to find it.** Menu « My profile » : `/superadmin/profile`, `/admin/profile`, `/teacher/profile`, `/parent/profile`, `/student/profile`

**Steps.**

1. Open "My profile" in the menu.
2. In "Personal information", change first name, last name or phone, then "Save".
3. In "Change password", enter the current one, then the new one twice.
4. Click "Change password".

**Important fields.**

- The email address cannot be changed here: ask the administration.

**Expected result.** Confirmation shown: "Profile updated!" or "Password changed successfully."

**Common errors.**

- *Current password rejected* : If you forgot it, ask the administration for a reset: FEBA does not send reset links by email.

**Effects on other modules.** The new password applies from the next sign-in.

**Permissions.** Each user, for their own account.

<a id="academie-langue"></a>
### How do I switch academy or language?

**What it is for.** Choose the academy whose data you view, and the interface language.

**Who can use it.** Super administrator, Administrator, Teacher, Parent, Student

**Prerequisites.**

- Have access to several academies for the selector (super administrator).

**Where to find it.** Menu « Academy selector and language »

**Steps.**

1. At the top of the page, open the academy selector.
2. Choose an academy, or "All academies" for a consolidated view.
3. Click FR or EN to change the language.

**Expected result.** Lists reload for the chosen academy; the language is remembered.

**Common errors.**

- *A creation is refused in "All academies" mode* : First choose a specific academy: each item belongs to a single academy.

**Effects on other modules.** Super administrators have no academy: they only appear in lists in "All academies" mode.

**Permissions.** Selector: super administrator. Language: everyone.

<a id="recherche-listes"></a>
### How do I search, sort and export a list?

**What it is for.** Quickly find an item in FEBA tables.

**Who can use it.** Super administrator, Administrator, Teacher, Parent, Student

**Where to find it.** Menu « Lists and tables »

**Steps.**

1. Type in the "Search..." field above the table.
2. Click a column header to sort, click again to reverse.
3. Use the arrows at the bottom of the table to change page.
4. When the screen offers it, "Excel export" or "Export CSV" downloads the list.
5. The bell at the top of the page opens your notifications; a click leads to the related item.

**Expected result.** The table only shows matching rows.

**Common errors.**

- *An expected row does not appear* : Check the filters (year, class, period) and the selected academy.

**Permissions.** Depends on the screen.

## Administration

<a id="tableau-de-bord"></a>
### What is the dashboard for?

**What it is for.** Overview: active students, teachers, classes, monthly revenue, latest payments and announcements.

**Who can use it.** Super administrator, Administrator, Teacher

**Prerequisites.**

- An active school year (Settings).

**Where to find it.** Menu « Dashboard » : `/superadmin/dashboard`, `/admin/dashboard`, `/teacher/dashboard`

**Steps.**

1. Open "Dashboard".
2. Read the figures for the active school year; click an item to open it.
3. Teacher: "My classes" lists your classes and their students.

**Expected result.** Figures reflect the selected academy.

**Common errors.**

- *Figures at zero* : Check that a school year is active in Settings.

**Permissions.** Super administrator, administrator, teacher (limited view).

<a id="utilisateurs-creer"></a>
### How do I create a user account?

**What it is for.** Give FEBA access to a student, parent, teacher or administrator.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- Choose the account's academy in the selector (except super administrators).

**Where to find it.** Menu « Users » : `/superadmin/users`, `/admin/users`

**Steps.**

1. Open "All users" (super administrator) or "Users" (administrator).
2. Click "New user".
3. Fill in first name, last name, email, phone and role.
4. Enter a temporary password and its confirmation.
5. Click "Save".
6. For a student, parent or teacher, then create their record (Students, Parents or Teachers) linked to this account.

**Important fields.**

- Unique email: it is the sign-in identifier.
- Role: an administrator can only create teachers, parents and students.

**Expected result.** Confirmation shown: "User created successfully!"; the user must change their password at first sign-in.

**Common errors.**

- *Email already used* : Search for the existing account instead of creating a second one.
- *Password rejected* : Follow the displayed rules (at least 8 characters, not too common).

**Effects on other modules.** Without a Student, Parent or Teacher record, the account can sign in but sees no school data.

**Permissions.** Super administrator: all roles. Administrator: teacher, parent, student of their academy.

<a id="utilisateurs-gerer"></a>
### How do I edit, disable or delete a user?

**What it is for.** Keep accounts up to date and cut access without losing history.

**Who can use it.** Super administrator, Administrator

**Where to find it.** Menu « Users » : `/superadmin/users`, `/admin/users`

**Steps.**

1. Open the user list and filter by role if needed.
2. Pencil: edit the account. Switch: "Disable" or "Enable".
3. Bin: delete, after confirmation.

**Expected result.** A disabled account can no longer sign in; its open sessions are closed.

**Common errors.**

- *Deletion refused* : Prefer disabling: an account linked to grades, payments or report cards must be kept.

**Effects on other modules.** Disabling keeps all data; deletion is permanent.

**Permissions.** Super administrator: all. Administrator: teachers, parents, students of their academy.

<a id="reinitialiser-mdp"></a>
### How do I reset a user's password?

**What it is for.** Unblock a user who forgot their password.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- Be allowed to manage this account (see Permissions).

**Where to find it.** Menu « Users » : `/superadmin/users`, `/admin/users`

**Steps.**

1. In the user list (or "Admin management"), click the key icon on the row.
2. Check the displayed identity, then enter the temporary password twice.
3. For a super administrator, also enter your own password (identity check).
4. Tick the confirmation box and click "Reset".
5. Give the temporary password to the user through a safe channel.

**Important fields.**

- Temporary password: same rules as any password.

**Expected result.** The user's sessions are closed; they will choose a new password at next sign-in. The operation is logged without the password.

**Common errors.**

- *No key icon on your own row* : Change your password in "My profile".
- *"Your password is incorrect: reset refused."* : Enter your own password, not the person's.

**Effects on other modules.** The holder of a super administrator account is notified by email.

**Permissions.** Administrator: teachers, parents, students of their academy. Super administrator: any other account, including another super administrator with their own password.

<a id="administrateurs"></a>
### How do I manage an academy's administrators?

**What it is for.** Create and manage the accounts that administer an academy.

**Who can use it.** Super administrator

**Prerequisites.**

- The academy exists (Academies).

**Where to find it.** Menu « Admin management » : `/superadmin/admins`

**Steps.**

1. Open "Admin management", then "New admin".
2. Fill in identity, email, school and temporary password.
3. Save. Row actions let you edit, reset the password, disable or delete.

**Important fields.**

- School: the administrator only sees this academy.

**Expected result.** Confirmation shown: "Administrator created!"

**Common errors.**

- *Empty list* : Switch to "All academies" or choose the right academy.

**Effects on other modules.** An administrator can neither create nor edit another administrator.

**Permissions.** Super administrator only.

<a id="academies"></a>
### How do I create and configure an academy?

**What it is for.** Add a school isolated from the others, with its type and language programme.

**Who can use it.** Super administrator

**Where to find it.** Menu « Academies » : `/superadmin/academies`

**Steps.**

1. Open "Academies", then "New academy".
2. Choose the academy type and the language programme.
3. Enter the name and internal code (permanent), then save.
4. Select the new academy in the selector and complete the "Remaining setup": years, levels, subjects, classes, logo.

**Important fields.**

- Language programme: languages of subjects, tracks and report cards, separate from the interface language.
- Internal code: cannot be changed later.

**Expected result.** Confirmation shown: "Academy created and initialised."

**Common errors.**

- *Warning "Existing data incompatible with this programme"* : Nothing is deleted: fix the listed subjects or classes before changing the programme.

**Effects on other modules.** Disabling an academy cuts access to its accounts without erasing its data.

**Permissions.** Super administrator only.

<a id="modules-pedagogiques"></a>
### How do I enable an optional module for an academy?

**What it is for.** Open teaching follow-up, online exams, monthly reports, online admissions or virtual rooms to an academy.

**Who can use it.** Super administrator

**Where to find it.** Menu « Teaching modules » : `/superadmin/modules`

**Steps.**

1. Open "Teaching modules".
2. Tick each academy's modules, then save.
3. Reload the page to see the updated menu.

**Important fields.**

- "Family access": publishes validated follow-up to students and parents.

**Expected result.** The matching menu entries appear for this academy.

**Common errors.**

- *The menu did not change* : Reload the page.

**Effects on other modules.** Disabling a module hides its screens; data is kept.

**Permissions.** Super administrator only.

<a id="parametres"></a>
### How do I configure the school: years, subjects and rooms?

**What it is for.** Set the school's information, school years, subjects and rooms.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- The data shown belongs to the academy chosen in the selector at the top of the page.

**Where to find it.** Menu « Settings » : `/superadmin/settings`, `/admin/settings`

**Steps.**

1. Open "Settings".
2. "School information": name, city, address, phone, email, then "Save".
3. School years: "New year", then "Activate" on the current year.
4. Subjects: "New subject" with name, code and coefficient.
5. Rooms: create room types then rooms (capacity, status).

**Important fields.**

- Coefficient: weight of the subject in averages and report cards.

**Expected result.** Confirmation shown: "Year activated!", "Subject created!", "Room created!"

**Common errors.**

- *"Select an academy to edit its information."* : Choose the academy in the selector.

**Effects on other modules.** The active year filters the dashboard; coefficients change the averages of report cards generated afterwards.

**Permissions.** Super administrator, administrator.

<a id="branding"></a>
### How do I change an academy's logo?

**What it is for.** Publish the official logo shown on the sign-in page, dashboards, report cards and documents.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- The data shown belongs to the academy chosen in the selector at the top of the page.
- A PNG, JPEG or WebP file of 5 MB at most.

**Where to find it.** Menu « Logo & branding » : `/superadmin/branding`, `/admin/branding`

**Steps.**

1. Open "Logo & branding".
2. In "Upload a new logo", give a version label and choose the file.
3. Check the preview and upload: the logo becomes active.
4. The history lets you reactivate an older version.

**Expected result.** Confirmation shown: "Logo uploaded and activated successfully! Applied across the application."

**Common errors.**

- *"Format refused"* : Use PNG, JPEG or WebP.
- *"File too large"* : Reduce the image below 5 MB.

**Effects on other modules.** Report cards and documents produced afterwards carry the new logo; existing PDFs do not change.

**Permissions.** Super administrator, administrator.

<a id="incidents"></a>
### How do I handle a technical incident?

**What it is for.** Follow the server errors and monitoring alerts recorded automatically.

**Who can use it.** Super administrator

**Where to find it.** Menu « Technical incidents » : `/superadmin/incidents`

**Steps.**

1. Open "Technical incidents"; filter by status or severity.
2. Open an incident: message, endpoint, context (sensitive data redacted), occurrences.
3. Fill in the internal note and the validation levels with their evidence.
4. "Mark resolved" only when all evidence is gathered; "Reopen" if the defect returns.

**Important fields.**

- Validation levels: fix developed, tested automatically, tested locally, tested in production, real journey validated by the user concerned.

**Expected result.** The status and its history are kept.

**Common errors.**

- *An incident reappears* : A new occurrence of the same defect is added to the existing incident: reopen it.

**Effects on other modules.** "Monitoring" alerts (backup, certificates, disk, video conferencing) repeat as long as the cause persists.

**Permissions.** Super administrator only.

<a id="emails-groupes"></a>
### How do I send an email to a group?

**What it is for.** Write to profiles of an academy (parents, teachers...) at once.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- The data shown belongs to the academy chosen in the selector at the top of the page.

**Where to find it.** Menu « Group emails » : `/superadmin/emails`, `/admin/emails`

**Steps.**

1. Open "Group emails".
2. Choose the profile types, then tick the recipients.
3. Enter the subject and content, add attachments if needed.
4. "Preview", then "Confirm sending".
5. Check the report in "Recent sends".

**Important fields.**

- Each recipient receives an individual message: no address is visible to others.

**Expected result.** The report shows delivered, failed and skipped messages.

**Common errors.**

- *Failures in the report* : Open the Outbox to see the cause and retry.

**Effects on other modules.** All sends are archived in the Outbox.

**Permissions.** Super administrator, administrator.

<a id="boite-envoi"></a>
### How do I check that an email was sent?

**What it is for.** View every email sent by the platform, with content, attachments and attempts.

**Who can use it.** Super administrator, Administrator

**Where to find it.** Menu « Outbox » : `/superadmin/outbox`, `/admin/outbox`

**Steps.**

1. Open "Outbox".
2. Filter by recipient, status, origin or date, then "Filter".
3. "Open" shows the details; "Retry this send" retries a failed send.

**Expected result.** Status of each send and attempt history.

**Common errors.**

- *Status "Failed"* : Read the cause in the attempt history (invalid address, mail server).

**Permissions.** Super administrator, administrator.

## School management

<a id="eleves"></a>
### How do I add a student?

**What it is for.** Create a student's school record and link it to their account.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- A user account with the Student role (Users).
- An existing class and school year.

**Where to find it.** Menu « Students » : `/superadmin/students`, `/admin/students`

**Steps.**

1. Open "Students", then "Add a student".
2. Search for the student's account in "Student user account".
3. Complete date of birth, gender, class and school year, then save.
4. "View" opens the record; "New year" enrols the student for the following year.

**Important fields.**

- Registration number: the student's identifier in the school.

**Expected result.** Confirmation shown: "Student created!"; the student appears in their class.

**Common errors.**

- *The account does not appear in the search* : First create the account with the Student role, in the same academy.

**Effects on other modules.** The student becomes visible to their class teachers, linked parents, grades, attendance and report cards.

**Permissions.** Super administrator, administrator.

<a id="enseignants"></a>
### How do I assign a teacher to a class and subjects?

**What it is for.** Create the teacher record and set their classes and subjects: they determine what they can grade.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- A user account with the Teacher role.
- Classes and subjects created.

**Where to find it.** Menu « Teachers » : `/superadmin/teachers`, `/admin/teachers`

**Steps.**

1. Open "Teachers", then "Add".
2. Choose the account, speciality, contract type and hiring date.
3. "Assigned classes": add each class. "Assigned subjects": add each subject.
4. Save. "Teacher assignments" summarises class by class.

**Important fields.**

- Contract type: Permanent, Contract or Hourly.

**Expected result.** Confirmation shown: "Teacher created!"; their classes appear in "My classes".

**Common errors.**

- *The teacher sees "No class assigned"* : Add their classes and subjects on their record.

**Effects on other modules.** A teacher only grades, creates tests and takes attendance in their classes and subjects.

**Permissions.** Super administrator, administrator.

<a id="parents"></a>
### How do I link a parent to their children?

**What it is for.** Create the parent record and link the students they are responsible for.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- A Parent account and the students' records.

**Where to find it.** Menu « Parents » : `/superadmin/parents`, `/admin/parents`

**Steps.**

1. Open "Parents", then "Add".
2. Choose the account, occupation and address.
3. In "Linked students", add each child, then save.

**Expected result.** The parent sees their children in "My children".

**Common errors.**

- *"No child linked to your account" on the parent side* : Add the students in "Linked students".

**Effects on other modules.** The parent only accesses the grades, report cards, attendance, homework, payments and messages of these children.

**Permissions.** Super administrator, administrator.

<a id="inscriptions"></a>
### How do I enrol students in a new year or promote them?

**What it is for.** Manage enrolments, transfers and promotions.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- The target year and its classes exist.

**Where to find it.** Menu « Enrolments » : `/superadmin/enrollments`, `/admin/enrollments`

**Steps.**

1. Open "Enrolments".
2. "Individual enrolment": one student, target year, target class and promotion status.
3. "Class promotion": source class, target year and, if needed, new class, then "Promote this class".
4. "Year promotion": source year and target year, then "Run year promotion".
5. "End-of-year wizard": per-student decisions, enrolments and report cards at once. "Student history" traces their path.

**Important fields.**

- The two years must be different.

**Expected result.** Number of students enrolled and decisions applied.

**Common errors.**

- *"All already enrolled in the target year."* : Nothing to do: the operation never enrols twice.

**Effects on other modules.** Grades and report cards of previous years stay attached to their year.

**Permissions.** Super administrator, administrator.

<a id="classes"></a>
### How do I create a new class?

**What it is for.** Create a class, its subjects and its language track.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- The level and school year exist.

**Where to find it.** Menu « Classes » : `/superadmin/classes`, `/admin/classes`

**Steps.**

1. Open "Classes", then "New class".
2. Enter the name (e.g. CM2-A), level, year, capacity and language track.
3. Save, then "Manage subjects" to choose the class's subjects.
4. "Copy from a year" recreates a year's classes in another.

**Important fields.**

- Language track: French, English or bilingual; it determines expected subjects and the report card layout.

**Expected result.** Confirmation shown: "Class created!". The "Incomplete" badge flags missing subjects.

**Common errors.**

- *"This class no longer exists"* : Someone deleted it: the list is refreshed.

**Effects on other modules.** Students, teachers, timetables, homework and report cards rely on the class.

**Permissions.** Super administrator, administrator.

<a id="niveaux"></a>
### How do I create school levels?

**What it is for.** Define the levels (CI, CP, CM1...) before creating classes.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- The data shown belongs to the academy chosen in the selector at the top of the page.

**Where to find it.** Menu « Levels » : `/superadmin/levels`, `/admin/levels`

**Steps.**

1. Open "Levels", then "New level".
2. Enter the name, display order and school cycle.
3. Save.

**Important fields.**

- Cycle: it sets the grading scale (out of 10 or 20) of the report card.

**Expected result.** Confirmation shown: "Level created!"

**Common errors.**

- *"Select an academy to create a level."* : Choose the academy in the selector.

**Effects on other modules.** The level's cycle also selects the appreciation scale used.

**Permissions.** Super administrator, administrator.

## Teaching and learning

<a id="notes-saisir"></a>
### How do I record an official grade?

**What it is for.** Enter the grades that count in averages and report cards.

**Who can use it.** Super administrator, Administrator, Teacher

**Prerequisites.**

- For a teacher: the class and subject must be assigned to them.

**Where to find it.** Menu « Grades » : `/superadmin/grades`, `/admin/grades`, `/teacher/grades`

**Steps.**

1. Open "Grades".
2. "Add a grade" (or "Enter a grade"): student, subject, period, type and value.
3. For a whole class, use "Bulk entry".
4. Save.

**Important fields.**

- Period: Term 1, 2, 3 or Exam.
- Type: homework, quiz, test, exam, practical work or other.

**Expected result.** Confirmation shown: "Grade added!"; the related report card is flagged "PDF to regenerate".

**Common errors.**

- *Refusal for a teacher* : The subject is not assigned to the teacher in this class: see Teachers.

**Effects on other modules.** The grade enters averages; the student and parents see it in "My grades" / "Grades".

**Permissions.** Super administrator, administrator; teacher in their classes and subjects.

<a id="notes-modifier"></a>
### How do I edit, delete or restore a grade?

**What it is for.** Correct a grade while keeping a record of each change.

**Who can use it.** Super administrator, Administrator, Teacher

**Where to find it.** Menu « Grades » : `/superadmin/grades`, `/admin/grades`, `/teacher/grades`

**Steps.**

1. In "Grades", find the row and click "Edit".
2. To delete: "Delete", enter the justification (required), confirm.
3. "Deleted" (or "Show deleted") lists removed grades; "Restore" brings them back.
4. "History" shows each change: old and new value, author, justification, date.

**Important fields.**

- Justification: required for any deletion.

**Expected result.** The grade is never erased: it is marked deleted and stays restorable.

**Common errors.**

- *"A justification is required to delete a grade."* : Enter a reason.
- *"Already deleted."* : Someone deleted it before you: refresh the list.

**Effects on other modules.** Averages and the report card are recalculated at the next generation.

**Permissions.** Super administrator, administrator; teacher in their subjects.

<a id="bulletins-generer"></a>
### How do I generate a report card?

**What it is for.** Produce the PDF report cards of a student, a class or the whole academy.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- Grades entered for the period; correct subjects and coefficients.

**Where to find it.** Menu « Report cards » : `/superadmin/bulletins`, `/admin/bulletins`

**Steps.**

1. Open "Report cards".
2. One student: "Preview / generate a report card".
3. One class: "Generate a class's report cards", choose class, period and year, then "Review before generation".
4. Whole academy: "Generate all report cards".
5. Follow the progress, then download the PDF from the list.

**Important fields.**

- Common comment (optional): replaces the existing principal's comments.

**Expected result.** Confirmation shown: "Report card generated successfully! PDF available."

**Common errors.**

- *"no grades: skipped"* : Enter the student's grades for this period.
- *"PDF to regenerate"* : A grade changed since: generate again.

**Effects on other modules.** Students and parents download the report card in "Report cards". Regenerating keeps the principal's comments.

**Permissions.** Super administrator, administrator.

<a id="appreciations"></a>
### How do I customise report card appreciations?

**What it is for.** Define the remarks (Very good, Fair...) according to the grade percentage.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- The data shown belongs to the academy chosen in the selector at the top of the page.

**Where to find it.** Menu « Appreciations » : `/superadmin/appreciations`, `/admin/appreciations`

**Steps.**

1. Open "Appreciations" and choose the scope (academy or cycle).
2. "Customise this academy's scale" or "Create a scale for this cycle".
3. For each row: French label, English label, threshold in %, active or not.
4. Test with "Preview", then "Save".

**Important fields.**

- The lowest threshold must be 0%; at least one active appreciation.

**Expected result.** Confirmation shown: "Scale saved."

**Common errors.**

- *Cannot delete an appreciation* : It appears on issued report cards: disable it.

**Effects on other modules.** Applies to report cards generated afterwards.

**Permissions.** Super administrator, administrator.

<a id="referentiels"></a>
### How do I create a competency framework?

**What it is for.** List what each student must be able to do, by subject or programme.

**Who can use it.** Super administrator, Administrator, Teacher

**Prerequisites.**

- "Teaching follow-up" module enabled for the academy.

**Where to find it.** Menu « Teaching follow-up » (optional academy module) : `/superadmin/suivi/referentiels`, `/admin/suivi/referentiels`, `/teacher/suivi/referentiels`

**Steps.**

1. Open "Competencies" (Frameworks and competencies).
2. "New framework", for example "French CM1".
3. Add its competencies, grouped by domain, with their criteria.
4. "Import" or "Duplicate" speed up entry.

**Important fields.**

- Mastery levels: To work on, To strengthen, In progress, Acquired.

**Expected result.** Confirmation shown: "Framework saved."

**Common errors.**

- *A competency cannot be deleted* : A competency already assessed is archived: its history is kept.

**Effects on other modules.** Follow-up never changes grades or report cards.

**Permissions.** Super administrator, administrator, teacher.

<a id="suivi-eleve"></a>
### How do I follow a student's progress?

**What it is for.** Assess competencies, record follow-up assessments, observe participation and set goals.

**Who can use it.** Super administrator, Administrator, Teacher

**Prerequisites.**

- A competency framework.

**Where to find it.** Menu « Teaching follow-up » (optional academy module) : `/superadmin/suivi`, `/admin/suivi`, `/teacher/suivi`

**Steps.**

1. Open "Teaching follow-up" and the student's record.
2. Competencies tab: "Assess a competency" (level, date, comment).
3. Results tab: "Add a teaching assessment" or "Observe participation".
4. Goals tab: "Create a goal".
5. "Assess a class" assesses one competency for all students; "Alerts" lists students to watch.

**Important fields.**

- Follow-up assessment: does not count in the report card.

**Expected result.** Confirmation shown: "Saved."; the summary and charts update.

**Common errors.**

- *"No student here."* : A teacher only sees students of their classes.

**Effects on other modules.** Visible to families only if the academy has opened family access.

**Permissions.** Super administrator, administrator, teacher.

<a id="rapports-pedagogiques"></a>
### How do I generate and publish a follow-up report?

**What it is for.** Produce a PDF teaching report and make it visible to the family.

**Who can use it.** Super administrator, Administrator, Teacher

**Prerequisites.**

- Assessments in the student's record.

**Where to find it.** Menu « Teaching follow-up » (optional academy module) : `/superadmin/suivi`, `/admin/suivi`, `/teacher/suivi`

**Steps.**

1. In the student's record, open Reports.
2. Choose the type, then "Generate the report".
3. Review, "Validate", then "Publish".
4. "Create a new version" to correct a published report.

**Expected result.** Report downloadable as PDF.

**Common errors.**

- *The family cannot see the report* : Check that it is published and family access is open.

**Permissions.** Super administrator, administrator, teacher.

<a id="banque-questions"></a>
### How do I create questions in the bank?

**What it is for.** Build questions reusable from one test to the next.

**Who can use it.** Super administrator, Administrator, Teacher

**Prerequisites.**

- "Online exams" module enabled.

**Where to find it.** Menu « Exams and assessments » (optional academy module) : `/superadmin/evaluations/banque`, `/admin/evaluations/banque`, `/teacher/evaluations/banque`

**Steps.**

1. In "Exams and assessments", open "Question bank".
2. "New question": type, statement, answers (tick the correct one(s)), points.
3. Save. "Import a CSV" and "Export" handle several questions.

**Important fields.**

- Subject, type and difficulty are used by filters.

**Expected result.** Confirmation shown: "Question saved in the bank."

**Common errors.**

- *A change does not appear in a published test* : Expected: a published test keeps its version of the question.

**Permissions.** Super administrator, administrator, teacher (their subjects).

<a id="epreuves"></a>
### How do I create, publish and mark an online test?

**What it is for.** Run an online quiz or exam, from draft to grade transfer.

**Who can use it.** Super administrator, Administrator, Teacher

**Prerequisites.**

- Questions in the bank; the subject assigned to the teacher in the class.

**Where to find it.** Menu « Exams and assessments » (optional academy module) : `/superadmin/evaluations`, `/admin/evaluations`, `/teacher/evaluations`

**Steps.**

1. "New test": title, type, subject, class, opening, closing, duration, attempts, maximum mark, pass threshold.
2. Add questions from the bank, order them, check the "Test preview".
3. "Publish the test": it can no longer be edited.
4. After the attempts, mark open questions and validate the papers.
5. "Close the test", "Publish results", then "Transfer to grades" if it must count.

**Important fields.**

- Quiz: practice. Official exam: can produce a grade, after validation.

**Expected result.** The "Next step" shown at the top of the test tells what to do.

**Common errors.**

- *Creation refused* : The subject must be assigned to you in the chosen class.
- *The answer key is not visible* : It only appears after the test is closed.

**Effects on other modules.** The transfer creates the official grade once per student.

**Permissions.** Super administrator, administrator, teacher.

<a id="passer-epreuve"></a>
### How do I take an online test?

**What it is for.** Answer a quiz or exam published by your teacher.

**Who can use it.** Student

**Prerequisites.**

- The test is open (opening date passed).

**Where to find it.** Menu « My tests » (optional academy module) : `/student/evaluations`

**Steps.**

1. Open "My tests" and read the instructions.
2. Click "Start": the timer starts.
3. Answer; your answers are saved automatically.
4. If disconnected, come back and click "Resume".
5. Click "Submit my paper" and keep the receipt.

**Expected result.** The result is visible when the teacher publishes it ("View result").

**Common errors.**

- *"Your tests could not be loaded."* : Check your connection and reload the page.

**Effects on other modules.** Each attempt is kept.

**Permissions.** Student.

<a id="rapports-mensuels"></a>
### How do I produce and send monthly reports?

**What it is for.** Produce each online-academy student's monthly report and send it to the guardians.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- "Monthly reports" module enabled.

**Where to find it.** Menu « Monthly reports » (optional academy module) : `/superadmin/monthly-reports`, `/admin/monthly-reports`

**Steps.**

1. Open "Monthly reports", choose the year and month.
2. "Produce the month's batch".
3. Open a report, add the appreciation, download the PDF.
4. "Send to guardians".

**Expected result.** The batch shows reports created, already present and failed; each send has its status.

**Common errors.**

- *Status "Not confirmed"* : No email provider accepted the message: see the Outbox.

**Effects on other modules.** Producing again does not create duplicates.

**Permissions.** Super administrator, administrator.

## School life

<a id="absences"></a>
### How do I record an absence or late arrival?

**What it is for.** Keep the attendance register with supporting documents.

**Who can use it.** Super administrator, Administrator, Teacher

**Where to find it.** Menu « Attendance » : `/superadmin/attendance`, `/admin/attendance`, `/teacher/attendance`

**Steps.**

1. Open "Attendance", then "New attendance".
2. Choose the student, date and status: Present, Absent, Late, Excused.
3. Add the reason and attach a supporting document if needed, then save.

**Important fields.**

- Supporting document: image, PDF or document.

**Expected result.** Confirmation shown: "Attendance recorded!"

**Common errors.**

- *The student does not appear (teacher)* : Only students of your classes are offered.

**Effects on other modules.** The student and parents see the absence in "Attendance".

**Permissions.** Super administrator, administrator, teacher; viewing: parent, student.

<a id="devoirs"></a>
### How do I give homework to a class?

**What it is for.** Publish an assignment with instructions, due date and attachments.

**Who can use it.** Super administrator, Administrator, Teacher

**Where to find it.** Menu « Homework » : `/superadmin/homework`, `/admin/homework`, `/teacher/homework`

**Steps.**

1. Open "Homework", then "New homework".
2. Enter title, description, class, subject and due date.
3. Add files if needed, then save.

**Expected result.** Confirmation shown: "Homework created!"; the class's students and their parents see it.

**Common errors.**

- *Class missing from the list (teacher)* : It must be assigned to you.

**Permissions.** Super administrator, administrator, teacher; viewing: parent, student.

<a id="emploi-du-temps"></a>
### How do I build the timetable?

**What it is for.** Schedule in-person classes and, for an online academy, live sessions.

**Who can use it.** Super administrator, Administrator, Teacher, Parent, Student

**Prerequisites.**

- The data shown belongs to the academy chosen in the selector at the top of the page.
- Classes, subjects, teachers and rooms created.

**Where to find it.** Menu « Timetable » : `/superadmin/schedule`, `/admin/schedule`, `/teacher/schedule`, `/parent/schedule`, `/student/schedule`

**Steps.**

1. Open "Timetable".
2. In-person classes: "New slot": class, subject, teacher, year, day, times, room.
3. Online sessions: "New session": group, subject, day and time in UTC, teacher, virtual room.
4. Switch between "Grid" and "List".
5. Teachers, students and parents view their timetable in "Timetable", without being able to change it.

**Important fields.**

- Online sessions: time is entered in UTC and also shown in local time.

**Expected result.** Confirmation shown: "Slot created!" or "Session scheduled."; teachers, students and parents see their timetable.

**Common errors.**

- *"Online sessions do not exist for this academy."* : Only online academies have live sessions.

**Permissions.** Super administrator, administrator; viewing: teacher, parent, student.

<a id="annonces"></a>
### How do I publish an announcement?

**What it is for.** Inform the academy's users (meeting, closure, event).

**Who can use it.** Super administrator, Administrator, Teacher, Parent, Student

**Where to find it.** Menu « Announcements » : `/superadmin/announcements`, `/admin/announcements`, `/teacher/announcements`, `/parent/announcements`, `/student/announcements`

**Steps.**

1. Open "Announcements", then "New announcement".
2. Enter title, content, recipients and optional attachment.
3. Tick "Publish now" or keep a draft, then "Publish".
4. Other profiles read published announcements in "Announcements".

**Expected result.** Confirmation shown: "Announcement published!"; it appears in the recipients' "Announcements".

**Effects on other modules.** A draft is not visible to anyone else.

**Permissions.** Super administrator, administrator; reading: everyone.

<a id="messagerie"></a>
### How do I send a message?

**What it is for.** Exchange with authorised people at the school.

**Who can use it.** Super administrator, Administrator, Teacher, Parent, Student

**Where to find it.** Menu « Messages » : `/superadmin/messages`, `/admin/messages`, `/teacher/messages`, `/parent/messages`, `/student/messages`

**Steps.**

1. Open "Messages", then "New message".
2. Choose the recipient, enter the subject and message, attach a file if needed.
3. "Send". To reply, open the conversation and write in "Write a reply...".

**Expected result.** Confirmation shown: "Message sent!"; the recipient is notified.

**Common errors.**

- *Recipient not found* : A teacher writes to administrators and to their students' parents; a parent or student, to their academy's staff.

**Permissions.** Everyone, according to authorised recipients.

<a id="salles-virtuelles"></a>
### How do I hold or join an online class?

**What it is for.** Create a video conferencing room and let participants in.

**Who can use it.** Super administrator, Administrator, Teacher, Parent, Student

**Prerequisites.**

- "Virtual rooms" module enabled; recent browser with camera and microphone allowed.

**Where to find it.** Menu « Virtual rooms » (optional academy module) : `/superadmin/virtual`, `/admin/virtual`, `/teacher/virtual`, `/parent/virtual`, `/student/virtual`

**Steps.**

1. Staff: "New room": name, description, class, subject, allowed profiles, schedule.
2. At the scheduled time, click "Join".
3. Allow camera and microphone in the browser.
4. The organiser ends with "Close the meeting"; "Reopen" restarts it.

**Important fields.**

- "Reserved for": no box ticked = open to all allowed profiles.

**Expected result.** The video room opens in the tab.

**Common errors.**

- *No sound or picture* : Allow camera and microphone in the browser, then join again.
- *"Join" missing* : The room is not open yet or does not concern your profile.

**Effects on other modules.** Recordings, if any, appear in "Recordings".

**Permissions.** Creation: super administrator, administrator, teacher. Participation: the room's allowed profiles.

## Payments

<a id="paiements"></a>
### How do I record a payment and produce a receipt?

**What it is for.** Record collected school fees and issue a receipt.

**Who can use it.** Super administrator, Administrator

**Where to find it.** Menu « Payments » : `/superadmin/payments`, `/admin/payments`

**Steps.**

1. Open "Payments", then "New payment".
2. Student, type (registration, monthly fee, canteen, transport, childcare, other), method (cash, transfer, cheque), amount, date, time, month concerned.
3. Save, then "Generate receipt" on the row; "View receipt" opens it.
4. To cancel: cancel action, mandatory reason. "Show deleted" and "Restore" bring it back.

**Important fields.**

- Time: the academy's local time; leave blank if unknown.

**Expected result.** Confirmation shown: "Payment recorded!"; the total collected updates.

**Common errors.**

- *Amounts excluded from the total* : An exchange rate is missing: the amounts concerned are listed.

**Effects on other modules.** The parent sees the payment and its receipt; reminders take the balance into account.

**Permissions.** Super administrator, administrator; viewing: parent.

<a id="transactions-carte"></a>
### How do I refund a card payment?

**What it is for.** View card payments and refund all or part.

**Who can use it.** Super administrator, Administrator

**Where to find it.** Menu « Card transactions » : `/superadmin/card-transactions`, `/admin/card-transactions`

**Steps.**

1. Open "Card transactions".
2. On the row, click "Refund".
3. Enter the amount (empty = remaining balance), then "Confirm refund".

**Important fields.**

- Collected and already refunded amounts are shown before confirming.

**Expected result.** The status and refunded amount update.

**Common errors.**

- *Amount refused* : It exceeds the refundable balance.

**Permissions.** Super administrator, administrator.

<a id="relances"></a>
### How do I configure payment reminders?

**What it is for.** Define payment schedules and automatically remind late payers by email and notification.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- The data shown belongs to the academy chosen in the selector at the top of the page.

**Where to find it.** Menu « Payment reminders » : `/superadmin/payment-reminders`, `/admin/payment-reminders`

**Steps.**

1. Open "Payment reminders" and check the "Service status".
2. Reminder rules: grace period, interval, maximum count, minimum balance, channels, instructions and contact. Save.
3. "New schedule" for due dates.
4. Check the situation, then "Confirm sending reminders" if needed.

**Important fields.**

- "Suspend automatic sending" stops reminders without losing the rules.

**Expected result.** Confirmation shown: "Reminders started: the result will appear in the history."

**Common errors.**

- *"Real sending disabled on this server"* : The screen runs as a simulation: nothing is sent. The server setting belongs to the technical administrator.

**Permissions.** Super administrator, administrator.

## Documents and files

<a id="documents-officiels"></a>
### How do I produce a certificate or diploma?

**What it is for.** Produce, issue or revoke a numbered official document.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- An active template for this document type (Document templates).

**Where to find it.** Menu « Official documents » : `/superadmin/official-documents`, `/admin/official-documents`

**Steps.**

1. Open "Official documents", then "Produce a document".
2. Type, student, date obtained and certificate purpose (optional).
3. "Preview", then "Produce": a draft is created.
4. "Issue" assigns the number; "Revoke" cancels an issued document.
5. "Production by class" produces for a whole class.

**Important fields.**

- The student determines the issuing academy.

**Expected result.** Confirmation shown: "Draft produced. It is not issued yet."

**Common errors.**

- *"No active template"* : Upload, verify and activate the template.

**Effects on other modules.** An issued document keeps its fingerprint and stays viewable even when revoked.

**Permissions.** Super administrator, administrator.

<a id="gabarits"></a>
### How do I prepare a diploma or certificate template?

**What it is for.** Upload the official background and place the printed fields.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- The data shown belongs to the academy chosen in the selector at the top of the page.

**Where to find it.** Menu « Document templates » : `/superadmin/document-templates`, `/admin/document-templates`

**Steps.**

1. Open "Document templates"; "Upload" on the diploma or certificate.
2. "Place the fields" and choose the page format.
3. "PDF preview", then "Verify" (test render) and "Activate".

**Expected result.** Confirmation shown: "Version activated: it is now used to produce documents."

**Common errors.**

- *"Verification failed."* : Fix the field placement and verify again.

**Effects on other modules.** The active version stays in use until the new one is verified then activated.

**Permissions.** Super administrator, administrator.

<a id="fichiers"></a>
### How do I upload a file for a user?

**What it is for.** Keep documents (birth certificate, medical certificate...) attached to an account.

**Who can use it.** Super administrator, Administrator

**Where to find it.** Menu « Files » : `/superadmin/user-files`, `/admin/user-files`

**Steps.**

1. Open "Files", then "Add a file".
2. Name, description, target user, file.
3. Save. "Preview", "Download", "Replace" and "Delete" are on each file.

**Important fields.**

- Images, PDF, Word, Excel, CSV, ZIP, 5 MB maximum.

**Expected result.** Confirmation shown: "File uploaded!"

**Common errors.**

- *File refused* : Check the format and size.

**Permissions.** Super administrator, administrator.

## Public website and admissions

<a id="site-vitrine"></a>
### How do I handle website messages and pre-registrations?

**What it is for.** Read contact form messages and pre-registration requests from the public website.

**Who can use it.** Super administrator, Administrator

**Where to find it.** Menu « Public website » : `/superadmin/website`, `/admin/website`

**Steps.**

1. Open "Public website".
2. Open a message: "Reply by email" or "Reply on WhatsApp", "Mark read".
3. Pre-registrations: "View file", "Export CSV".

**Important fields.**

- The visitor's consent is shown for each request.

**Expected result.** Handled requests change status.

**Effects on other modules.** The CSV export neutralises formulas for safe use in a spreadsheet.

**Permissions.** Super administrator, administrator.

<a id="admissions-en-ligne"></a>
### How do I process an online application?

**What it is for.** Follow the online academy's application forms and placement test requests.

**Who can use it.** Super administrator, Administrator

**Prerequisites.**

- "Online admissions" module enabled.

**Where to find it.** Menu « Online admissions » (optional academy module) : `/superadmin/fha-admissions`, `/admin/fha-admissions`

**Steps.**

1. Open "Online admissions": "Application forms" and "Placement tests" tabs.
2. Filter by status, open the PDF form, change the status.
3. Tick rows for a group confirmation send; export if needed.

**Important fields.**

- "Do not resend to files already confirmed" avoids duplicates.

**Expected result.** Confirmation shown: "Status updated."; the email to the parent has its own status.

**Common errors.**

- *"Saved, but no real provider is configured."* : The message is archived but was not sent: see the Outbox.

**Permissions.** Super administrator, administrator.

## Family area

<a id="famille-notes"></a>
### How do I view grades and download a report card?

**What it is for.** See results by subject and period, and get PDF report cards.

**Who can use it.** Parent, Student

**Prerequisites.**

- Parent: your children must be linked to your account.

**Where to find it.** Menu « Grades and report cards » : `/parent/grades`, `/student/grades`

**Steps.**

1. Open "Grades" ("My grades" for a student); filter by period.
2. Open "Report cards", choose the year, then "Download".

**Expected result.** The report card PDF opens or downloads.

**Common errors.**

- *"No report card available for this period"* : The school has not generated it yet.

**Permissions.** Parent (their children), student (themselves).

<a id="famille-suivi"></a>
### How do I follow competencies and test results?

**What it is for.** See what the teacher validated: competencies, goals, reports and published results.

**Who can use it.** Parent, Student

**Prerequisites.**

- The academy has opened follow-up to families.

**Where to find it.** Menu « Follow-up and results » : `/parent/suivi`, `/student/suivi`

**Steps.**

1. Open "Teaching follow-up" ("My follow-up" for a student).
2. Browse the tabs; download published reports.
3. Parent: "Test results" for published test marks.

**Expected result.** Only what has been validated and published appears.

**Common errors.**

- *"Your academy has not opened these results to families yet."* : Nothing to do on your side.

**Permissions.** Parent, student.

<a id="famille-paiements"></a>
### How do I view my payments and receipts?

**What it is for.** See the payments recorded for your children and download receipts.

**Who can use it.** Parent

**Where to find it.** Menu « Payments » : `/parent/payments`

**Steps.**

1. Open "Payments".
2. Check the confirmed total and the list; "PDF" downloads the receipt.

**Expected result.** Each payment shows its status: Confirmed or Cancelled.

**Common errors.**

- *"Payment being verified"* : The online payment is awaiting the provider's confirmation.
- *"Payment abandoned"* : Nothing was charged; you can try again.

**Permissions.** Parent.

<a id="famille-vie"></a>
### Where do I see homework, attendance, timetable and announcements?

**What it is for.** Find the student's school life information.

**Who can use it.** Parent, Student

**Where to find it.** Menu « School life » : `/parent/homework`, `/student/homework`

**Steps.**

1. "Home" summarises the situation; "My children" (parent) shows each child's record.
2. "Homework": tasks and attachments.
3. "Attendance": presence, late arrivals and supporting documents.
4. "Timetable": the week's classes.
5. "Announcements": school information.

**Expected result.** Information only concerns the student or your children.

**Common errors.**

- *A parent sees no child* : Ask the administration to link your children to your account.

**Permissions.** Parent, student.

## Frequently asked questions

**I forgot my password: what should I do?**

Contact your school's administration: they will give you a temporary password to replace at sign-in. FEBA does not send reset links by email.

**Why does a menu not appear for me?**

Some modules (teaching follow-up, online exams, monthly reports, online admissions, virtual rooms) are enabled academy by academy. Menus also depend on your profile.

**Does a follow-up assessment count in the report card?**

No. Only grades from the Grades module, including those transferred from a validated test, count in averages and report cards.

**Can I permanently delete a grade or payment?**

No: they are marked deleted or cancelled with a reason, kept in history and restorable.

**When is the report card available?**

As soon as the school has generated it for the period; it then appears in "Report cards".

## Troubleshooting

**The page says "cannot reach the server".**

Check your network, then reload. If the problem persists for everyone, tell the administration: the incident is recorded automatically.

**I was signed out.**

The session expires after inactivity or if your password was reset. Sign in again.

**A PDF does not open.**

Allow downloads and pop-ups for FEBA in the browser, then try again.

**The virtual room stays black or silent.**

Allow camera and microphone (icon left of the address bar), close other apps using them, then join again.

**A creation is refused without a clear message.**

Check that a specific academy is selected and that fields marked * are filled in.

## Glossary

- **Academy** : School managed in FEBA, isolated from the others.
- **Active school year** : Year used by default in lists and the dashboard.
- **Coefficient** : Weight of a subject in the average.
- **Competency** : What a student can do, for example "understand a short text".
- **Framework** : A list of competencies, by subject or programme.
- **Mastery level** : To work on, To strengthen, In progress or Acquired.
- **Follow-up assessment** : Result useful for support. It does not count in the report card.
- **Official grade** : Grade from the Grades module, which counts in averages and report cards.
- **Quiz** : Practice test. It does not have to produce a grade.
- **Official exam** : Test that can produce an official grade, after validation.
- **Attempt** : A complete run of a test. Each attempt is kept.
- **Transfer** : Creation of the official grade from a validated test, once per student.
- **Publication** : Making a result or report visible. Nothing is visible before.
- **Template** : Official background of a diploma or certificate, with field positions.
- **Temporary password** : Password given by the administration, to replace at sign-in.
