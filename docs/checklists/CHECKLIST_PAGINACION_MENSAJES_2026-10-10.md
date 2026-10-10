Última modificación: 2026-10-10

# Checklist: paginación del listado de mensajes

**Rama:** `feat/paginacion-listado-mensajes`

## Objetivo

El listado de mensajes del panel izquierdo solo tenía paginación acumulativa
(«Cargar más»). Se sustituye por paginación real: elegir elementos por página,
indicar la página y saltar a la primera/última, mostrando **todos** los mensajes.

## Backend

- [x] `GET /api/messages/list` ya devolvía `limit`, `offset` y `total`; sin cambios de
      contrato. Se sube su tope de página a 200 (`crud.MESSAGE_LIST_LIMIT_MAX`) sin
      tocar el máximo del endpoint legado `/api/messages`.
- [x] Tests: `tests/test_api_messages_list.py` (límite 200 y 422 por encima).

## Frontend — lógica

- [x] `lib/messagePagination.js`: `normalizePageSize`, `totalPages`, `clampPage`,
      `pageOffset`, `pageRange` (+ `MESSAGE_PAGE_SIZE_OPTIONS`) y sus tests.
- [x] `historyStore`: `messagePage`, `messagePageSize`; persistencia de tamaño
      (`LEFT_HISTORY_PAGE_SIZE_KEY`).
- [x] `historyActions`: `loadMessageList` calcula `limit`/`offset` desde la página;
      nuevas acciones `goToMessagePage`, `goToFirstMessagePage`, `goToPrevMessagePage`,
      `goToNextMessagePage`, `goToLastMessagePage`, `setMessagePageSize`.
- [x] Filtro, orden y tamaño de página reinician a la primera; la navegación no.
- [x] Persistencia por usuario: `messagePageSize` en `userPreferencesSync`.

## Frontend — UI

- [x] Pager fijo (sticky) con selector de tamaño, rango visible, entrada de página
      editable, primera/anterior/siguiente/última.
- [x] CSS del pager (y `hidden` cuando no hay resultados).

## Verificación

- [x] `npx vitest run` → 288 passed.
- [x] `pytest -m "not e2e"` → 1010 passed.
- [x] `npm run build` → SPA publicado en `app/static`.

## Mensajes sin modelo conocido

- [x] `GET /api/messages/list` expone `has_missing_model` y acepta `model_id=__none__`
      para filtrar los mensajes cuya conversación no tiene `model_id`.
- [x] El selector de modelos añade la opción **«Sin modelo»** cuando procede.
- [x] La fila muestra `· Sin modelo` en lugar de omitir el modelo.
- [x] Tests: `tests/test_api_messages_list.py` (`has_missing_model`, filtro `__none__`) y
      `frontend/src/ui/history/HistoryLists.test.jsx`.

## Pendiente / seguimiento

- [ ] Revisión visual manual en navegador (claro y oscuro).
- [ ] Valorar si el tamaño de página se ofrece también cuando el filtro no tiene
      resultados (ahora el pager se oculta).
- [ ] **Mensajes huérfanos**: existen filas `messages` sin conversación (borradas antes de
      añadir las claves foráneas; quedan 37 en la BD real). Su `provider`/`model_id` vive en
      la conversación, así que hoy no se pueden mostrar con su origen. Valorar una limpieza
      o un backfill de origen si se quieren recuperar.
