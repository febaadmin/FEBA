/**
 * Grilles d'emploi du temps : chaque cours apparaît UNE fois.
 *
 * Défaut constaté sur la pile FEBA FHA (3 séances, 5 cartes affichées) :
 * les lignes de la grille sont des créneaux « début-fin », mais chaque
 * case ne comparait que l'heure de DÉBUT. Deux cours commençant à la même
 * heure avec des fins différentes produisaient deux lignes, et chaque
 * cours apparaissait dans les deux.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const empty = () => Promise.resolve({ data: [] });
vi.mock("../../../api", () => ({
  onlineSessionsAPI: { list: vi.fn() },
  scheduleAPI: { list: vi.fn() },
  classesAPI: { list: () => Promise.resolve({ data: [] }) },
  schoolsAPI: { years: () => Promise.resolve({ data: [] }), rooms: () => Promise.resolve({ data: [] }) },
  subjectsAPI: { list: () => Promise.resolve({ data: [] }) },
  teachersAPI: { list: () => Promise.resolve({ data: [] }) },
  virtualAPI: { list: () => Promise.resolve({ data: [] }) },
}));
vi.mock("../../../context/AcademyContext", () => ({
  useAcademy: () => ({ activeAcademy: { name: "FEBA FHA", short_name: "FEBA FHA" }, isAllAcademies: false }),
}));

import { onlineSessionsAPI, scheduleAPI } from "../../../api";
import OnlineSchedule from "./OnlineSchedule";
import CampusSchedule from "./CampusSchedule";

function renderWithQuery(ui) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); void empty; });

describe("grille des séances en ligne (FEBA FHA)", () => {
  it("deux séances à 22:00 de durées différentes : chacune une seule fois", async () => {
    onlineSessionsAPI.list.mockResolvedValue({ data: [
      { id: 1, day_of_week: 1, start_time_utc: "22:00:00", end_time_utc: "22:45", group_name: "Junior Roots",
        subject_name: "Français", local_start_label: "17:00", display_timezone: "America/New_York", is_active: true },
      { id: 2, day_of_week: 3, start_time_utc: "22:00:00", end_time_utc: "23:00", group_name: "French Explorers",
        subject_name: "Français", local_start_label: "17:00", display_timezone: "America/New_York", is_active: true },
    ] });
    renderWithQuery(<OnlineSchedule />);
    expect(await screen.findAllByText("Junior Roots")).toHaveLength(1);
    expect(screen.getAllByText("French Explorers")).toHaveLength(1);
  });
});

describe("grille des cours présentiels (FEBA)", () => {
  it("deux cours à 08:00 de fins différentes : chacun une seule fois", async () => {
    scheduleAPI.list.mockResolvedValue({ data: [
      { id: 1, day_of_week: 0, start_time: "08:00:00", end_time: "09:00:00", class_name: "CE1-A", subject_name: "Maths" },
      { id: 2, day_of_week: 2, start_time: "08:00:00", end_time: "10:00:00", class_name: "CM1-A", subject_name: "Sciences" },
    ] });
    renderWithQuery(<CampusSchedule />);
    expect(await screen.findAllByText(/Maths/)).toHaveLength(1);
    expect(screen.getAllByText(/Sciences/)).toHaveLength(1);
  });
});
