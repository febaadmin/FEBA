"""
apps/payments/reminders.py — Moteur des relances de paiement en retard.

CE QUE LE MOTEUR CALCULE, POUR CHAQUE ÉCHÉANCE D'UN ÉLÈVE
----------------------------------------------------------
1. Le tarif applicable : celui de son académie, de son année et de son
   niveau, le plus spécifique l'emportant (même règle que FeeSchedule.resolve).
   Un tarif NON obligatoire (cantine, transport, garderie) ne s'applique
   qu'aux élèves abonnés.
2. Le montant prévu : les échéances (`FeeInstallment`), diminuées d'une
   éventuelle réduction (imputée sur les DERNIÈRES échéances : la réduction
   allège le solde, elle ne retarde pas la première tranche). Une
   exonération annule tout.
3. Les paiements imputés : paiements CONFIRMÉS et non supprimés, du même
   type et de la même année scolaire, nets des remboursements carte.
   - un paiement qui précise son « mois concerné » est d'abord imputé à
     l'échéance de ce mois (imputation réelle) ;
   - le reste est imputé à l'échéance la plus ancienne non soldée. C'est la
     règle des modalités par tranche : en novembre, ce qui est exigible est
     le CUMUL de septembre et novembre. Elle ne présente jamais un montant
     comme dû deux fois.
   Les paiements annulés, supprimés ou « en attente » (transaction carte
   ouverte) ne comptent pas comme payés ; une transaction carte ouverte
   suspend la relance (le parent est peut-être en train de payer).
4. Le solde et le statut : à venir, réglée, échue, partiellement payée,
   exonérée.

QUAND LE MOTEUR S'ABSTIENT (ANOMALIES)
--------------------------------------
Plutôt que d'écrire à une famille un montant faux, il signale et ne relance
pas : échéancier « par tranches » dont la somme ≠ montant total, paiement
sans année scolaire, devise incohérente, responsable d'une autre académie.

IDEMPOTENCE
-----------
Chaque relance porte une clé unique (échéance × élève × destinataire ×
niveau de rappel). Rejouer le moteur le même jour, ou l'exécuter deux fois
en parallèle, ne produit aucune relance en double : la base refuse la
seconde insertion.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.age import academy_today
from apps.core.currency import Money

logger = logging.getLogger("apps")

PURPOSE_REMINDER = "payment_reminder"

STATUS_UPCOMING = "upcoming"
STATUS_PAID = "paid"
STATUS_OVERDUE = "overdue"
STATUS_PARTIAL = "partial"
STATUS_EXEMPTED = "exempted"
STATUS_LABELS = {
    STATUS_UPCOMING: "À venir",
    STATUS_PAID: "Réglée",
    STATUS_OVERDUE: "Échue — impayée",
    STATUS_PARTIAL: "Échue — partiellement payée",
    STATUS_EXEMPTED: "Exonérée",
}


def reminders_globally_enabled():
    return bool(getattr(settings, "PAYMENT_REMINDERS_ENABLED", False))


def type_label(payment_type):
    from apps.payments.models import Payment
    return dict(Payment.PAYMENT_TYPES).get(payment_type, payment_type)


@dataclass
class DueItem:
    student: object
    fee: object
    installment: object
    school_year_id: int
    expected: int
    discount: int = 0
    paid: int = 0
    outstanding: int = 0
    status: str = STATUS_UPCOMING
    days_overdue: int = 0
    blockers: list = field(default_factory=list)

    @property
    def currency(self):
        return self.fee.currency

    def money(self, minor):
        return Money(minor, self.currency).formatted()

    def as_dict(self):
        fee = self.fee
        return {
            "student_id": self.student.pk,
            "student_name": self.student.get_full_name(),
            "fee_id": fee.pk,
            "fee_label": fee.label or type_label(fee.payment_type),
            "payment_type": fee.payment_type,
            "installment_id": self.installment.pk,
            "installment_label": self.installment.label,
            "due_date": self.installment.due_date,
            "currency": self.currency,
            "expected_minor": self.expected,
            "discount_minor": self.discount,
            "paid_minor": self.paid,
            "outstanding_minor": self.outstanding,
            "expected_display": self.money(self.expected),
            "paid_display": self.money(self.paid),
            "outstanding_display": self.money(max(self.outstanding, 0)),
            "status": self.status,
            "status_label": STATUS_LABELS[self.status],
            "days_overdue": self.days_overdue,
            "blockers": list(self.blockers),
        }


@dataclass
class Computation:
    items: list
    anomalies: list


def _anomaly(kind, message, **context):
    return {"kind": kind, "message": message, **context}


def _pick_fee(candidates):
    """Le plus spécifique gagne : niveau ET année, puis année, puis niveau."""
    def specificity(fee):
        return (fee.school_year_id is not None) * 2 + (fee.level_id is not None)
    return sorted(candidates, key=specificity, reverse=True)[0] if candidates else None


def compute_dues(academy, on_date=None):
    """
    Échéances de tous les élèves actifs de l'académie à la date `on_date`
    (date LOCALE de l'académie par défaut). Aucune écriture.
    """
    from apps.payments.models import FeeSchedule, Payment, StudentFeeArrangement
    from apps.payments.transaction_models import PaymentTransaction
    from apps.students.models import Student

    on_date = on_date or academy_today(academy)
    anomalies = []

    fees = list(
        FeeSchedule.objects.filter(academy=academy, is_active=True)
        .prefetch_related("installments")
    )
    fees = [f for f in fees if f.installments.all()]
    blocked_fees = set()
    for fee in fees:
        total = sum(i.amount_minor for i in fee.installments.all())
        if fee.installment_mode == FeeSchedule.INSTALLMENTS_SPLIT and total != fee.amount_minor:
            blocked_fees.add(fee.pk)
            anomalies.append(_anomaly(
                "fee_sum_mismatch",
                f"« {fee.label or type_label(fee.payment_type)} » : la somme des échéances "
                f"({Money(total, fee.currency).formatted()}) diffère du montant total "
                f"({fee.money.formatted()}). Aucune relance pour ce tarif tant que ce n'est pas corrigé.",
                fee_id=fee.pk,
            ))
    if not fees:
        return Computation(items=[], anomalies=anomalies)

    fees_by_type = defaultdict(list)
    for fee in fees:
        fees_by_type[fee.payment_type].append(fee)

    students = list(
        Student.objects.filter(school=academy, is_active=True)
        .select_related("current_class__level", "school")
        .prefetch_related("enrollments__class_obj__level")
    )
    student_ids = [s.pk for s in students]

    arrangements = defaultdict(dict)
    for arr in StudentFeeArrangement.objects.filter(student_id__in=student_ids):
        arrangements[(arr.student_id, arr.fee_schedule_id)][arr.kind] = arr

    payments = defaultdict(list)
    payments_without_year = set()
    payment_currency_issue = set()
    refunds = {
        tx.payment_id: tx.amount_refunded_minor
        for tx in PaymentTransaction.objects.filter(
            payment__student_id__in=student_ids, amount_refunded_minor__gt=0,
        ).only("payment_id", "amount_refunded_minor")
    }
    for p in Payment.objects.filter(
        student_id__in=student_ids, is_confirmed=True, is_deleted=False,
    ).only("id", "student_id", "payment_type", "school_year_id", "amount_minor",
           "currency", "period_month", "payment_date"):
        if p.school_year_id is None:
            payments_without_year.add((p.student_id, p.payment_type))
            continue
        if p.currency and p.currency != academy.currency_code:
            payment_currency_issue.add((p.student_id, p.payment_type))
        net = max(p.amount_minor - refunds.get(p.pk, 0), 0)
        payments[(p.student_id, p.payment_type, p.school_year_id)].append((net, p.period_month, p.payment_date))

    open_card = set(
        PaymentTransaction.objects.filter(
            academy=academy, status__in=PaymentTransaction.OPEN_STATUSES,
        ).values_list("student_id", "payment_type", "school_year_id")
    )

    items = []
    for student in students:
        enrollments = {e.school_year_id: e for e in student.enrollments.all()}

        def level_for(year_id):
            enrollment = enrollments.get(year_id)
            if enrollment is not None and enrollment.class_obj is not None:
                return enrollment.class_obj.level_id
            if year_id == student.school_year_id and student.current_class:
                return student.current_class.level_id
            return None

        def enrolled_in(year_id):
            return year_id == student.school_year_id or year_id in enrollments

        for payment_type, candidates in fees_by_type.items():
            # Un tarif par année : regrouper par année cible.
            by_year = defaultdict(list)
            for fee in candidates:
                year_id = fee.school_year_id or student.school_year_id
                if year_id is None or not enrolled_in(year_id):
                    continue
                level_id = level_for(year_id)
                if fee.level_id is not None and fee.level_id != level_id:
                    continue
                by_year[year_id].append(fee)
            for year_id, year_fees in by_year.items():
                fee = _pick_fee(year_fees)
                items.extend(_items_for(
                    student, fee, year_id, on_date,
                    arrangements.get((student.pk, fee.pk), {}),
                    payments.get((student.pk, payment_type, year_id), []),
                    blocked=fee.pk in blocked_fees,
                    no_year=(student.pk, payment_type) in payments_without_year,
                    currency_issue=(student.pk, payment_type) in payment_currency_issue,
                    card_open=(student.pk, payment_type, year_id) in open_card,
                    anomalies=anomalies,
                ))
    return Computation(items=items, anomalies=anomalies)


def _items_for(student, fee, year_id, on_date, arrangement, payments, *, blocked,
               no_year, currency_issue, card_open, anomalies):
    from apps.payments.models import StudentFeeArrangement

    installments = sorted(fee.installments.all(), key=lambda i: (i.due_date, i.order, i.pk))
    if not fee.is_mandatory:
        subscription = arrangement.get(StudentFeeArrangement.SUBSCRIPTION)
        if subscription is None:
            return []
        installments = [
            i for i in installments
            if (subscription.start_date is None or i.due_date >= subscription.start_date)
            and (subscription.end_date is None or i.due_date <= subscription.end_date)
        ]
    if not installments:
        return []

    exempted = StudentFeeArrangement.EXEMPTION in arrangement
    discount_left = getattr(arrangement.get(StudentFeeArrangement.DISCOUNT), "discount_minor", 0)

    rows = [DueItem(student=student, fee=fee, installment=i, school_year_id=year_id,
                    expected=i.amount_minor) for i in installments]
    # Réduction imputée sur les dernières échéances.
    for row in reversed(rows):
        take = min(discount_left, row.expected)
        row.discount = take
        discount_left -= take

    # 1) imputation réelle : paiements précisant leur mois.
    pool = 0
    for amount, period_month, _date in payments:
        target = None
        if period_month is not None:
            target = next(
                (r for r in rows if (r.installment.due_date.year, r.installment.due_date.month)
                 == (period_month.year, period_month.month)), None,
            )
        if target is None:
            pool += amount
            continue
        need = max(target.expected - target.discount - target.paid, 0)
        take = min(amount, need)
        target.paid += take
        pool += amount - take
    # 2) le reste à l'échéance la plus ancienne non soldée.
    for row in rows:
        need = max(row.expected - row.discount - row.paid, 0)
        take = min(pool, need)
        row.paid += take
        pool -= take

    blockers = []
    if blocked:
        blockers.append("Échéancier incohérent (somme ≠ total)")
    if no_year:
        blockers.append("Paiement sans année scolaire pour ce type de frais")
        anomalies.append(_anomaly(
            "payment_without_year",
            f"{student.get_full_name()} : un paiement « {type_label(fee.payment_type)} » n'a pas "
            "d'année scolaire. Le solde ne peut pas être établi avec certitude.",
            student_id=student.pk,
        ))
    if currency_issue:
        blockers.append("Paiement dans une autre devise")
        anomalies.append(_anomaly(
            "currency_mismatch",
            f"{student.get_full_name()} : paiement « {type_label(fee.payment_type)} » dans une devise "
            "différente de celle de l'académie.", student_id=student.pk,
        ))
    if card_open:
        blockers.append("Paiement par carte en cours")

    for row in rows:
        row.outstanding = row.expected - row.discount - row.paid
        row.days_overdue = max((on_date - row.installment.due_date).days, 0)
        row.blockers = list(blockers)
        if exempted:
            row.status, row.outstanding = STATUS_EXEMPTED, 0
        elif row.outstanding <= 0:
            row.status = STATUS_PAID
        elif row.installment.due_date >= on_date:
            row.status = STATUS_UPCOMING
        elif row.paid > 0:
            row.status = STATUS_PARTIAL
        else:
            row.status = STATUS_OVERDUE
    return rows


# ── Destinataires ─────────────────────────────────────────────────────

def responsible_parents(student, anomalies=None):
    """
    Responsables à relancer : ceux marqués « responsable financier » ; à
    défaut, les tuteurs légaux. Comptes actifs, de la MÊME académie.
    """
    links = list(student.parents.select_related("parent__user").all())
    chosen = [l for l in links if l.is_financial_responsible] or [l for l in links if l.is_legal_guardian]
    users, seen = [], set()
    for link in chosen:
        user = link.parent.user
        if user.pk in seen or not user.is_active:
            continue
        if user.school_id != student.school_id:
            if anomalies is not None:
                anomalies.append(_anomaly(
                    "parent_other_academy",
                    f"{student.get_full_name()} : un responsable appartient à une autre académie ; il "
                    "n'est pas relancé.", student_id=student.pk,
                ))
            continue
        seen.add(user.pk)
        users.append(user)
    return users


def _email_ok(email):
    try:
        validate_email(email or "")
        return True
    except DjangoValidationError:
        return False


# ── Plan de relance ───────────────────────────────────────────────────

def get_policy(academy, create=False):
    from apps.payments.models import PaymentReminderPolicy

    if create:
        return PaymentReminderPolicy.objects.get_or_create(academy=academy)[0]
    return (PaymentReminderPolicy.objects.filter(academy=academy).first()
            or PaymentReminderPolicy(academy=academy))


def plan_reminders(academy, on_date=None, computation=None, policy=None, now=None):
    """
    Relances qui DOIVENT partir aujourd'hui, sans rien écrire.

    Renvoie (plan, computation) où `plan` est une liste de dicts
    {item, recipient, level}.
    """
    from apps.payments.models import PaymentReminder

    on_date = on_date or academy_today(academy)
    now = now or timezone.now()
    policy = policy or get_policy(academy)
    computation = computation or compute_dues(academy, on_date)

    eligible = [
        i for i in computation.items
        if i.status in (STATUS_OVERDUE, STATUS_PARTIAL) and not i.blockers
        and i.outstanding >= max(policy.min_amount_minor, 1)
        and i.days_overdue >= policy.grace_days
    ]
    if not eligible:
        return [], computation

    history = defaultdict(list)
    for r in PaymentReminder.objects.filter(
        installment_id__in={i.installment.pk for i in eligible},
        student_id__in={i.student.pk for i in eligible},
    ).only("installment_id", "student_id", "recipient_id", "level", "created_at"):
        history[(r.installment_id, r.student_id, r.recipient_id)].append(r)

    plan = []
    parents_cache = {}
    for item in eligible:
        student = item.student
        if student.pk not in parents_cache:
            parents_cache[student.pk] = responsible_parents(student, computation.anomalies)
        recipients = parents_cache[student.pk]
        if not recipients:
            item.blockers.append("Aucun responsable joignable")
            continue
        for user in recipients:
            past = history[(item.installment.pk, student.pk, user.pk)]
            level = len(past) + 1
            if level > policy.max_reminders:
                continue
            threshold = policy.grace_days + (level - 1) * policy.interval_days
            if item.days_overdue < threshold:
                continue
            if past and now - max(r.created_at for r in past) < timedelta(days=policy.interval_days):
                continue
            plan.append({"item": item, "recipient": user, "level": level})
    return plan, computation


# ── Messages ──────────────────────────────────────────────────────────

def _lines(rows, lang):
    out = []
    for r in rows:
        due = r.due_date.strftime("%d/%m/%Y" if lang != "en" else "%m/%d/%Y")
        money = lambda m: Money(m, r.currency).formatted()  # noqa: E731
        if lang == "en":
            out.append(
                f"- {r.student.get_full_name()} — {r.fee_label} — {r.installment_label} "
                f"(due {due}): expected {money(r.amount_expected_minor)}, "
                f"paid {money(r.amount_paid_minor)}, balance due {money(r.amount_due_minor)}."
            )
        else:
            out.append(
                f"- {r.student.get_full_name()} — {r.fee_label} — {r.installment_label} "
                f"(échéance du {due}) : montant prévu {money(r.amount_expected_minor)}, "
                f"déjà réglé {money(r.amount_paid_minor)}, reste à payer {money(r.amount_due_minor)}."
            )
    return "\n".join(out)


def build_message(academy, policy, recipient, rows):
    """Objet, texte, HTML et texte de notification d'une relance groupée."""
    import html

    lang = "en" if (getattr(recipient, "preferred_language", "") or academy.default_language or "fr").startswith("en") else "fr"
    name = recipient.get_full_name() or recipient.email
    lines = _lines(rows, lang)
    contact = policy.contact_text or "\n".join(filter(None, [academy.phone, academy.email]))
    if lang == "en":
        subject = f"{academy.name} — payment reminder"
        text = (
            f"Dear {name},\n\nAccording to our records, the following amounts are past due:\n\n"
            f"{lines}\n\nIf you have already paid, please disregard this message or send us your "
            "receipt so we can update your account."
        )
        if policy.payment_instructions:
            text += f"\n\nPayment options:\n{policy.payment_instructions}"
        if contact:
            text += f"\n\nContact:\n{contact}"
        text += f"\n\nKind regards,\n{academy.name}"
        notif_title = "Payment reminder"
    else:
        subject = f"{academy.name} — rappel de paiement"
        text = (
            f"Madame, Monsieur {name},\n\nSauf erreur de notre part, les montants suivants restent "
            f"dus après leur date limite :\n\n{lines}\n\nSi vous avez déjà effectué ce règlement, "
            "merci de ne pas tenir compte de ce message ou de nous transmettre votre reçu afin que "
            "nous mettions votre dossier à jour."
        )
        if policy.payment_instructions:
            text += f"\n\nModalités de paiement :\n{policy.payment_instructions}"
        if contact:
            text += f"\n\nContact :\n{contact}"
        text += f"\n\nVeuillez agréer nos salutations distinguées.\n{academy.name}"
        notif_title = "Rappel de paiement"
    html_body = (
        "<div style=\"font-family:Arial,sans-serif;font-size:14px;line-height:1.5\">"
        + html.escape(text).replace("\n", "<br>") + "</div>"
    )
    notif_message = lines[:1900]
    return subject, text, html_body, notif_title, notif_message


# ── Exécution ─────────────────────────────────────────────────────────

def run_reminders(academy, *, trigger, user=None, on_date=None, dry_run=False, now=None):
    """
    Calcule et (sauf simulation) envoie les relances dues pour l'académie.

    Renvoie le ReminderRun (enregistré, y compris pour une simulation : la
    trace de qui a simulé quoi fait partie de l'audit).
    """
    from apps.payments.models import PaymentReminder, ReminderRun

    on_date = on_date or academy_today(academy, now)
    run = ReminderRun.objects.create(
        academy=academy, trigger=ReminderRun.TRIGGER_DRY_RUN if dry_run else trigger,
        triggered_by=user, reference_date=on_date,
    )
    stats = defaultdict(int)
    try:
        policy = get_policy(academy, create=not dry_run)
        if not dry_run:
            stats["resumed"] = resume_pending(academy, policy, now=now)
        plan, computation = plan_reminders(academy, on_date, policy=policy, now=now)
        stats["items"] = len(computation.items)
        stats["overdue"] = sum(1 for i in computation.items if i.status in (STATUS_OVERDUE, STATUS_PARTIAL))
        stats["anomalies"] = len(computation.anomalies)
        stats["planned"] = len(plan)
        if dry_run:
            run.stats = dict(stats)
            run.status = ReminderRun.DONE
            run.finished_at = timezone.now()
            run.save(update_fields=["stats", "status", "finished_at"])
            run.plan = plan
            run.computation = computation
            return run

        by_recipient = defaultdict(list)
        for entry in plan:
            by_recipient[entry["recipient"].pk].append(entry)

        for entries in by_recipient.values():
            recipient = entries[0]["recipient"]
            created = []
            for entry in entries:
                item = entry["item"]
                key = PaymentReminder.make_key(item.installment.pk, item.student.pk, recipient.pk, entry["level"])
                try:
                    with transaction.atomic():
                        created.append(PaymentReminder.objects.create(
                            academy=academy, student=item.student, fee_schedule=item.fee,
                            installment=item.installment, recipient=recipient, level=entry["level"],
                            idempotency_key=key, run=run, currency=item.currency,
                            due_date=item.installment.due_date,
                            fee_label=(item.fee.label or type_label(item.fee.payment_type))[:160],
                            installment_label=item.installment.label[:80],
                            amount_expected_minor=item.expected - item.discount,
                            amount_paid_minor=item.paid,
                            amount_due_minor=item.outstanding,
                        ))
                except IntegrityError:
                    # Déjà produite (exécution concurrente ou rejouée).
                    stats["duplicates_avoided"] += 1
            if not created:
                continue
            _deliver(academy, policy, recipient, created, stats)
            stats["reminders"] += len(created)
        run.status = ReminderRun.DONE
    except Exception as exc:
        logger.exception("Relances %s : échec de l'exécution", academy.code)
        run.status = ReminderRun.FAILED
        run.error = f"{type(exc).__name__}: {exc}"[:2000]
    run.stats = dict(stats)
    run.finished_at = timezone.now()
    run.save(update_fields=["stats", "status", "finished_at", "error"])
    logger.info("Relances %s (%s) : %s", academy.code, run.trigger, dict(stats))
    return run


def _deliver(academy, policy, recipient, rows, stats=None):
    """
    Notification interne puis e-mail pour un groupe de relances d'un même
    responsable. Les statuts écrits sont ceux réellement constatés :
    notification CRÉÉE (donc visible dans l'espace parent), e-mail REMIS au
    serveur de messagerie, en nouvel essai, ou en échec.
    """
    from apps.notifications.mailer import send_tracked_email
    from apps.notifications.models import Notification
    from apps.notifications.utils import notification_path
    from apps.payments.models import PaymentReminder

    stats = stats if stats is not None else defaultdict(int)
    subject, text, html_body, notif_title, notif_message = build_message(academy, policy, recipient, rows)
    notification = next((r.notification for r in rows if r.notification_id), None)
    if notification is None and policy.send_notification:
        notification = Notification.objects.create(
            user=recipient, type="payment", title=notif_title[:200], message=notif_message,
            related_url=notification_path(recipient, "payments"),
        )
        stats["notifications"] += 1
    status = PaymentReminder.NOTIFIED if notification else PaymentReminder.NO_CHANNEL
    delivery, error, email_to = None, "", ""
    if policy.send_email and _email_ok(recipient.email):
        email_to = recipient.email
        delivery = send_tracked_email(
            purpose=PURPOSE_REMINDER, to_email=recipient.email, subject=subject,
            text_body=text, html_body=html_body, entity=academy,
            reference=f"REM-{rows[0].pk}",
            language=getattr(recipient, "preferred_language", ""),
        )
        if delivery.is_delivered_to_provider:
            status = PaymentReminder.SENT
            stats["emails_sent"] += 1
        elif delivery.status == delivery.RETRY:
            status, error = PaymentReminder.RETRY, delivery.last_error
            stats["emails_retry"] += 1
        else:
            status, error = PaymentReminder.FAILED, delivery.last_error
            stats["emails_failed"] += 1
    elif policy.send_email:
        error = "Aucune adresse e-mail valide pour ce responsable."
        stats["no_email"] += 1
    PaymentReminder.objects.filter(pk__in=[r.pk for r in rows]).update(
        status=status, notification=notification, email_delivery=delivery,
        email_to=email_to, error=error, updated_at=timezone.now(),
    )
    return status


def resume_pending(academy, policy, now=None, older_than_minutes=10):
    """
    Relances enregistrées mais jamais acheminées (worker arrêté entre
    l'écriture et l'envoi). Sans cette reprise, la clé d'idempotence
    empêcherait à jamais leur envoi. Une relance déjà rattachée à un
    e-mail n'est pas renvoyée.
    """
    from apps.payments.models import PaymentReminder

    now = now or timezone.now()
    stale = list(
        PaymentReminder.objects.filter(
            academy=academy, status=PaymentReminder.PENDING, email_delivery__isnull=True,
            created_at__lt=now - timedelta(minutes=older_than_minutes),
        ).select_related("recipient", "student", "notification")
    )
    groups = defaultdict(list)
    for row in stale:
        groups[row.recipient_id].append(row)
    for rows in groups.values():
        _deliver(academy, policy, rows[0].recipient, rows)
    return len(stale)


def sync_reminders_with_delivery(delivery):
    """
    Reporte sur les relances liées le résultat d'une nouvelle tentative
    automatique de l'e-mail (le contenu est rejoué depuis l'archive).
    """
    from apps.notifications.email_models import EmailDelivery
    from apps.payments.models import PaymentReminder

    rows = PaymentReminder.objects.filter(email_delivery=delivery)
    if not rows.exists():
        return 0
    if delivery.status in (EmailDelivery.SENT, EmailDelivery.ACCEPTED):
        status, error = PaymentReminder.SENT, ""
    elif delivery.status == EmailDelivery.RETRY:
        status, error = PaymentReminder.RETRY, delivery.last_error
    else:
        status, error = PaymentReminder.FAILED, delivery.last_error
    return rows.update(status=status, error=error, updated_at=timezone.now())
