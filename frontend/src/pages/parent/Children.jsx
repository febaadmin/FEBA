/**
 * Mes Enfants — v15 (fixed)
 *
 * BUG FIX #3 : Affiche le vrai contact parent (nom, téléphone, email)
 *              au lieu des labels statiques "guardian" / "father"
 * BUG FIX #5 : Synchronisation complète — toutes les données du profil parent
 *              sont affichées (user_phone, user_email, etc.)
 */
import { useQuery } from "@tanstack/react-query";
import { parentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { GraduationCap, Calendar, Users, Phone, Mail, UserCheck } from "lucide-react";
import { motion } from "framer-motion";

const RELATIONSHIP_LABELS = {
  father: "Père",
  mother: "Mère",
  guardian: "Tuteur / Tutrice",
  other: "Autre",
};

export default function ParentChildren() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["parent-me"],
    queryFn: parentsAPI.me,
  });

  const parent = data?.data;
  const children = parent?.children_links || [];

  if (isLoading) return (
    <div className="space-y-4">
      {[...Array(2)].map((_,i) => <div key={i} className="skeleton h-36 rounded-2xl" />)}
    </div>
  );

  if (error) return (
    <div className="card text-center py-12">
      <div className="w-16 h-16 rounded-2xl bg-amber-50 flex items-center justify-center mx-auto mb-4">
        <Users className="w-8 h-8 text-amber-400" />
      </div>
      <p className="font-semibold text-slate-700">Profil parent introuvable</p>
      <p className="text-sm mt-1 text-slate-500">
        {error?.response?.data?.error || "Votre profil parent n'est pas encore configuré. Contactez l'administration."}
      </p>
    </div>
  );

  return (
    <div className="space-y-6">
      <PageHeader title="Mes Enfants" subtitle={`${children.length} enfant(s) enregistré(s)`} />

      {/* Bloc contact parent — données réelles */}
      {parent && (
        <div className="card border border-amber-100 bg-amber-50/40">
          <div className="flex items-center gap-3 mb-3">
            <UserCheck className="w-5 h-5 text-amber-600" />
            <h3 className="font-semibold text-slate-700 text-sm">Votre fiche contact</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
            <div>
              <p className="text-xs text-slate-400 mb-0.5">Nom complet</p>
              <p className="font-semibold text-slate-800">{parent.full_name || "—"}</p>
            </div>
            <div className="flex items-center gap-2">
              <Phone className="w-4 h-4 text-slate-400 shrink-0" />
              <div>
                <p className="text-xs text-slate-400 mb-0.5">Téléphone</p>
                <p className="font-medium text-slate-700">{parent.user_phone || "—"}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Mail className="w-4 h-4 text-slate-400 shrink-0" />
              <div>
                <p className="text-xs text-slate-400 mb-0.5">Email</p>
                <p className="font-medium text-slate-700 text-xs">{parent.user_email || "—"}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {children.length === 0 ? (
        <div className="card text-center py-12 text-slate-400">
          <Users className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="font-medium">Aucun enfant associé à votre compte</p>
          <p className="text-sm mt-1">Contactez l'administration pour lier vos enfants.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {children.map((link, i) => {
            const child = link.student_detail || {};
            const relLabel = RELATIONSHIP_LABELS[link.relationship] || link.relationship || "—";

            return (
              <motion.div key={i} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }} className="card border-l-4 border-amber-500">

                {/* En-tête enfant */}
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-white text-2xl font-bold shrink-0">
                    {(child.first_name || "?")[0]}
                  </div>
                  <div className="flex-1">
                    <p className="font-bold text-slate-800 text-lg">
                      {child.full_name || `${child.first_name || ""} ${child.last_name || ""}`.trim() || "—"}
                    </p>
                    <p className="text-sm text-slate-500">{relLabel}</p>
                    {link.is_primary_contact && (
                      <span className="badge bg-amber-100 text-amber-700 mt-1 text-xs">Contact principal</span>
                    )}
                  </div>
                </div>

                {/* Infos scolaires */}
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div className="bg-slate-50 rounded-xl p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <GraduationCap className="w-4 h-4 text-slate-400" />
                      <span className="text-xs font-medium text-slate-500">Classe</span>
                    </div>
                    <p className="font-semibold text-slate-800">{child.class_name || "—"}</p>
                    <p className="text-xs text-slate-400">{child.school_year_name || "—"}</p>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <Calendar className="w-4 h-4 text-slate-400" />
                      <span className="text-xs font-medium text-slate-500">Matricule</span>
                    </div>
                    <p className="font-semibold text-slate-800 text-sm font-mono">{child.matricule || "—"}</p>
                    <p className="text-xs text-slate-400">
                      {child.gender === "M" ? "Garçon" : child.gender === "F" ? "Fille" : "—"}
                    </p>
                  </div>
                </div>

                {/* Contact parent — données réelles BUG FIX #3 */}
                {parent && (
                  <div className="border-t border-slate-100 pt-3">
                    <p className="text-xs font-medium text-slate-400 mb-2">Contact enregistré</p>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 text-sm">
                        <UserCheck className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span className="text-slate-700 font-medium">{parent.full_name}</span>
                        <span className="text-slate-400 text-xs">({relLabel})</span>
                      </div>
                      {parent.user_phone ? (
                        <div className="flex items-center gap-2 text-sm">
                          <Phone className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <a href={`tel:${parent.user_phone}`} className="text-slate-600 hover:text-primary">
                            {parent.user_phone}
                          </a>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-sm text-slate-400">
                          <Phone className="w-3.5 h-3.5 shrink-0" />
                          <span className="text-xs italic">Téléphone non renseigné</span>
                        </div>
                      )}
                      {parent.user_email && (
                        <div className="flex items-center gap-2 text-sm">
                          <Mail className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <a href={`mailto:${parent.user_email}`} className="text-slate-600 hover:text-primary text-xs">
                            {parent.user_email}
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
