import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Megaphone, Paperclip, ChevronDown, ChevronUp, Search } from "lucide-react";
import { announcementsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { t, dateLocale } from "../../i18n";

export default function SharedAnnouncements() {
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState(null);

  const { data, isLoading } = useQuery({
    queryKey: ["announcements"],
    queryFn: () => announcementsAPI.list(),
    refetchInterval: 60000,
  });

  const all = data?.data?.results || data?.data || [];
  const announcements = all.filter(a =>
    a.title?.toLowerCase().includes(search.toLowerCase()) ||
    a.content?.toLowerCase().includes(search.toLowerCase())
  );

  const formatDate = d => new Date(d).toLocaleDateString(dateLocale(), { day: "2-digit", month: "long", year: "numeric" });

  return (
    <div className="space-y-6">
      <PageHeader title={t("Annonces")} subtitle={t("{n} annonce(s)", { n: announcements.length })} />
      <div className="card flex items-center gap-3">
        <Search className="w-4 h-4 text-slate-400 shrink-0" />
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder={t("Rechercher une annonce…")}
          className="flex-1 bg-transparent outline-none text-sm text-slate-700 placeholder:text-slate-400" />
      </div>
      {isLoading ? (
        <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin" /></div>
      ) : announcements.length === 0 ? (
        <div className="card text-center py-16">
          <Megaphone className="w-12 h-12 text-slate-200 mx-auto mb-3" />
          <p className="text-slate-400 font-medium">{t("Aucune annonce disponible")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {announcements.map(a => (
            <div key={a.id} className="card overflow-hidden">
              <button onClick={() => setExpanded(expanded === a.id ? null : a.id)} className="w-full flex items-start gap-4 text-left">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-primary to-violet-600 flex items-center justify-center shrink-0 mt-0.5">
                  <Megaphone className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-semibold text-slate-800 truncate">{a.title}</h3>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-slate-400">{formatDate(a.created_at)}</span>
                      {expanded === a.id ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    </div>
                  </div>
                  <p className="text-sm text-slate-500 mt-0.5">{t("Par")} {a.author_name || "Administration"}</p>
                  {expanded !== a.id && <p className="text-sm text-slate-600 mt-1 line-clamp-2">{a.content}</p>}
                </div>
              </button>
              {expanded === a.id && (
                <div className="mt-4 pt-4 border-t border-slate-100">
                  <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{a.content}</p>
                  {a.attachment && (
                    <a href={a.attachment} target="_blank" rel="noreferrer"
                      className="inline-flex items-center gap-2 mt-4 text-sm text-primary bg-primary-50 hover:bg-primary/10 rounded-xl px-4 py-2 transition-colors">
                      <Paperclip className="w-4 h-4" />
                      <span>{a.attachment_name || "Télécharger la pièce jointe"}</span>
                    </a>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
