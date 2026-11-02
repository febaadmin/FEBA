import { describe, it, expect, vi } from "vitest";
import toast from "react-hot-toast";
import { signalerErreurLecture } from "./erreursRequetes";

vi.mock("react-hot-toast", () => ({ default: { error: vi.fn() } }));

describe("signalerErreurLecture", () => {
  it("prévient sur une panne ou une coupure", () => {
    expect(signalerErreurLecture({ response: { status: 500 } })).toBe(true);
    expect(signalerErreurLecture(new Error("Network Error"))).toBe(true);
    expect(toast.error).toHaveBeenCalledTimes(2);
  });
  it("se tait sur une annulation, un refus ou un 404", () => {
    toast.error.mockClear();
    expect(signalerErreurLecture({ code: "ERR_CANCELED" })).toBe(false);
    expect(signalerErreurLecture({ isStaleAcademy: true })).toBe(false);
    expect(signalerErreurLecture({ response: { status: 403 } })).toBe(false);
    expect(signalerErreurLecture({ response: { status: 404 } })).toBe(false);
    expect(signalerErreurLecture({ response: { status: 503 } })).toBe(false);
    expect(toast.error).not.toHaveBeenCalled();
  });
});
