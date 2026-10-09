Última modificación: 2026-10-09

# Checklist: Integración del proveedor NaN Builders

**Objetivo:** Añadir NaN Builders (`nan`) como proveedor de LLM, siguiendo la misma arquitectura que Ollama/Mancer/OpenAI/Abliteration (Protocol `LLMProvider`, Factory, params por proveedor, contrato de modelo y uso de contexto).

**Fecha de creación:** 2026-10-09

**Referencias:**
- **Docs:** [nan.builders/docs](https://nan.builders/docs), [Getting started](https://nan.builders/docs/getting-started), [Models](https://nan.builders/docs/models)
- **Base URL:** `https://api.nan.builders` (la API expone `/v1/...`; se guarda la base sin `/v1`, coherente con OpenAI/Abliteration)
- **Autenticación:** `Authorization: Bearer sk-...` (personal y no transferible; requiere ser miembro de la comunidad NaN)
- **Chat:** `POST /v1/chat/completions` — `model`, `messages`, `stream`, `max_tokens`, `temperature`, `top_p`, `stop`, `presence_penalty`, `frequency_penalty`, `reasoning_effort`
- **Listar modelos:** `GET /v1/models` — `data[]` con `id`. No devuelve `context_length`; se enriquece con catálogo conocido.
- **Reasoning:** `reasoning_effort` (request) y `reasoning_content` (response, separado del `content`). Valores por modelo (ver tabla).

---

## 1. Configuración

- [x] **1.1** En `app/config.py`: `nan_api_key` (`NAN_API_KEY`) y `nan_base_url` (`NAN_BASE_URL`, default `https://api.nan.builders`).
- [x] **1.2** Añadir `NAN_API_KEY` y `NAN_BASE_URL` a `ENV_VARS_TO_SYNC`.
- [x] **1.3** Actualizar `.env.example` (`NAN_API_KEY`, `NAN_BASE_URL`) y `DEFAULT_LLM_PROVIDER` (`... | nan`).

## 2. Proveedor: interfaz y clase

- [x] **2.1** Crear `app/providers/nan.py` con `NanProvider` que implemente el Protocol `LLMProvider`:
  - `provider_name` → `"nan"`.
  - `list_models()` → `GET {base}/v1/models`; enriquece con `NAN_KNOWN_MODELS` (context_length + display_name). **No añade modelos que la API no liste** (a diferencia de Abliteration): `/v1/models` es la fuente de verdad y el catálogo puede incluir modelos no accesibles (glm5.3 requiere tier premium).
  - `chat()` → `POST {base}/v1/chat/completions` con `stream: false`.
  - `chat_stream()` → mismo endpoint con `stream: true`; lee SSE; **ignora `delta.reasoning_content`** y solo expone `delta.content`; normaliza `usage` en el chunk `done`.
  - `show_model()` → `GET {base}/v1/models/{id}`; si no responde 200, devuelve el catálogo conocido. Habilita la capacidad `show_model`.
  - `validate_connection()` → `list_models()`.
- [x] **2.2** Manejo de errores HTTP con `error.message`. Nota: NaN devuelve `401` tanto por key inválida como por modelo no incluido en el tier ("does not have access to the requested model"); el mensaje se propaga tal cual para no confundir al usuario.

## 3. Parámetros, presets y contrato

- [x] **3.1** En `config/provider_params.json` añadir `"nan"`: `temperature`, `top_p`, `max_tokens`, `stop_sequences` (→ `stop`), `presence_penalty`, `frequency_penalty`.
- [x] **3.2** Crear `config/nan.json` con presets por modelo (`context_length.max`, `max_tokens`, `tags`).
- [x] **3.3** Crear `config/model_overlays/nan.json` con `capabilities.thinking` y el param `think` (→ `reasoning_effort`) por modelo.

### Contrato de reasoning por modelo (según docs NaN)

| Modelo | `reasoning_effort` | kind | can_disable | default |
|---|---|---|---|---|
| `glm5.3`, `glm5.3-flash` | `low·medium·high·max` | levels | no | high |
| `deepseek-v4-flash` | aceptado, sin efecto | boolean | no | medium |
| `qwen3.8-flash`, `mimo-v2.6-flash` | aceptado, profundidad no ajustable | boolean | no | medium |
| `gemma4`, `qwen3.6` | `none·minimal·low·medium·high·max` | levels | sí | medium |

## 4. Factory e integración

- [x] **4.1** Registrar `"nan"` en `ProviderFactory.get_provider()`.
- [x] **4.2** `list_available_providers()` incluye `nan` solo si `settings.nan_api_key`.
- [x] **4.3** `parse_model_id()` acepta el prefijo `nan` (`nan:deepseek-v4-flash`).
- [x] **4.4** Actualizar mensaje de error "Proveedores disponibles".
- [x] **4.5** Documentar `NanProvider` en `app/providers/__init__.py` y `app/providers/base.py`.
- [x] **4.6** Los endpoints de `api_models.py` son genéricos por `provider_name`: sin cambios.

## 5. Tests

- [x] **5.1** `tests/test_providers.py`: `TestNanProvider` (provider_name, base_url default, missing key, override, protocol, list_models enriquece/no inventa, chat, chat 401, chat_stream ignora reasoning_content, show_model, validate).
- [x] **5.2** `TestProviderFactory`: `get_nan_provider`, `list_available_providers_with_nan`, `parse_model_id_nan_prefix`; actualizados los tests de listado para contemplar `nan`.
- [x] **5.3** `tests/test_model_contract.py`: overlay NaN (glm niveles, deepseek coacciona false, gemma4 desactivable).
- [x] **5.4** `tests/test_capabilities.py`: `nan` tiene `show_model`.
- [x] **5.5** `tests/test_api_models.py`: params y presets de `nan`.
- [x] **5.6** `tests/test_config.py`: `NAN_API_KEY`/`NAN_BASE_URL` en `ENV_VARS_TO_SYNC`.
- [x] **5.7** `tests/conftest.py`: fixture `nan_available` (skip sin key).
- [x] **5.8** `tests/test_e2e_api.py`: modelos, validate, params, capabilities, context-length y `list_providers`.

## 6. Documentación y cierre

- [x] **6.1** `.env.example`, `TECHNICAL.md` (adaptadores, variables, proveedores remotos) y este checklist.
- [ ] **6.2** Frontend: el selector de proveedor es genérico (`GET /api/providers`); verificar en UI que aparece `nan` y se pueden listar/enviar modelos. `frontend/src/app/imagesPanel.test.js` fija `["ollama","mancer"]` con un mock, no depende del backend.
- [ ] **6.3** Revisión final: linter y `make test` (pytest + vitest sin e2e).

## Resumen de archivos tocados

| Archivo | Acción |
|---|---|
| `app/config.py` | `nan_api_key`/`nan_base_url` + `ENV_VARS_TO_SYNC` |
| `app/providers/nan.py` | Nueva clase `NanProvider` |
| `app/providers/factory.py` | Registro, listado, `parse_model_id`, mensaje |
| `app/providers/__init__.py`, `app/providers/base.py` | Documentación |
| `config/provider_params.json` | Entrada `"nan"` |
| `config/nan.json` | Presets por modelo |
| `config/model_overlays/nan.json` | Thinking / `reasoning_effort` |
| `tests/*` | Provider, factory, contrato, capabilities, api, config, e2e, conftest |
| `.env.example`, `TECHNICAL.md` | Variables y arquitectura |
