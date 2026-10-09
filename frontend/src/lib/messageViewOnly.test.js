import { describe, it, expect } from "vitest";
import { isMessageViewOnly, messagesForPane } from "./messageViewOnly.js";

describe("messageViewOnly", () => {
  it("no activa en el estado por defecto", () => {
    expect(isMessageViewOnly({})).toBe(false);
    expect(isMessageViewOnly({ messageViewOnly: false, messageViewOnlyMessageId: "m1" })).toBe(false);
  });

  it("activa solo para la conversación dueña", () => {
    const state = { messageViewOnly: true, messageViewOnlyConversationId: "c1" };
    expect(isMessageViewOnly(state, "c1")).toBe(true);
    expect(isMessageViewOnly(state, "c2")).toBe(false);
    expect(isMessageViewOnly(state)).toBe(true);
  });

  it("messagesForPane deja la ventana intacta fuera de la vista aislada", () => {
    const display = [{ id: "m1" }, { id: "m2" }];
    expect(messagesForPane({}, display)).toBe(display);
  });

  it("messagesForPane filtra al único mensaje en vista aislada", () => {
    const display = [{ id: "m1" }, { id: "m2" }, { id: "m3" }];
    const state = { messageViewOnly: true, messageViewOnlyMessageId: "m2" };
    expect(messagesForPane(state, display).map((m) => m.id)).toEqual(["m2"]);
  });
});
