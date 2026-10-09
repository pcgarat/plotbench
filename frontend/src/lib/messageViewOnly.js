/**
 * Vista de mensaje aislado: al abrir un mensaje desde el listado queremos ver solo
 * ese mensaje (ni el prompt que lo generó ni ningún otro del hilo). El composer sigue
 * disponible para continuar la conversación, pero la transcripción se limita al mensaje.
 */
export function isMessageViewOnly(state, conversationId) {
  if (!state || !state.messageViewOnly) return false;
  const target = state.messageViewOnlyConversationId || null;
  if (conversationId && target && conversationId !== target) return false;
  return true;
}

/**
 * Mensajes visibles del panel: en vista aislada solo el mensaje seleccionado; si no,
 * la ventana normal.
 */
export function messagesForPane(state, display) {
  if (!isMessageViewOnly(state, state && state.conversationId)) return display;
  const id = state.messageViewOnlyMessageId;
  return (display || []).filter((m) => m && m.id === id);
}
