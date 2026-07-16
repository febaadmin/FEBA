/**
 * Emplois du temps de mes enfants — v15 (refonte UX complète)
 *
 * BUG FIX #4 : Vraie grille hebdomadaire (Lun→Sam) par enfant
 *              - Tableau responsive avec lignes horaires
 *              - Colonnes Lundi à Samedi
 *              - Chaque cellule : matière + salle + enseignant
 *              - Mobile : vue liste par jour
 *              - Multi-enfants : onglets
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Calendar, BookOpen, User, Clock, MapPin, ChevronLeft, ChevronRight } from "lucide-react";
import { parentsAPI, scheduleAPI } from "../../api";
import { t } from "../../i18n";

const DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];
const DAY_SHORT = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];

const SUBJECT_COLORS = [
  "bg-blue-50 border-blue-200 text-blue-800",
  "bg-emerald-50 border-emerald-200 text-emerald-800",
  "bg-amber-50 border-amber-200 text-amber-800",
  "bg-rose-50 border-rose-200 text-rose-800",
  "bg-purple-50 border-purple-200 text-purple-800",
  "bg-cyan-50 border-cyan-200 text-cyan-800",
  "bg-orange-50 border-orange-200 text-orange-800",
  "bg-indigo-50 border-indigo-200 text-indigo-800",
];

function buildColorMap(schedules) {
  const map = {};
  let idx = 0;
  schedules.forEach(s => {
    if (s.subject_name && !(s.subject_name in map)) {
      map[s.subject_name] = SUBJECT_COLORS[idx % SUBJECT_COLORS.length];
      idx++;
    }
  });
  return map;
}

/** Cellule d'un créneau */
function SlotCell({ item, colorClass }) {
  return (
    <div className={`rounded-lg border px-2 py-1.5 text-xs mb-1 ${colorClass}`}>
      <p className="font-semibold leading-tight">{item.subject_name}</p>
      <p className="text-xs opacity-70 flex items-center gap-1 mt-0.5">
        <Clock className="w-2.5 h-2.5 inline" />
        {item.start_time?.slice(0,5)}–{item.end_time?.slice(0,5)}
      </p>
      {item.room && (
        <p className="text-xs opacity-60 flex items-center gap-1">
          <MapPin className="w-2.5 h-2.5 inline" />{item.room}
        </p>
      )}
      {item.teacher_name && (
        <p className="text-xs opacity-60 truncate">{item.teacher_name}</p>
      )}
    </div>
  );
}

/** Grille hebdomadaire d'un enfant */
function WeekGrid({ schedules }) {
  const colorMap = buildColorMap(schedules);

  // Récupérer toutes les tranches horaires uniques, triées
  const timeSlots = [...new Set(
    schedules.map(s => `${s.start_time?.slice(0,5)}–${s.end_time?.slice(0,5)}`)
  )].sort();

  if (schedules.length === 0) {
    return (
      <div className="text-center py-10 text-slate-400">
        <BookOpen className="w-10 h-10 mx-auto mb-2 opacity-30" />
        <p className="text-sm">{t("Aucun créneau disponible.")}</p>
      </div>
    );
  }

  return (
    <>
      {/* Vue desktop : tableau */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-slate-50">
              <th className="border border-slate-200 px-3 py-2 text-left font-semibold text-slate-500 w-24">{t("Horaire")}</th>
              {DAYS.map((d, i) => (
                <th key={i} className="border border-slate-200 px-3 py-2 text-center font-semibold text-slate-600 min-w-[120px]">
                  {d}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {timeSlots.map(slot => {
              const [start, end] = slot.split("–");
              return (
                <tr key={slot} className="hover:bg-slate-50/50">
                  <td className="border border-slate-200 px-3 py-2 font-mono text-slate-500 whitespace-nowrap bg-slate-50/60">
                    <div className="flex items-center gap-1">
                      <Clock className="w-3 h-3 opacity-50" />
                      {slot}
                    </div>
                  </td>
                  {DAYS.map((_, di) => {
                    const items = schedules.filter(
                      s => s.day_of_week === di &&
                           s.start_time?.slice(0,5) === start
                    );
                    return (
                      <td key={di} className="border border-slate-200 px-2 py-1.5 align-top">
                        {items.map((item, k) => (
                          <SlotCell key={k} item={item} colorClass={colorMap[item.subject_name] || SUBJECT_COLORS[0]} />
                        ))}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Vue mobile : liste par jour */}
      <div className="md:hidden space-y-4">
        {DAYS.map((day, di) => {
          const dayItems = schedules
            .filter(s => s.day_of_week === di)
            .sort((a, b) => (a.start_time > b.start_time ? 1 : -1));
          if (dayItems.length === 0) return null;
          return (
            <div key={di}>
              <p className="font-bold text-slate-700 mb-2 text-sm uppercase tracking-wide border-b border-slate-100 pb-1">
                {t(day)}
              </p>
              <div className="space-y-2">
                {dayItems.map((item, k) => (
                  <div key={k} className={`rounded-xl border px-3 py-2.5 ${colorMap[item.subject_name] || SUBJECT_COLORS[0]}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm">{item.subject_name}</span>
                      <span className="text-xs opacity-70">
                        {item.start_time?.slice(0,5)}–{item.end_time?.slice(0,5)}
                      </span>
                    </div>
                    <div className="flex gap-3 mt-1 text-xs opacity-70">
                      {item.teacher_name && <span>{item.teacher_name}</span>}
                      {item.room && <span className="flex items-center gap-0.5"><MapPin className="w-3 h-3" />{item.room}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

export default function ParentSchedule() {
  const [activeChild, setActiveChild] = useState(0);

  // 1. Charger le profil parent + ses enfants
  const { data: parentData, isLoading: parentLoading } = useQuery({
    queryKey: ["parent-me"],
    queryFn: parentsAPI.me,
  });

  const parent   = parentData?.data;
  const children = parent?.children_links || [];

  // Extraire les IDs de classes uniques
  const classIds = [...new Set(
    children.map(l => l.student_detail?.class_id).filter(Boolean)
  )];

  // 2. Charger les emplois du temps pour chaque classe
  const { data: schedulesData, isLoading: schedLoading } = useQuery({
    queryKey: ["parent-schedule", classIds.join(",")],
    queryFn: async () => {
      if (!classIds.length) return {};
      const results = await Promise.all(
        classIds.map(id => scheduleAPI.byClass(id))
      );
      const map = {};
      classIds.forEach((id, idx) => {
        map[id] = results[idx]?.data?.results || results[idx]?.data || [];
      });
      return map;
    },
    enabled: classIds.length > 0,
  });

  const schedulesByClass = schedulesData || {};
  const isLoading = parentLoading || schedLoading;

  // Préparer les données par enfant
  const childrenData = children.map(link => {
    const detail = link.student_detail || {};
    const classId = detail.class_id;
    const schedules = classId ? (schedulesByClass[classId] || []) : [];
    return { link, detail, classId, schedules };
  });

  const currentChild = childrenData[activeChild];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-primary-50 flex items-center justify-center">
          <Calendar className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">{t("Emplois du temps")}</h1>
          <p className="text-sm text-slate-500">{t("Planning hebdomadaire de mes enfants")}</p>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-3">
          {[1,2].map(i => <div key={i} className="skeleton h-48 w-full rounded-2xl" />)}
        </div>
      )}

      {/* Aucun enfant */}
      {!isLoading && children.length === 0 && (
        <div className="card text-center py-16 text-slate-400">
          <User className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="font-medium">{t("Aucun enfant enregistré")}</p>
          <p className="text-sm mt-1">{t("Contactez l'administration pour associer vos enfants à votre compte.")}</p>
        </div>
      )}

      {/* Onglets enfants + Grille */}
      {!isLoading && childrenData.length > 0 && (
        <>
          {/* Onglets si plusieurs enfants */}
          {childrenData.length > 1 && (
            <div className="flex gap-2 flex-wrap">
              {childrenData.map((c, i) => (
                <button
                  key={i}
                  onClick={() => setActiveChild(i)}
                  className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                    activeChild === i
                      ? "bg-primary text-white shadow-md"
                      : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {c.detail.full_name || c.detail.first_name || `Enfant ${i+1}`}
                </button>
              ))}
            </div>
          )}

          {/* Tableau de l'enfant actif */}
          {currentChild && (
            <div className="card">
              {/* En-tête enfant */}
              <div className="flex items-center justify-between mb-5 pb-4 border-b border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-primary text-white flex items-center justify-center font-bold text-sm">
                    {currentChild.detail.first_name?.[0] || "?"}
                  </div>
                  <div>
                    <p className="font-semibold text-slate-800">
                      {currentChild.detail.full_name ||
                       `${currentChild.detail.first_name || ""} ${currentChild.detail.last_name || ""}`.trim()}
                    </p>
                    <p className="text-xs text-slate-500">
                      {currentChild.detail.class_name || "Classe non assignée"}
                      {currentChild.detail.school_year_name ? ` · ${currentChild.detail.school_year_name}` : ""}
                    </p>
                  </div>
                </div>
                {/* Légende compteur */}
                <span className="text-xs text-slate-400 bg-slate-50 px-3 py-1 rounded-full">
                  {currentChild.schedules.length} créneau(x)
                </span>
              </div>

              {/* Navigation enfants (mobile) */}
              {childrenData.length > 1 && (
                <div className="flex items-center justify-between mb-4 md:hidden">
                  <button
                    onClick={() => setActiveChild(i => Math.max(0, i-1))}
                    disabled={activeChild === 0}
                    className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-30"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-sm text-slate-500">
                    {activeChild + 1} / {childrenData.length}
                  </span>
                  <button
                    onClick={() => setActiveChild(i => Math.min(childrenData.length-1, i+1))}
                    disabled={activeChild === childrenData.length-1}
                    className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-30"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}

              <WeekGrid schedules={currentChild.schedules} />
            </div>
          )}

          {/* Résumé rapide par matière */}
          {currentChild && currentChild.schedules.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-slate-700 mb-3 text-sm">{t("Matières enseignées")}</h3>
              <div className="flex flex-wrap gap-2">
                {[...new Set(currentChild.schedules.map(s => s.subject_name))].map((subj, i) => (
                  <span key={subj} className={`px-3 py-1 rounded-full text-xs font-medium border ${SUBJECT_COLORS[i % SUBJECT_COLORS.length]}`}>
                    {subj}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
