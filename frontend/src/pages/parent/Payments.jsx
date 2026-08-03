import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { paymentsAPI, parentsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import CardPaymentPanel from "../../components/payments/CardPaymentPanel";
import { Download, CheckCircle, Clock, Info } from "lucide-react";
import { t } from "../../i18n";
import { useMoney } from "../../hooks/useMoney";

export default function ParentPayments() {
  // P0 : la devise vient de l'académie active, jamais d'un symbole codé en dur.
  const money = useMoney();
  // Retour depuis la page du prestataire. L'URL de succès est DEVINABLE :
  // elle ne prouve rien et n'est jamais présentée comme une confirmation.
  // Seul le webhook signé encaisse, et la ligne apparaît alors ci-dessous.
  const [searchParams] = useSearchParams();
  const returnState = searchParams.get("paiement");
  // Active year for context
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const years = yearsData?.data?.results || yearsData?.data || [];
  const activeYear = years.find(y => y.is_current);

  // Enfants du parent — sert au panneau de paiement par carte, qui a
  // besoin de savoir POUR QUI l'on paie.
  const { data: parentData } = useQuery({ queryKey: ["parent-me"], queryFn: parentsAPI.me });
  const children = (parentData?.data?.children_links || [])
    .map(link => link.student_detail)
    .filter(Boolean);

  // Backend filtre automatiquement par année active et par les enfants du parent
  const { data, isLoading } = useQuery({
    queryKey: ["parent-payments", activeYear?.id],
    queryFn: () => paymentsAPI.list(activeYear ? { school_year: activeYear.id } : {}),
    enabled: !!yearsData, // attend que les années soient chargées
  });
  const payments = data?.data?.results || data?.data || [];
  const confirmed = payments.filter(p => p.is_confirmed);
  // V8 — Le total est ventilé PAR DEVISE, à partir des unités mineures
  // renvoyées par le serveur. L'ancien `reduce` sur `parseFloat(amount)`
  // additionnait des dollars et des francs CFA en un seul nombre, et
  // l'affichait avec un symbole unique : le résultat ne correspondait à
  // aucune somme réelle.
  const total = money.totalOf(confirmed);

  const cols = [
    { key: "ref",     label: t("Référence"),  accessor: "reference_number" },
    { key: "student", label: t("Élève"),      accessor: "student_name" },
    { key: "type",    label: t("Type"),       render: r => t(r.payment_type_label || r.payment_type || "—") },
    { key: "amount",  label: t("Montant"),    render: r =>
        <span className="font-bold text-success">{money.amountOf(r)}</span> },
    { key: "method",  label: t("Mode"),       render: r => t(r.payment_method_label || r.payment_method || "—") },
    { key: "date",    label: t("Date"),       accessor: "payment_date" },
    { key: "status",  label: t("Statut"),     render: r => r.is_confirmed
        ? <span className="flex items-center gap-1 text-xs text-green-600 font-medium"><CheckCircle className="w-3 h-3"/>{t("Confirmé")}</span>
        : <span className="flex items-center gap-1 text-xs text-amber-500 font-medium"><Clock className="w-3 h-3"/>{t("En attente")}</span>
    },
    { key: "receipt", label: t("Reçu"),       sortable: false,
      render: r => (r.receipt_url || r.receipt_file)
        ? <a href={r.receipt_url || r.receipt_file} target="_blank" rel="noreferrer"
             className="flex items-center gap-1 text-xs text-primary hover:underline font-medium">
            <Download className="w-3 h-3" />{t("PDF")}</a>
        : <span className="text-xs text-slate-400">—</span>
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Paiements")}
        subtitle={t("Total confirmé : {n}", { n: total }) + (activeYear ? ` — ${activeYear.name}` : "")}
      />

      {returnState === "succes" && (
        <div className="card border border-blue-200 bg-blue-50/60 flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-slate-800">
              {t("Paiement en cours de vérification")}
            </p>
            <p className="text-sm text-slate-600 mt-1">
              {t("Votre banque a accepté l'opération. Elle est confirmée par notre prestataire, puis apparaît dans la liste ci-dessous avec son reçu — généralement en quelques secondes.")}
            </p>
          </div>
        </div>
      )}

      {returnState === "annule" && (
        <div className="card border border-slate-200 flex items-start gap-3">
          <Info className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
          <p className="text-sm text-slate-600">
            {t("Paiement abandonné. Rien n'a été débité ; vous pouvez recommencer quand vous le souhaitez.")}
          </p>
        </div>
      )}

      <CardPaymentPanel students={children} />

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="card text-center">
          <p className="text-xs text-slate-500 mb-1">{t("Total confirmé")}</p>
          <p className="text-xl font-bold text-green-600">{total}</p>
        </div>
        <div className="card text-center">
          <p className="text-xs text-slate-500 mb-1">{t("Nombre de paiements")}</p>
          <p className="text-xl font-bold text-primary">{payments.length}</p>
        </div>
      </div>

      <div className="card">
        <DataTable columns={cols} data={payments} loading={isLoading} />
      </div>
    </div>
  );
}
