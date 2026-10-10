Última modificación: 2026-10-10

# Checklist: Selección de modelo/proveedor persistente y "sticky"

**Objetivo:** Que el proveedor y el modelo elegidos en el panel de conversación sean los que de verdad se usan al generar, que la selección no se revierta al borrar mensajes o refrescar la conversación, y que una elección explícita del usuario mande aunque cambie de conversación.

**Fecha de creación:** 2026-10-10

**Problema original:** al cambiar el modelo y eliminar mensajes, el panel volvía siempre a `ollama`. Además, lo seleccionado en la UI no siempre era lo que el backend usaba (se persistía en la conversación por `saveConversationMeta`, que no se llamaba al cambiar de modelo).

## Causa raíz

- `changeModel` / `changeProvider` solo tocaban `settingsStore`; las columnas `provider` / `model_id` de la conversación (lo que usa el backend) no se actualizaban.
- `deleteMessageFromHistory` recarga la conversación y `setCurrentConversation` volvía a volcar los valores persistidos (antiguos) sobre el store.

## Decisiones de diseño

- **Fuente única de verdad:** el backend genera con `conv.provider` / `conv.model_id`. Al enviar, la selección viva de la UI viaja en el body y el backend la persiste → lo mostrado es lo usado.
- **Modelo global (sticky):** una vez el usuario elige proveedor/modelo (`modelSelectionLocal`), abrir otra conversación no pisa esa elección. Antes de la primera elección se adopta la de la conversación.

## Backend

- [x] `MessageSend` acepta `provider` y `model` opcionales (schemas.py).
- [x] `_resolve_turn_model()` en `api_conversations.py`: aplica y persiste el override si difiere; respeta la conversación si no.
- [x] Usado en `send_message_stream` y en `send_message`.
- [x] `PromptGeneratorTurnIn` acepta `provider`/`model`; `run_turn` los aplica y persiste.
- [x] Tests: `test_stream_con_provider_model_override_persiste_el_usado`,
  `test_stream_sin_override_respeta_el_modelo_de_la_conversacion`,
  `test_send_message_con_override_usa_y_persiste_el_modelo_elegido`,
  `test_turn_prompt_generator_usa_y_persiste_el_modelo_elegido`.

## Frontend

- [x] `settingsStore.modelSelectionLocal` (persistente) marca la elección explícita del usuario.
- [x] `changeModel` / `changeProvider` marcan la elección y sincronizan la conversación (debounce 250 ms).
- [x] `flushPendingConversationModelSync()` fuerza el guardado pendiente antes de enviar.
- [x] `sendMessage` y `sendPromptGeneratorTurn` envían `provider` y `model` vivos en el body.
- [x] `setCurrentConversation`: solo adopta el modelo de la conversación si no hay elección local (sticky).
- [x] Tests: `conversationModelSync.test.js`, `sendMessageModel.test.js`, `sessionModelSticky.test.js`.

## Regresión

- [x] Cambiar modelo y eliminar mensajes mantiene la selección (no vuelve a `ollama`).
- [x] El modelo del desplegable coincide con el `model` que recibe el provider.
- [x] Sin override, el comportamiento previo se conserva (usa el modelo de la conversación).
