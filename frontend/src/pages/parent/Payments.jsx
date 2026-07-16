import { useQuery } from "@tanstack/react-query";
import { paymentsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import { Download, CheckCircle, Clock } from "lucide-react";
import { t } from "../../i18n";

export default function ParentPayments() {
  // Active year for context
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const years = yearsData?.data?.results || yearsData?.data || [];
  const activeYear = years.find(y => y.is_current);

  // Backend filtre automatiquement par année active et par les enfants du parent
  const { data, isLoading } = useQuery({
    queryKey: ["parent-payments", activeYear?.id],
    queryFn: () => paymentsAPI.list(activeYear ? { school_year: activeYear.id } : {}),
    enabled: !!yearsData, // attend que les années soient chargées
  });
  const payments = data?.data?.results || data?.data || [];
  const total = payments.filter(p => p.is_confirmed).reduce((sum, p) => sum + parseFloat(p.amount || 0), 0);

  const cols = [
    { key: "ref",     label: t("Référence"),  accessor: "reference_number" },
    { key: "student", label: t("Élève"),      accessor: "student_name" },
    { key: "type",    label: t("Type"),       render: r => t(r.payment_type_label || r.payment_type || "—") },
    { key: "amount",  label: t("Montant"),    render: r =>
        <span className="font-bold text-success">{Number(r.amount).toLocaleString()} FCFA</span> },
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
        subtitle={t("Total confirmé : {n} FCFA", { n: total.toLocaleString() }) + (activeYear ? ` — ${activeYear.name}` : "")}
      />

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="card text-center">
          <p className="text-xs text-slate-500 mb-1">{t("Total confirmé")}</p>
          <p className="text-xl font-bold text-green-600">{total.toLocaleString()} FCFA</p>
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
