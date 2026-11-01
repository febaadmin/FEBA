/**
 * Onglets de l'emploi du temps : nommés d'après les académies réelles.
 *
 * Avant : « FEBA — cours présentiels » et « FEBA FHA — séances en ligne »
 * écrits en dur. Une académie « testete » voyait son emploi du temps sous
 * le nom d'une autre ; avec 7 ou 19 académies, les libellés étaient faux.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const ctx = vi.hoisted(() => ({ value: null }));
vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => ctx.value }));
vi.mock("./schedule/CampusSchedule", () => ({ default: () => <div data-testid="campus-view" /> }));
vi.mock("./schedule/OnlineSchedule", () => ({ default: () => <div data-testid="online-view" /> }));

import AdminSchedule, { academyList } from "./Schedule";

const academy = (i, type, name = `Académie n°${i}`) => ({
  id: i, code: `A${i}`, name, short_name: name, entity_type: type,
});
const TESTETE = academy(99, "campus", "Académie Évangélique Saint-Éloi de Natitingou");

function setCtx({ active = null, all = false, allowed = [], canSwitch = false }) {
  ctx.value = { activeAcademy: active, isAllAcademies: all, allowedAcademies: allowed, canSwitchAcademy: canSwitch };
}

const tabs = () => screen.queryAllByRole("tab");
const body = () => document.body.textContent;

beforeEach(() => setCtx({ active: TESTETE, allowed: [TESTETE] }));

describe("une académie active", () => {
  it("testete (présentielle) : un seul onglet, à son nom", () => {
    render(<AdminSchedule />);
    expect(tabs()).toHaveLength(1);
    expect(tabs()[0].textContent).toMatch("Académie Évangélique Saint-Éloi de Natitingou - cours présentiels");
    expect(body()).not.toMatch(/FEBA/);
    expect(screen.getByTestId("campus-view")).toBeTruthy();
  });

  it("une académie en ligne quelconque : son onglet de séances en ligne", () => {
    const online = academy(5, "online", "Lycée Numérique du Zou");
    setCtx({ active: online, allowed: [online] });
    render(<AdminSchedule />);
    expect(tabs()).toHaveLength(1);
    expect(tabs()[0].textContent).toMatch("Lycée Numérique du Zou - séances en ligne");
    expect(screen.getByTestId("online-view")).toBeTruthy();
  });

  it("super administrateur sur testete : nomme les académies de l'autre type, sans onglet vide", () => {
    const others = [academy(1, "online", "École en ligne Alpha"), academy(2, "online", "École en ligne Bêta")];
    setCtx({ active: TESTETE, allowed: [TESTETE, ...others], canSwitch: true });
    render(<AdminSchedule />);
    expect(tabs()).toHaveLength(1);
    expect(screen.getByTestId("schedule-other-academies").textContent)
      .toMatch("École en ligne Alpha, École en ligne Bêta");
  });
});

describe("« Toutes les Académies »", () => {
  for (const n of [2, 7, 19]) {
    it(`${n} académies : un onglet par type présent, liste abrégée, total exact`, () => {
      const allowed = Array.from({ length: n }, (_, i) => academy(i + 1, i % 3 === 0 ? "online" : "campus"));
      const online = allowed.filter((a) => a.entity_type === "online");
      const campus = allowed.filter((a) => a.entity_type === "campus");
      setCtx({ all: true, allowed, canSwitch: true });
      render(<AdminSchedule />);
      expect(tabs()).toHaveLength(2);
      const campusTab = screen.getByTestId("schedule-tab-campus");
      const onlineTab = screen.getByTestId("schedule-tab-online");
      expect(campusTab.textContent).toMatch(`Cours présentiels - ${campus.length} académie(s)`);
      expect(onlineTab.textContent).toMatch(`Séances en ligne - ${online.length} académie(s)`);
      // Toutes les académies figurent dans l'info-bulle, même au-delà de 3.
      expect(campusTab.getAttribute("title").split(", ")).toHaveLength(campus.length);
      if (campus.length > 3) expect(campusTab.textContent).toMatch(`et ${campus.length - 3} autres`);
      expect(body()).not.toMatch(/FEBA/);
      fireEvent.click(onlineTab);
      expect(screen.getByTestId("online-view")).toBeTruthy();
    });
  }

  it("aucune académie en ligne : pas d'onglet en ligne", () => {
    setCtx({ all: true, allowed: [academy(1, "campus"), TESTETE], canSwitch: true });
    render(<AdminSchedule />);
    expect(tabs()).toHaveLength(1);
    expect(screen.queryByTestId("schedule-tab-online")).toBeNull();
  });
});

describe("academyList", () => {
  it("abrège au-delà de trois noms", () => {
    const list = [1, 2, 3, 4, 5].map((i) => academy(i, "campus"));
    expect(academyList(list)).toBe("Académie n°1, Académie n°2, Académie n°3 et 2 autres");
    expect(academyList(list.slice(0, 2))).toBe("Académie n°1, Académie n°2");
  });
});
