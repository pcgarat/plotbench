Última modificación: 2026-10-10

# Checklist: distinguir mensajes de conversaciones

**Rama:** `feat/mensajes-vs-conversaciones`

## Objetivo

Separar el concepto de **mensaje** (cada respuesta del agente) del de **conversación**
(hilo completo). El panel izquierdo lista mensajes con su título (primera frase, sin
signos y con espacios entre palabras) y su fecha; al hacer clic se muestra **solo ese
mensaje**, sin el prompt que lo generó ni el resto del hilo, dejando el composer
disponible para continuar.

## Backend

- [x] `Message.title` (`VARCHAR(80)`, indexado) en `app/models.py`.
- [x] Migración idempotente + backfill al arrancar (`app/db.py`).
- [x] `derive_message_title` (primera frase, sin signos y con espacios) en `app/services/message_title.py`.
- [x] `add_message` / `update_message_content` persisten `title`.
- [x] `GET /api/messages/list`: `sort` (`date|title|length|photos`), `direction`
      (`asc|desc`, opcional; por defecto el propio de cada criterio), `q`,
      `search_in` (`title|both`), `model_id`, paginación y `models`.
- [x] `GET /api/messages/models`: solo modelos que han generado algún mensaje.
- [x] Tests: `tests/test_message_title.py`, `tests/test_api_messages_list.py`.

## Frontend — estado

- [x] `historyStore`: `mode` (`messages` por defecto | `conversations`), `messageSort`,
      `messageSearchIn`, `messageListItems`, `messageListTotal`, `messageListQuery`,
      `messageModelFilter`, `messageModels`.
- [x] `sessionStore`: `messageViewOnly`, `messageViewOnlyMessageId`,
      `messageViewOnlyConversationId`.
- [x] `lib/messageViewOnly.js`: `isMessageViewOnly`, `messagesForPane`.
- [x] `openIsolatedMessage(conversationId, messageId)` en `app/sessionActions.js`.
- [x] `clearIsolatedMessageView()`: al continuar la conversación, saltar desde el árbol
      o la galería se abandona la vista aislada.
- [x] `applyTreeToStore` limpia la vista aislada en cada turno nuevo.
- [x] `refreshLeftHistory` refresca según el modo activo (mensajes o árbol).

## Frontend — UI

- [x] Conmutador **Mensajes | Conversaciones** (`HistoryModeSwitch`).
- [x] Búsqueda con ámbito `Solo título` / `Título y cuerpo`.
- [x] Controles de orden: fecha, título, extensión, nº de fotos.
- [x] Dirección del orden ascendente/descendente (botón ↑/↓).
- [x] Selector de modelo (solo generadores; sigue completo al filtrar).
- [x] Listado de mensajes: título + fecha + métricas; clic abre el mensaje aislado.
- [x] Paginación incremental («Cargar más»).
- [x] Persistencia de modo/orden/ámbito en el servidor (preferencias por usuario).
- [x] CSS del panel y modo oscuro.

## Verificación

- [x] `pytest -m "not e2e"` → 1009 passed.
- [x] `vitest run` → 274 passed.
- [x] `npm run build` → SPA publicado en `app/static`.

## Pendiente / seguimiento

- [ ] Revisión visual manual en navegador (claro y oscuro).
- [ ] Evaluar agrupar el listado de mensajes por fecha (hoy/ayer/semana) como el árbol.
