import { useEffect } from "react";
import { LayoutEffects } from "./ui/layout/LayoutEffects.jsx";
import { onAppClick, onAppChange, onAppKeyDown, onAppPointerDown, onAppPointerMove, onAppPointerUp } from "./ui/layout/shellEvents.js";
import { ConversationsList } from "./ui/history/HistoryLists.jsx";
import { MessagesPane, ReadingModeOverlay } from "./ui/messages/MessagesPane.jsx";
import { GalleryPanelBody } from "./ui/gallery/GalleryPanelBody.jsx";
import { QueuePanelBody } from "./ui/queue/QueuePanelBody.jsx";
import { RulesList } from "./ui/rules/RulesList.jsx";
import { RuleEditModal } from "./ui/rules/RuleEditModal.jsx";
import { bootApp } from "./app/boot.js";
import { StoreDomSync } from "./ui/layout/StoreDomSync.jsx";
import { PrefPercentValue, PrefDebugLogValue } from "./ui/layout/PreferenceValues.jsx";
import { AuthGate } from "./ui/auth/AuthGate.jsx";
import { AuthStatusBar } from "./ui/auth/AuthStatusBar.jsx";
import { authStore } from "./store/auth.js";

export default function App() {
  useEffect(() => {
    let booted = false;
    const tryBoot = () => {
      if (booted) return;
      if (!authStore.get().user) return;
      booted = true;
      bootApp();
    };
    const unsub = authStore.subscribe(tryBoot);
    tryBoot();
    return unsub;
  }, []);
  return (
    <AuthGate>
    <>
    <LayoutEffects />
    <StoreDomSync />
    <div id="app" className="app-shell" onClick={onAppClick} onChange={onAppChange} onKeyDown={onAppKeyDown} onPointerDown={onAppPointerDown} onPointerMove={onAppPointerMove} onPointerUp={onAppPointerUp} onPointerCancel={onAppPointerUp}>
        <aside className="column-left sidebar-column" id="column-left" aria-label="Conversaciones">
          <div className="sidebar-header">
            <button type="button" id="btn-collapse-left" className="icon-btn sidebar-collapse-btn" title="Ocultar historial" aria-label="Ocultar historial" aria-controls="column-left" aria-expanded="true">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/><path d="M5 12h2"/></svg>
            </button>
          </div>
            <div className="sidebar-new-conversation-wrap">
            <div className="sidebar-create-stack">
              <button type="button" id="btn-new-chat" className="sidebar-add-btn" title="Nueva conversación" aria-label="Nueva conversación">
                <span className="sidebar-add-btn-text">Nueva conversación</span>
              </button>
              <button type="button" id="btn-prompt-generator" className="sidebar-add-btn" title="Generador de prompts" aria-label="Generador de prompts">
                <span className="sidebar-add-btn-text">Generador de prompts</span>
              </button>
            </div>
          </div>
          <div className="conversations-list-wrap">
            <ConversationsList />
          </div>
          <div id="sidebar-left-splitter" className="sidebar-column-splitter sidebar-column-splitter--right" role="separator" aria-orientation="vertical" aria-controls="column-left" aria-label="Redimensionar historial" aria-valuemin="180" aria-valuemax="420" aria-valuenow="188" tabIndex="0" title="Arrastra para cambiar el ancho. Doble clic restaura."></div>
        </aside>
        <main className="column-center chat-area main-pane">
          <header className="chat-panel-header">
            <div className="chat-title-row">
              <button type="button" id="btn-expand-left" className="icon-btn sidebar-expand-btn" title="Mostrar historial" aria-label="Mostrar historial" aria-controls="column-left" aria-expanded="false">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/><path d="M14 12h5"/></svg>
              </button>
              <div className="chat-session-identity">
                <input type="text" id="conversation-title" className="session-title conversation-title-input" placeholder="Chat de órdenes" aria-label="Título de la conversación" />
                <div id="conversation-image-filter-notice" className="chat-image-filter-notice-wrap" hidden aria-live="polite">
                  <button type="button" className="chat-image-filter-notice-open" title="Abrir la galería para cambiar los filtros">Filtros de imágenes activos</button>
                  <button type="button" id="conversation-image-filter-notice-dismiss" className="chat-image-filter-notice-dismiss" title="Quitar todos los filtros" aria-label="Quitar todos los filtros">×</button>
                </div>
              </div>
              <div className="chat-session-actions">
                <div className="center-panel-toggles" role="group" aria-label="Paneles centrales">
                  <button type="button" id="btn-center-chat" className="center-view-toggle" title="Mostrar u ocultar la conversación" aria-label="Conversación" aria-pressed="true" aria-controls="chat-column">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                    <span className="center-view-toggle-text">Conversación</span>
                  </button>
                  <button type="button" id="btn-image-gallery" className="center-view-toggle" title="Mostrar u ocultar la galería" aria-label="Galería de imágenes" aria-pressed="false" aria-controls="image-gallery-panel">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
                    <span className="center-view-toggle-text">Galería</span>
                  </button>
                  <button type="button" id="btn-image-queue" className="center-view-toggle" title="Mostrar u ocultar la cola de imágenes" aria-label="Cola de imágenes" aria-pressed="false" aria-controls="image-queue-panel">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                    <span className="center-view-toggle-text">Cola</span>
                  </button>
                </div>
                <button type="button" id="btn-clear-memory" className="icon-btn icon-btn-danger chat-delete-btn" title="Borrar conversación" aria-label="Borrar conversación">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                </button>
              </div>
            </div>
          </header>
          <p id="center-panels-empty" className="center-panels-empty" hidden>Activa Conversación, Galería o Cola para mostrar un panel.</p>
          <section className="chat-column" id="chat-column">
            <div className="chat-stream-wrap">
              <div className="chat-stream-view-controls chat-font-size-corner font-size-controls" role="group" aria-label="Vista del chat">
                <button type="button" id="btn-chat-fullscreen" className="icon-btn font-size-btn" title="Pantalla completa" aria-label="Pantalla completa" aria-pressed="false">
                  <svg className="chat-fs-icon-enter" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M16 3h3a2 2 0 0 1 2 2v3"/><path d="M8 21H5a2 2 0 0 1-2-2v-3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>
                  <svg className="chat-fs-icon-exit" hidden xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M16 3v3a2 2 0 0 0 2 2h3"/><path d="M8 21v-3a2 2 0 0 0-2-2H3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/></svg>
                </button>
                <button type="button" id="btn-font-size-decrease" className="icon-btn font-size-btn" title="Reducir tamaño" aria-label="Reducir tamaño"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
                <button type="button" id="btn-font-size-increase" className="icon-btn font-size-btn" title="Aumentar tamaño" aria-label="Aumentar tamaño"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
                <button type="button" id="btn-collapse-all-messages" className="icon-btn font-size-btn" title="Colapsar todos los mensajes" aria-label="Colapsar todos los mensajes"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 14 12 6 20 14"/><polyline points="4 20 12 12 20 20"/></svg></button>
              </div>
              <MessagesPane />
              <div className="chat-scroll-nav" id="chat-scroll-nav" aria-hidden="true">
                <button type="button" id="btn-scroll-msg-up" className="chat-scroll-nav-btn" title="Ir al inicio del primer mensaje visible" aria-label="Ir al inicio del primer mensaje visible">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="6 15 12 9 18 15"/></svg>
                </button>
                <button type="button" id="btn-scroll-msg-down" className="chat-scroll-nav-btn" title="Ir al final del último mensaje visible" aria-label="Ir al final del último mensaje visible">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>
                </button>
              </div>
              <button type="button" id="btn-expand-composer" className="icon-btn composer-expand-btn" title="Mostrar cuadro de mensaje" aria-label="Mostrar cuadro de mensaje" aria-controls="composer-panel" aria-expanded="false" hidden>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 14h18"/><path d="M12 9v3"/><path d="M9.5 10.5L12 8l2.5 2.5"/></svg>
                <span className="composer-expand-label">Escribir</span>
              </button>
            </div>
            <div className="input-area composer-panel" id="composer-panel">
              <div className="composer-top-row instruction-once-row">
                <input type="text" id="instruction-override" className="inline-input instruction-input" placeholder="Instrucción temporal (opcional)" aria-label="Instrucción opcional" />
                <button type="button" id="btn-collapse-composer" className="icon-btn composer-collapse-btn" title="Ocultar cuadro de mensaje" aria-label="Ocultar cuadro de mensaje" aria-controls="composer-panel" aria-expanded="true">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 14h18"/><path d="M12 18v-3"/><path d="M9.5 16.5L12 19l2.5-2.5"/></svg>
                </button>
              </div>
              <div className="composer-separator"></div>
              <div className="composer-model-row" id="composer-model-row" hidden>
                <label className="composer-think-label" id="composer-think-wrap" hidden>
                  <span>Thinking</span>
                  <select id="param-think" className="param-control composer-think-select" data-control-id="think" aria-label="Esfuerzo de razonamiento" disabled>
                  </select>
                </label>
                <div className="composer-recipes" id="composer-recipes" hidden role="group" aria-label="Recetas del modelo"></div>
              </div>
              <div className="composer-main-row send-row">
                <textarea id="message-input" className="composer-textarea" rows="2" placeholder="Escribe un comando o envía un mensaje al modelo..." aria-label="Mensaje"></textarea>
                <div className="composer-actions send-row-buttons">
                  <button type="button" id="btn-generate-prompt" className="send-button composer-generate-prompt-btn" title="Generar prompt" aria-label="Generar prompt" hidden><span className="composer-generate-prompt-icon" aria-hidden="true"></span></button>
                  <button type="button" id="btn-send" className="send-button composer-send-btn" title="Enviar" aria-label="Enviar mensaje" data-composer-action="send"><span className="composer-send-icon" aria-hidden="true"></span></button>
                </div>
              </div>
            </div>
          </section>
          <div id="center-panels-splitter" className="center-panels-splitter" hidden role="separator" aria-orientation="horizontal" aria-label="Redimensionar conversación y galería" aria-valuemin="28" aria-valuemax="72" aria-valuenow="50" tabIndex="0"></div>
          <section className="image-gallery-panel" id="image-gallery-panel" hidden aria-label="Galería de imágenes generadas">
            <GalleryPanelBody />
          </section>
          <section className="image-queue-panel" id="image-queue-panel" hidden aria-label="Cola de imágenes">
            <QueuePanelBody />
          </section>
        </main>
        <aside className="column-right sidebar-column" id="column-right" aria-label="Reglas, ajustes y preferencias">
          <div id="sidebar-right-splitter" className="sidebar-column-splitter sidebar-column-splitter--left" role="separator" aria-orientation="vertical" aria-controls="column-right" aria-label="Redimensionar reglas y ajustes" aria-valuemin="260" aria-valuemax="480" aria-valuenow="284" tabIndex="0" title="Arrastra para cambiar el ancho. Doble clic restaura."></div>
          <div className="workspace-profile-bar" role="group" aria-label="Perfiles de configuración">
            <select id="workspace-profile-select" className="param-control workspace-profile-select" aria-label="Perfil">
              <option value="">Elegir perfil</option>
            </select>
            <button type="button" id="btn-workspace-profile-apply" className="icon-btn workspace-profile-icon-btn" title="Aplicar perfil" aria-label="Aplicar perfil">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
            </button>
            <button type="button" id="btn-workspace-profile-save" className="icon-btn workspace-profile-icon-btn" title="Guardar" aria-label="Guardar">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
            </button>
            <button type="button" id="btn-workspace-profile-save-as" className="icon-btn workspace-profile-icon-btn" title="Guardar como" aria-label="Guardar como">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
            <button type="button" id="btn-workspace-profile-delete" className="icon-btn workspace-profile-icon-btn" title="Eliminar perfil" aria-label="Eliminar perfil">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
          <div className="sidebar-side-layout">
            <div className="sidebar-tab-rail" role="tablist" aria-label="Panel lateral" aria-orientation="vertical">
              <button type="button" className="sidebar-tab is-active" role="tab" id="sidebar-tab-reglas" data-sidebar-tab="reglas" aria-controls="tab-reglas" aria-selected="true" tabIndex="0" title="Reglas" aria-label="Reglas">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
              </button>
              <button type="button" className="sidebar-tab" role="tab" id="sidebar-tab-parametros" data-sidebar-tab="parametros" aria-controls="tab-parametros" aria-selected="false" tabIndex="-1" title="Ajustes" aria-label="Ajustes">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
              </button>
              <button type="button" className="sidebar-tab" role="tab" id="sidebar-tab-imagenes" data-sidebar-tab="imagenes" aria-controls="tab-imagenes" aria-selected="false" tabIndex="-1" title="Imágenes" aria-label="Imágenes">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              </button>
              <button type="button" className="sidebar-tab" role="tab" id="sidebar-tab-preferencias" data-sidebar-tab="preferencias" aria-controls="tab-preferencias" aria-selected="false" tabIndex="-1" title="Preferencias" aria-label="Preferencias">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
              </button>
            </div>
            <div className="sidebar-tab-panels">
            <div className="sidebar-tab-panel is-active" id="tab-reglas" role="tabpanel" data-sidebar-panel="reglas" aria-labelledby="sidebar-tab-reglas">
                <div className="rules-tab-scroll panel-scroll">
                  <p className="panel-hint">Se envían como un solo mensaje system, concatenadas con espacio.</p>
                  <section className="panel-section rules-panel" aria-labelledby="rules-active-heading">
                    <h3 id="rules-active-heading" className="panel-section-title">Activas</h3>
                    <div id="rules-list">
                    <RulesList scope="chat" />
                    </div>
                  </section>
                  <section className="panel-section" aria-labelledby="rules-library-heading">
                    <h3 id="rules-library-heading" className="panel-section-title">Añadir existente</h3>
                    <div className="rules-add-existing">
                      <select id="rule-library-select" className="rule-library-select" aria-label="Seleccionar regla de la biblioteca">
                        <option value="">Elegir regla</option>
                      </select>
                      <button type="button" id="btn-add-library-rule" className="btn btn-secondary btn-small">Añadir</button>
                    </div>
                  </section>
                  <section className="panel-section" id="rules-add-block" aria-labelledby="rules-create-heading">
                    <h3 id="rules-create-heading" className="panel-section-title">Crear nueva</h3>
                    <div className="rules-create-block">
                      <input type="text" id="rule-new-title" className="rule-new-title" placeholder="Título" aria-label="Título" />
                      <textarea id="rule-new-input" rows="2" placeholder="Contenido..." aria-label="Contenido"></textarea>
                      <button type="button" id="btn-add-rule" className="btn btn-secondary btn-small">Crear y añadir</button>
                    </div>
                  </section>
                </div>
            </div>
            <div className="sidebar-tab-panel" id="tab-parametros" role="tabpanel" data-sidebar-panel="parametros" aria-labelledby="sidebar-tab-parametros" hidden>
                  <section className="settings-model-pin" id="settings-model-pin" aria-labelledby="settings-model-heading">
                    <header className="settings-model-pin-header">
                      <h3 id="settings-model-heading" className="settings-model-pin-title">Modelo</h3>
                      <p className="settings-model-pin-caption">Proveedor y modelo activos</p>
                    </header>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="provider-select">Proveedor</label>
                          <select id="provider-select" className="param-control selector-control select-native" aria-label="Proveedor"></select>
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label param-help-trigger" htmlFor="model-select-input" data-control-id="model" title="Mantén el cursor 2 s para ver ayuda">Modelo</label>
                          <div className="model-select-wrap">
                            <input type="text" id="model-select-input" className="model-select-input param-control" autoComplete="off" placeholder="Escribir para filtrar..." aria-label="Modelo (escribir para filtrar)" aria-autocomplete="list" aria-expanded="false" aria-controls="model-select-list" />
                            <select id="model-select" className="model-select-native" aria-hidden="true" tabIndex="-1"></select>
                            <ul id="model-select-list" className="model-select-list" role="listbox" aria-hidden="true"></ul>
                          </div>
                          <div id="settings-model-capabilities" className="model-capability-chips" hidden role="list" aria-label="Capacidades del modelo"></div>
                        </div>
                  </section>
                  <div className="accordion-list sidebar-accordion sidebar-accordion-params">
                    <div className="accordion-section param-group is-open" data-accordion-section="params-presets">
                      <button type="button" className="accordion-header" aria-expanded="true" aria-controls="accordion-params-presets" id="accordion-params-presets-btn">
                        <div>
                          <span className="accordion-title">Presets</span>
                          <span className="accordion-caption">Recetas del modelo y los parámetros que cambian</span>
                        </div>
                        <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                      </button>
                      <div className="accordion-content" id="accordion-params-presets" role="region" aria-labelledby="accordion-params-presets-btn">
                        <p id="settings-presets-empty" className="param-note settings-presets-empty">Este modelo no tiene recetas.</p>
                        <div className="settings-presets-controls" id="settings-presets-controls" hidden>
                          <label className="composer-think-label" id="settings-think-wrap" hidden>
                            <span>Razonamiento</span>
                            <select id="settings-think" className="param-control composer-think-select" aria-label="Esfuerzo de razonamiento" disabled></select>
                          </label>
                          <div className="composer-recipes" id="settings-recipes" hidden role="group" aria-label="Recetas del modelo"></div>
                        </div>
                        <div id="settings-recipe-params" className="settings-recipe-params" hidden></div>
                      </div>
                    </div>
                    <div className="accordion-section param-group" data-accordion-section="params-contexto">
                      <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-params-contexto" id="accordion-params-contexto-btn">
                        <div>
                          <span className="accordion-title">Contexto</span>
                          <span className="accordion-caption">Ventana, truncado e historial del prompt</span>
                        </div>
                        <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                      </button>
                      <div className="accordion-content" id="accordion-params-contexto" role="region" aria-labelledby="accordion-params-contexto-btn">
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-truncation">Truncado del input</label>
                          <select id="param-truncation" className="param-control control-disabled" disabled data-control-id="truncation">
                            <option value="disabled">Desactivado (fallar si excede)</option>
                            <option value="auto">Auto (recortar al inicio)</option>
                          </select>
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-num-ctx">Ventana de contexto (num_ctx)</label>
                          <input type="number" id="param-num-ctx" className="param-control control-disabled" disabled min="512" max="131072" placeholder="2048" data-control-id="num_ctx" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="history-turns-input">Mensajes de historial</label>
                          <input type="number" id="history-turns-input" className="param-control history-turns-input" min="0" max="100" defaultValue="5" aria-label="Mensajes de historial a enviar en cada prompt" />
                          <p className="param-note">Cuántos mensajes anteriores se incluyen en cada prompt.</p>
                        </div>
                      </div>
                    </div>
                    <div className="accordion-section param-group" data-accordion-section="params-instruccion">
                      <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-params-instruccion" id="accordion-params-instruccion-btn">
                        <div>
                          <span className="accordion-title">Instrucción</span>
                          <span className="accordion-caption">System extra del proveedor</span>
                        </div>
                        <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                      </button>
                      <div className="accordion-content" id="accordion-params-instruccion" role="region" aria-labelledby="accordion-params-instruccion-btn">
                        <div className="sidebar-option param-option">
                          <label className="param-label">Instrucción de sistema</label>
                          <p className="param-note">Usa el cuadro "Instrucciones para todos los mensajes" en Reglas. Este control se activará cuando se soporte por proveedor.</p>
                          <textarea id="param-system-extra" className="param-control control-disabled" disabled rows="2" placeholder="Instrucción adicional (desactivado)" data-control-id="system_instruction"></textarea>
                        </div>
                      </div>
                    </div>
                    <div className="accordion-section param-group" data-accordion-section="params-longitud">
                      <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-params-longitud" id="accordion-params-longitud-btn">
                        <div>
                          <span className="accordion-title">Longitud y paradas</span>
                          <span className="accordion-caption">Tope de tokens y cortes</span>
                        </div>
                        <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                      </button>
                      <div className="accordion-content" id="accordion-params-longitud" role="region" aria-labelledby="accordion-params-longitud-btn">
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-max-tokens">Límite de tokens de salida</label>
                          <input type="number" id="param-max-tokens" className="param-control control-disabled" disabled min="1" max="128000" placeholder="ej. 512" data-control-id="max_tokens" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-stop-sequences">Secuencias de parada</label>
                          <input type="text" id="param-stop-sequences" className="param-control control-disabled" disabled placeholder="ej. \n\n o \nUsuario:" data-control-id="stop_sequences" />
                        </div>
                      </div>
                    </div>
                    <div className="accordion-section param-group" data-accordion-section="params-aleatoriedad">
                      <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-params-aleatoriedad" id="accordion-params-aleatoriedad-btn">
                        <div>
                          <span className="accordion-title">Aleatoriedad y diversidad</span>
                          <span className="accordion-caption">Temperatura, top-p y semilla</span>
                        </div>
                        <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                      </button>
                      <div className="accordion-content" id="accordion-params-aleatoriedad" role="region" aria-labelledby="accordion-params-aleatoriedad-btn">
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-temperature">Temperatura</label>
                          <input type="number" id="param-temperature" className="param-control control-disabled" disabled min="0" max="2" step="0.1" placeholder="0.8" data-control-id="temperature" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-top-p">Top-p (nucleus)</label>
                          <input type="number" id="param-top-p" className="param-control control-disabled" disabled min="0" max="1" step="0.05" placeholder="0.9" data-control-id="top_p" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-top-k">Top-k</label>
                          <input type="number" id="param-top-k" className="param-control control-disabled" disabled min="0" max="500" placeholder="40" data-control-id="top_k" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-min-p">Min-p (avanzado)</label>
                          <input type="number" id="param-min-p" className="param-control control-disabled" disabled min="0" max="1" step="0.01" placeholder="0" data-control-id="min_p" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-seed">Semilla</label>
                          <input type="number" id="param-seed" className="param-control control-disabled" disabled placeholder="0 = aleatorio" data-control-id="seed" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-presence-penalty">Presence penalty</label>
                          <input type="number" id="param-presence-penalty" className="param-control control-disabled" disabled min="-2" max="2" step="0.1" placeholder="0" data-control-id="presence_penalty" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-frequency-penalty">Frequency penalty</label>
                          <input type="number" id="param-frequency-penalty" className="param-control control-disabled" disabled min="-2" max="2" step="0.1" placeholder="0" data-control-id="frequency_penalty" />
                        </div>
                      </div>
                    </div>
                    <div className="accordion-section param-group" data-accordion-section="params-seguridad">
                      <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-params-seguridad" id="accordion-params-seguridad-btn">
                        <div>
                          <span className="accordion-title">Seguridad y formato</span>
                          <span className="accordion-caption">JSON y filtros de contenido</span>
                        </div>
                        <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                      </button>
                      <div className="accordion-content" id="accordion-params-seguridad" role="region" aria-labelledby="accordion-params-seguridad-btn">
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-response-format">Formato de salida</label>
                          <select id="param-response-format" className="param-control control-disabled" disabled data-control-id="response_format">
                            <option value="text">Texto</option>
                            <option value="json_object">JSON objeto</option>
                            <option value="json_schema">JSON Schema</option>
                          </select>
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="param-safety-mode">Modo seguridad</label>
                          <select id="param-safety-mode" className="param-control control-disabled" disabled data-control-id="safety_mode">
                            <option value="default">Por defecto</option>
                            <option value="contextual">Contextual</option>
                            <option value="off">Desactivado</option>
                          </select>
                        </div>
                      </div>
                    </div>
                    <div className="accordion-section param-group" data-accordion-section="params-payload">
                      <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-params-payload" id="accordion-params-payload-btn">
                        <div>
                          <span className="accordion-title" id="params-payload-heading">Payload</span>
                          <span className="accordion-caption">Qué se enviará en la petición</span>
                        </div>
                        <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                      </button>
                      <div className="accordion-content panel-section-payload" id="accordion-params-payload" role="region" aria-labelledby="accordion-params-payload-btn">
                        <div className="badge-row params-to-send-container" id="params-to-send-container" aria-live="polite"></div>
                      </div>
                    </div>
                  </div>
            </div>
            <div className="sidebar-tab-panel" id="tab-imagenes" role="tabpanel" data-sidebar-panel="imagenes" aria-labelledby="sidebar-tab-imagenes" hidden>
                <div className="accordion-list sidebar-accordion sidebar-accordion-images">
                  <div className="accordion-section is-open" data-accordion-section="images-activation">
                    <button type="button" className="accordion-header" aria-expanded="true" aria-controls="accordion-images-activation" id="accordion-images-activation-btn">
                      <div>
                        <span className="accordion-title" id="images-activation-heading">Activación</span>
                        <span className="accordion-caption">Ilustrar tras el relato</span>
                      </div>
                      <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div className="accordion-content" id="accordion-images-activation" role="region" aria-labelledby="accordion-images-activation-btn">
                      <label className="pref-row fluent-toggle-row" title="Generar imágenes tras respuestas de relato o roleplay">
                        <span className="pref-row-copy">
                          <span className="pref-row-label">Activar ilustración</span>
                          <span className="pref-row-hint">Tras cada respuesta de relato</span>
                        </span>
                        <input type="checkbox" id="images-enabled" className="fluent-switch-input" aria-label="Activar ilustración" />
                        <span className="fluent-switch-track" aria-hidden="true"><span className="fluent-switch-thumb"></span></span>
                      </label>
                    </div>
                  </div>
                  <div className="accordion-section" data-accordion-section="images-planner">
                    <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-images-planner" id="accordion-images-planner-btn">
                      <div>
                        <span className="accordion-title" id="images-planner-heading">Planificador LLM</span>
                        <span className="accordion-caption">Cómo se eligen y describen las escenas</span>
                      </div>
                      <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div className="accordion-content" id="accordion-images-planner" role="region" aria-labelledby="accordion-images-planner-btn">
                      <div className="sidebar-option param-option">
                        <label className="param-label" htmlFor="images-scene-selection-strategy">Selección de escenas</label>
                        <select id="images-scene-selection-strategy" className="param-control" aria-label="Estrategia de selección de escenas" defaultValue="distributed">
                          <option value="distributed">Distribuida (huecos)</option>
                          <option value="llm_erotic_story">Narrativa erótica (LLM)</option>
                          <option value="llm_pornographic_peaks">Picos pornográficos (LLM)</option>
                        </select>
                        <p className="param-note">Cómo se eligen los párrafos a ilustrar. Se pueden añadir más estrategias.</p>
                      </div>
                      <label className="pref-row fluent-toggle-row" title="Usar el mismo proveedor, modelo, reglas del chat y parámetros. Las reglas del planificador se aplican igual.">
                        <span className="pref-row-copy">
                          <span className="pref-row-label">Usar configuración del chat</span>
                          <span className="pref-row-hint">Proveedor, modelo y recetas de Ajustes</span>
                        </span>
                        <input type="checkbox" id="images-use-chat-config" className="fluent-switch-input" aria-label="Usar configuración del chat" />
                        <span className="fluent-switch-track" aria-hidden="true"><span className="fluent-switch-thumb"></span></span>
                      </label>
                      <label className="pref-row fluent-toggle-row" title="Los prompts del lote y de las imágenes ya generadas comparten identidad: edad, vestuario y aspecto. Varía pose e instante. El relato manda si cambia ropa o lugar.">
                        <span className="pref-row-copy">
                          <span className="pref-row-label">Consistencia</span>
                          <span className="pref-row-hint">Misma identidad entre imágenes del mensaje</span>
                        </span>
                        <input type="checkbox" id="images-visual-consistency" className="fluent-switch-input" aria-label="Consistencia visual entre imágenes" defaultChecked />
                        <span className="fluent-switch-track" aria-hidden="true"><span className="fluent-switch-thumb"></span></span>
                      </label>
                      <div className="sidebar-option param-option" data-images-chat-config-control>
                        <label className="param-label" htmlFor="images-prompt-provider">Proveedor de prompts</label>
                        <select id="images-prompt-provider" className="param-control" aria-label="Proveedor para prompts de imagen"></select>
                      </div>
                      <div className="sidebar-option param-option" data-images-chat-config-control>
                        <label className="param-label" htmlFor="images-prompt-model">Modelo de prompts</label>
                        <select id="images-prompt-model" className="param-control" aria-label="Modelo para prompts de imagen"></select>
                      </div>
                      <div className="planner-presets" id="planner-presets" data-images-chat-config-control>
                        <p className="param-label">Presets</p>
                        <p id="planner-presets-empty" className="param-note">Este modelo no tiene recetas.</p>
                        <p id="planner-presets-chat-hint" className="param-note" hidden>Con la configuración del chat, las recetas se eligen en Ajustes.</p>
                        <div className="settings-presets-controls" id="planner-presets-controls" hidden>
                          <label className="composer-think-label" id="planner-think-wrap" hidden>
                            <span>Razonamiento</span>
                            <select id="planner-think" className="param-control composer-think-select" aria-label="Esfuerzo de razonamiento del planificador" disabled></select>
                          </label>
                          <div className="composer-recipes" id="planner-recipes" hidden role="group" aria-label="Recetas del planificador"></div>
                        </div>
                        <div id="planner-recipe-params" className="settings-recipe-params" hidden></div>
                      </div>
                    </div>
                  </div>
                  <div className="accordion-section" data-accordion-section="images-planner-rules">
                    <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-images-planner-rules" id="accordion-images-planner-rules-btn">
                      <div>
                        <span className="accordion-title" id="images-planner-rules-heading">Reglas del planificador</span>
                        <span className="accordion-caption">Se concatenan al system</span>
                      </div>
                      <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div className="accordion-content planner-rules-panel" id="accordion-images-planner-rules" role="region" aria-labelledby="accordion-images-planner-rules-btn">
                      <div className="workspace-profile-bar planner-rule-preset-bar" role="group" aria-label="Presets de reglas del planificador">
                        <select id="planner-rule-preset-select" className="param-control workspace-profile-select" aria-label="Preset de reglas">
                          <option value="">Elegir preset</option>
                        </select>
                        <button type="button" id="btn-planner-rule-preset-apply" className="icon-btn workspace-profile-icon-btn" title="Aplicar preset" aria-label="Aplicar preset">
                          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                        </button>
                        <button type="button" id="btn-planner-rule-preset-save" className="icon-btn workspace-profile-icon-btn" title="Guardar" aria-label="Guardar preset">
                          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                        </button>
                        <button type="button" id="btn-planner-rule-preset-save-as" className="icon-btn workspace-profile-icon-btn" title="Guardar como" aria-label="Guardar preset como">
                          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                        </button>
                        <button type="button" id="btn-planner-rule-preset-delete" className="icon-btn workspace-profile-icon-btn" title="Eliminar preset" aria-label="Eliminar preset">
                          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                      </div>
                      {/* id="planner-rules-list" */}
                      <div id="planner-rules-list">
                      <RulesList scope="planner" />
                      </div>
                      <div className="rules-add-existing">
                        <select id="planner-rule-library-select" className="rule-library-select" aria-label="Seleccionar regla del planificador">
                          <option value="">Elegir regla</option>
                        </select>
                        <button type="button" id="btn-add-planner-library-rule" className="btn btn-secondary btn-small">Añadir</button>
                      </div>
                      <div className="rules-create-block">
                        <input type="text" id="planner-rule-new-title" className="rule-new-title" placeholder="Título" aria-label="Título de la regla del planificador" />
                        <textarea id="planner-rule-new-input" rows="2" placeholder="Contenido..." aria-label="Contenido de la regla del planificador"></textarea>
                        <button type="button" id="btn-add-planner-rule" className="btn btn-secondary btn-small">Crear y añadir</button>
                      </div>
                    </div>
                  </div>
                  <div className="accordion-section" data-accordion-section="images-limits">
                    <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-images-limits" id="accordion-images-limits-btn">
                      <div>
                        <span className="accordion-title" id="images-limits-heading">Límites</span>
                        <span className="accordion-caption">Cuántas y en qué lote</span>
                      </div>
                      <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div className="accordion-content" id="accordion-images-limits" role="region" aria-labelledby="accordion-images-limits-btn">
                      <div className="sidebar-option param-option">
                        <label className="param-label" htmlFor="images-per-response">Imágenes por respuesta</label>
                        <input type="number" id="images-per-response" className="param-control" min="1" defaultValue="2" />
                      </div>
                      <div className="sidebar-option param-option">
                        <label className="param-label" htmlFor="images-batch-size">Tamaño de lote</label>
                        <input type="number" id="images-batch-size" className="param-control" min="1" defaultValue="10" title="Si hay más imágenes que este tamaño, se planifican y generan por lotes" />
                      </div>
                      <div className="sidebar-option param-option">
                        <label className="param-label" htmlFor="images-retries">Reintentos</label>
                        <input type="number" id="images-retries" className="param-control" min="0" max="10" defaultValue="1" />
                      </div>
                    </div>
                  </div>
                  <div className="accordion-section" data-accordion-section="images-forge">
                    <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-images-forge" id="accordion-images-forge-btn">
                      <div>
                        <span className="accordion-title" id="images-forge-heading">Prompt Forge</span>
                        <span className="accordion-caption">Texto extra en cada generación</span>
                      </div>
                      <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div className="accordion-content" id="accordion-images-forge" role="region" aria-labelledby="accordion-images-forge-btn">
                      <div className="sidebar-option param-option">
                        <label className="param-label" htmlFor="images-prompt">Prompt</label>
                        <textarea id="images-prompt" className="param-control images-prompt-textarea" rows="3" maxLength="4000" placeholder="Estilo, calidad u otras indicaciones fijas" aria-label="Prompt adicional para Forge"></textarea>
                        <p className="param-note">Se concatena a cada escena. Vacío = solo el prompt del planificador.</p>
                      </div>
                    </div>
                  </div>
                  <div className="accordion-section" data-accordion-section="images-forge-params">
                    <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-images-forge-params" id="accordion-images-forge-params-btn">
                      <div>
                        <span className="accordion-title" id="images-forge-params-heading">Parámetros Forge</span>
                        <span className="accordion-caption">Pasos, tamaño y semilla</span>
                      </div>
                      <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div className="accordion-content" id="accordion-images-forge-params" role="region" aria-labelledby="accordion-images-forge-params-btn">
                      <div className="sidebar-option param-option">
                        <label className="param-label" htmlFor="images-forge-steps">Pasos</label>
                        <input type="number" id="images-forge-steps" className="param-control" min="1" max="150" step="1" placeholder="Del último gen" title="Pasos de muestreo en Forge" />
                      </div>
                      <div className="sidebar-option param-option">
                        <label className="param-label" htmlFor="images-forge-width">Ancho</label>
                        <input type="number" id="images-forge-width" className="param-control" min="64" max="4096" step="8" placeholder="Del último gen" title="Ancho de la imagen" />
                      </div>
                      <div className="sidebar-option param-option">
                        <label className="param-label" htmlFor="images-forge-height">Alto</label>
                        <input type="number" id="images-forge-height" className="param-control" min="64" max="4096" step="8" placeholder="Del último gen" title="Alto de la imagen" />
                      </div>
                      <div className="sidebar-option param-option">
                        <label className="param-label" htmlFor="images-forge-seed">Semilla</label>
                        <input type="number" id="images-forge-seed" className="param-control" step="1" placeholder="Del último gen" title="Semilla (-1 = aleatoria en Forge)" />
                      </div>
                      <div className="sidebar-option sidebar-actions">
                        <button type="button" id="btn-images-forge-reload-params" className="btn btn-secondary btn-small" title="Sustituye pasos, ancho, alto y semilla por los del último gen de Forge">
                          Recargar desde Forge
                        </button>
                      </div>
                      <p className="panel-hint">Vacío = no sobrescribir el último gen. Recargar vuelve a leer Forge.</p>
                    </div>
                  </div>
                  <div className="accordion-section" data-accordion-section="images-reactor">
                    <button type="button" className="accordion-header" aria-expanded="false" aria-controls="accordion-images-reactor" id="accordion-images-reactor-btn">
                      <div>
                        <span className="accordion-title" id="images-reactor-heading">ReActor</span>
                        <span className="accordion-caption">Face swap y acabado</span>
                      </div>
                      <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div className="accordion-content" id="accordion-images-reactor" role="region" aria-labelledby="accordion-images-reactor-btn">
                      <label className="pref-row fluent-toggle-row" title="Tras generar en Forge, aplica ReActor antes de guardar">
                        <span className="pref-row-copy">
                          <span className="pref-row-label">Aplicar face swap</span>
                          <span className="pref-row-hint">Después de cada generación</span>
                        </span>
                        <input type="checkbox" id="images-reactor-enabled" className="fluent-switch-input" aria-label="Aplicar face swap" />
                        <span className="fluent-switch-track" aria-hidden="true"><span className="fluent-switch-thumb"></span></span>
                      </label>
                      <section className="panel-field-group" id="reactor-group-gender" aria-labelledby="reactor-gender-heading">
                        <h4 id="reactor-gender-heading" className="panel-section-title">Género</h4>
                        <p className="panel-hint">Si activas Mujer u Hombre, se usa ese facemodel. Si no, la imagen fuente del .env.</p>
                        <label className="pref-row fluent-toggle-row" title="Aplicar facemodel solo a caras femeninas detectadas">
                          <span className="pref-row-copy">
                            <span className="pref-row-label">Mujer</span>
                            <span className="pref-row-hint">Solo caras detectadas como mujer</span>
                          </span>
                          <input type="checkbox" id="images-reactor-female-enabled" className="fluent-switch-input" aria-label="Facemodel mujer" />
                          <span className="fluent-switch-track" aria-hidden="true"><span className="fluent-switch-thumb"></span></span>
                        </label>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-female-face-model">Facemodel mujer</label>
                          <input type="text" id="images-reactor-female-face-model" className="param-control" maxLength="256" placeholder="p. ej. elena.safetensors" disabled title="Nombre del facemodel en Forge (models/reactor/faces)" />
                        </div>
                        <label className="pref-row fluent-toggle-row" title="Aplicar facemodel solo a caras masculinas detectadas">
                          <span className="pref-row-copy">
                            <span className="pref-row-label">Hombre</span>
                            <span className="pref-row-hint">Solo caras detectadas como hombre</span>
                          </span>
                          <input type="checkbox" id="images-reactor-male-enabled" className="fluent-switch-input" aria-label="Facemodel hombre" />
                          <span className="fluent-switch-track" aria-hidden="true"><span className="fluent-switch-thumb"></span></span>
                        </label>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-male-face-model">Facemodel hombre</label>
                          <input type="text" id="images-reactor-male-face-model" className="param-control" maxLength="256" placeholder="p. ej. john.safetensors" disabled title="Nombre del facemodel en Forge (models/reactor/faces)" />
                        </div>
                      </section>
                      <section className="panel-field-group" id="reactor-group-source" aria-labelledby="reactor-source-heading">
                        <h4 id="reactor-source-heading" className="panel-section-title">Origen</h4>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-model">Modelo swap</label>
                          <input type="text" id="images-reactor-model" className="param-control" maxLength="256" placeholder="Del .env" title="Modelo InsightFace, p. ej. inswapper_128.onnx" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-source-faces-index">Índices cara fuente</label>
                          <input type="text" id="images-reactor-source-faces-index" className="param-control" maxLength="64" placeholder="Del .env" title="Índices separados por coma en la imagen fuente" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-face-index">Índices cara destino</label>
                          <input type="text" id="images-reactor-face-index" className="param-control" maxLength="64" placeholder="Del .env" title="Índices separados por coma en la imagen generada" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-select-source">Origen fuente</label>
                          <input type="number" id="images-reactor-select-source" className="param-control" min="0" max="2" step="1" placeholder="Del .env" title="0=imagen, 1=facemodel, 2=carpeta" />
                          <p className="param-note">0 imagen, 1 facemodel, 2 carpeta.</p>
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-face-model">Facemodel genérico</label>
                          <input type="text" id="images-reactor-face-model" className="param-control" maxLength="256" placeholder="Del .env" title="Solo si origen fuente=1 y no usas Mujer/Hombre" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-source-folder">Carpeta fuente</label>
                          <input type="text" id="images-reactor-source-folder" className="param-control" maxLength="512" placeholder="Del .env" title="Solo si origen fuente=2" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-random-image">Imagen aleatoria</label>
                          <input type="number" id="images-reactor-random-image" className="param-control" min="0" max="1" step="1" placeholder="Del .env" title="1=elige al azar de la carpeta fuente" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-gender-source">Género fuente</label>
                          <input type="number" id="images-reactor-gender-source" className="param-control" min="0" max="2" step="1" placeholder="Del .env" title="0=any, 1=mujer, 2=hombre (modo imagen fuente)" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-gender-target">Género destino</label>
                          <input type="number" id="images-reactor-gender-target" className="param-control" min="0" max="2" step="1" placeholder="Del .env" title="0=any, 1=mujer, 2=hombre (modo imagen fuente)" />
                        </div>
                      </section>
                      <section className="panel-field-group" id="reactor-group-finish" aria-labelledby="reactor-finish-heading">
                        <h4 id="reactor-finish-heading" className="panel-section-title">Acabado</h4>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-upscaler">Upscaler</label>
                          <input type="text" id="images-reactor-upscaler" className="param-control" maxLength="256" placeholder="Del .env" title="None para desactivar upscale" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-scale">Escala upscale</label>
                          <input type="number" id="images-reactor-scale" className="param-control" min="0.1" max="8" step="0.1" placeholder="Del .env" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-upscale-visibility">Visibilidad upscale</label>
                          <input type="number" id="images-reactor-upscale-visibility" className="param-control" min="0" max="1" step="0.05" placeholder="Del .env" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-upscale-force">Forzar upscale</label>
                          <input type="number" id="images-reactor-upscale-force" className="param-control" min="0" max="1" step="1" placeholder="Del .env" title="1=upscale aunque no detecte cara" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-face-restorer">Restaurador</label>
                          <input type="text" id="images-reactor-face-restorer" className="param-control" maxLength="64" placeholder="Del .env" title="CodeFormer, GFPGAN o None" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-restorer-visibility">Visibilidad restaurador</label>
                          <input type="number" id="images-reactor-restorer-visibility" className="param-control" min="0" max="1" step="0.05" placeholder="Del .env" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-codeformer-weight">Peso CodeFormer</label>
                          <input type="number" id="images-reactor-codeformer-weight" className="param-control" min="0" max="1" step="0.05" placeholder="Del .env" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-restore-first">Restaurar primero</label>
                          <input type="number" id="images-reactor-restore-first" className="param-control" min="0" max="1" step="1" placeholder="Del .env" title="1 = restaurar antes del upscale" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-device">Dispositivo</label>
                          <input type="text" id="images-reactor-device" className="param-control" maxLength="32" placeholder="Del .env" title="CUDA o CPU" />
                        </div>
                        <div className="sidebar-option param-option">
                          <label className="param-label" htmlFor="images-reactor-mask-face">Máscara facial</label>
                          <input type="number" id="images-reactor-mask-face" className="param-control" min="0" max="1" step="1" placeholder="Del .env" title="1=máscara, 0=bbox" />
                        </div>
                      </section>
                    </div>
                  </div>
                </div>
            </div>
            <div className="sidebar-tab-panel" id="tab-preferencias" role="tabpanel" data-sidebar-panel="preferencias" aria-labelledby="sidebar-tab-preferencias" hidden>
                <div className="accordion-list sidebar-accordion sidebar-accordion-prefs">
                  <div className="accordion-section is-open" data-accordion-section="prefs-interfaz">
                    <button type="button" className="accordion-header" aria-expanded="true" aria-controls="accordion-prefs-interfaz" id="accordion-prefs-interfaz-btn">
                      <div>
                        <span className="accordion-title">Interfaz</span>
                        <span className="accordion-caption">Apariencia y comportamiento del chat</span>
                      </div>
                      <svg className="accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div className="accordion-content" id="accordion-prefs-interfaz" role="region" aria-labelledby="accordion-prefs-interfaz-btn">
                      <div className="pref-row">
                        <div className="pref-row-copy">
                          <span className="pref-row-label" id="pref-font-base-label">Texto base</span>
                          <span className="pref-row-hint">Tamaño de referencia de toda la interfaz</span>
                        </div>
                        <div className="pref-font-stepper" role="group" aria-labelledby="pref-font-base-label">
                          <button type="button" id="pref-font-base-decrease" className="icon-btn font-size-btn" title="Reducir tamaño de texto base" aria-label="Reducir tamaño de texto base">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                          <PrefPercentValue id="pref-font-base-value" field="uiBaseFontScale" />
                          <button type="button" id="pref-font-base-increase" className="icon-btn font-size-btn" title="Aumentar tamaño de texto base" aria-label="Aumentar tamaño de texto base">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                        </div>
                      </div>
                      <div className="pref-row">
                        <div className="pref-row-copy">
                          <span className="pref-row-label" id="pref-font-label">Texto de la conversación</span>
                          <span className="pref-row-hint">Ajuste del cuerpo de los mensajes respecto al tamaño base</span>
                        </div>
                        <div className="pref-font-stepper" role="group" aria-labelledby="pref-font-label">
                          <button type="button" id="pref-font-decrease" className="icon-btn font-size-btn" title="Reducir tamaño del texto" aria-label="Reducir tamaño del texto">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                          <PrefPercentValue id="pref-font-value" field="conversationFontRem" />
                          <button type="button" id="pref-font-increase" className="icon-btn font-size-btn" title="Aumentar tamaño del texto" aria-label="Aumentar tamaño del texto">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                        </div>
                      </div>
                      <div className="pref-row">
                        <div className="pref-row-copy">
                          <span className="pref-row-label" id="pref-font-left-label">Texto del panel izquierdo</span>
                          <span className="pref-row-hint">Ajuste del historial respecto al tamaño base</span>
                        </div>
                        <div className="pref-font-stepper" role="group" aria-labelledby="pref-font-left-label">
                          <button type="button" id="pref-font-left-decrease" className="icon-btn font-size-btn" title="Reducir texto del historial" aria-label="Reducir texto del panel izquierdo">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                          <PrefPercentValue id="pref-font-left-value" field="sidebarLeftFontScale" />
                          <button type="button" id="pref-font-left-increase" className="icon-btn font-size-btn" title="Aumentar texto del historial" aria-label="Aumentar texto del panel izquierdo">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                        </div>
                      </div>
                      <div className="pref-row">
                        <div className="pref-row-copy">
                          <span className="pref-row-label" id="pref-font-right-label">Texto del panel derecho</span>
                          <span className="pref-row-hint">Ajuste de reglas y parámetros respecto al tamaño base</span>
                        </div>
                        <div className="pref-font-stepper" role="group" aria-labelledby="pref-font-right-label">
                          <button type="button" id="pref-font-right-decrease" className="icon-btn font-size-btn" title="Reducir texto de reglas y ajustes" aria-label="Reducir texto del panel derecho">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                          <PrefPercentValue id="pref-font-right-value" field="sidebarRightFontScale" />
                          <button type="button" id="pref-font-right-increase" className="icon-btn font-size-btn" title="Aumentar texto de reglas y ajustes" aria-label="Aumentar texto del panel derecho">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                        </div>
                      </div>
                      <div className="pref-row">
                        <div className="pref-row-copy">
                          <span className="pref-row-label" id="pref-image-label">Imágenes de la conversación</span>
                          <span className="pref-row-hint">Tamaño de las ilustraciones en los mensajes</span>
                        </div>
                        <div className="pref-font-stepper" role="group" aria-labelledby="pref-image-label">
                          <button type="button" id="pref-image-decrease" className="icon-btn font-size-btn" title="Reducir tamaño de las ilustraciones" aria-label="Reducir tamaño de las ilustraciones">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                          <PrefPercentValue id="pref-image-value" field="imageSizeFactor" />
                          <button type="button" id="pref-image-increase" className="icon-btn font-size-btn" title="Aumentar tamaño de las ilustraciones" aria-label="Aumentar tamaño de las ilustraciones">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                        </div>
                      </div>
                      <div className="pref-row">
                        <div className="pref-row-copy">
                          <span className="pref-row-label" id="pref-debug-log-label">Historial de debug</span>
                          <span className="pref-row-hint">Entradas FIFO en Debug y Debug imágenes</span>
                        </div>
                        <div className="pref-font-stepper" role="group" aria-labelledby="pref-debug-log-label">
                          <button type="button" id="pref-debug-log-decrease" className="icon-btn font-size-btn" title="Reducir historial de debug" aria-label="Reducir historial de debug">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                          <PrefDebugLogValue id="pref-debug-log-value" />
                          <button type="button" id="pref-debug-log-increase" className="icon-btn font-size-btn" title="Aumentar historial de debug" aria-label="Aumentar historial de debug">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                          </button>
                        </div>
                      </div>
                      <label className="pref-row fluent-toggle-row" title="Fondo y paneles en modo oscuro">
                        <span className="pref-row-copy">
                          <span className="pref-row-label">Tema oscuro</span>
                          <span className="pref-row-hint">Fondo y paneles</span>
                        </span>
                        <input type="checkbox" id="dark-mode-toggle" className="fluent-switch-input" aria-label="Tema oscuro" />
                        <span className="fluent-switch-track" aria-hidden="true"><span className="fluent-switch-thumb"></span></span>
                      </label>
                      <label className="pref-row fluent-toggle-row" title="Interpretar Markdown en los mensajes del panel de conversación">
                        <span className="pref-row-copy">
                          <span className="pref-row-label">Markdown en conversación</span>
                          <span className="pref-row-hint">Títulos, negrita, listas y el resto del formato</span>
                        </span>
                        <input type="checkbox" id="render-markdown-toggle" className="fluent-switch-input" defaultChecked aria-label="Markdown en conversación" />
                        <span className="fluent-switch-track" aria-hidden="true"><span className="fluent-switch-thumb"></span></span>
                      </label>
                      <label className="pref-row fluent-toggle-row" title="Durante la generación, hacer scroll al último contenido">
                        <span className="pref-row-copy">
                          <span className="pref-row-label">Auto-scroll al generar</span>
                          <span className="pref-row-hint">Sigue el texto mientras responde el modelo</span>
                        </span>
                        <input type="checkbox" id="auto-scroll-during-generation" className="fluent-switch-input" defaultChecked aria-label="Auto-scroll al generar" />
                        <span className="fluent-switch-track" aria-hidden="true"><span className="fluent-switch-thumb"></span></span>
                      </label>
                      <div className="pref-row">
                        <div className="pref-row-copy">
                          <span className="pref-row-label">Mensajes</span>
                          <span className="pref-row-hint">Pliega el cuerpo de todas las respuestas</span>
                        </div>
                        <button type="button" id="pref-collapse-all-messages" className="btn btn-secondary btn-small">Colapsar</button>
                      </div>
                    </div>
                  </div>
                </div>
            </div>
            </div>
          </div>
          <div id="debug-dock" className="debug-dock sidebar-footer" aria-label="Paneles de debug">
            <section className="debug-accordion" data-debug-panel="chat" id="debug-accordion-chat">
              <h2 className="debug-accordion-heading">
                <button type="button" className="debug-accordion-toggle" id="debug-chat-toggle" aria-expanded="false" aria-controls="debug-chat-body">
                  <span>Debug</span>
                  <svg className="debug-accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>
                </button>
              </h2>
              <div className="debug-accordion-body" id="debug-chat-body" hidden>
                <div className="debug-log" id="chat-debug-log" role="log" aria-live="polite"></div>
              </div>
            </section>
            <section className="debug-accordion" data-debug-panel="images" id="debug-accordion-images">
              <h2 className="debug-accordion-heading">
                <button type="button" className="debug-accordion-toggle" id="debug-images-toggle" aria-expanded="false" aria-controls="debug-images-body">
                  <span>Debug imágenes</span>
                  <svg className="debug-accordion-chevron" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>
                </button>
              </h2>
              <div className="debug-accordion-body" id="debug-images-body" hidden>
                <button type="button" id="images-debug-stop" className="icon-btn debug-stop-btn" title="Abortar todas las generaciones" aria-label="Abortar generaciones">Stop</button>
                <div className="debug-log" id="images-debug-log" role="log" aria-live="polite"></div>
              </div>
            </section>
          </div>
        </aside>
      </div>
      <footer id="app-status-bar" className="app-status-bar" role="status" aria-live="polite" aria-atomic="false">
        <span className="app-status-bar-grip" aria-hidden="true"></span>
        <span id="app-status-text" className="app-status-bar-text">Listo</span>
        <span id="app-status-detail" className="app-status-bar-detail" hidden></span>
        <AuthStatusBar />
        <div className="app-status-bar-right">
          <div className="status-bar-model-info" aria-label="Modelo activo">
            <span id="connection-status-dot" className="connection-status-dot" aria-hidden="true"></span>
            <span id="image-batch-progress" className="image-batch-progress" hidden aria-label="Progreso de imágenes por petición"></span>
            <span id="header-provider-name" className="header-provider-model status-bar-provider"></span>
            <span id="header-model-name" className="header-provider-model status-bar-model"></span>
            <span id="status-model-capabilities" className="model-capability-chips status-model-capabilities" hidden role="list" aria-label="Capacidades del modelo"></span>
          </div>
          <div className="status-bar-ctx" id="context-usage-row" aria-live="polite" title="Uso de contexto">
            <span className="context-usage-label" id="context-usage-label">Ctx</span>
            <span id="context-usage-badge" className="context-badge">—</span>
            <span id="context-usage-text" className="context-usage-text status-bar-ctx-detail"></span>
            <div id="context-usage-bar-wrap" className="context-usage-bar-wrap" hidden>
              <div id="context-usage-bar" className="context-usage-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" aria-label="Tokens de contexto usados">
                <div id="context-usage-segment-prompt" className="context-usage-segment context-usage-prompt"></div>
                <div id="context-usage-segment-completion" className="context-usage-segment context-usage-completion"></div>
              </div>
            </div>
          </div>
        </div>
      </footer>
      <ReadingModeOverlay />
      <div
        id="image-gallery-lightbox"
        className="modal-overlay image-gallery-lightbox"
        role="dialog"
        aria-modal="true"
        aria-labelledby="image-gallery-lightbox-title"
        hidden
      >
        <div className="modal-content image-gallery-lightbox-content">
          <div className="image-gallery-lightbox-header">
            <h2 id="image-gallery-lightbox-title" className="modal-title">Imagen generada</h2>
            <button type="button" id="image-gallery-lightbox-close" className="icon-btn" title="Cerrar" aria-label="Cerrar">×</button>
          </div>
          <div className="image-gallery-lightbox-body">
            <div className="image-gallery-lightbox-media">
              <button type="button" id="image-gallery-lightbox-prev" className="image-gallery-lightbox-nav" title="Anterior" aria-label="Imagen anterior">‹</button>
              <img id="image-gallery-lightbox-img" alt="" />
              <button type="button" id="image-gallery-lightbox-next" className="image-gallery-lightbox-nav" title="Siguiente" aria-label="Imagen siguiente">›</button>
            </div>
            <div className="image-gallery-lightbox-meta" id="image-gallery-lightbox-meta"></div>
          </div>
        </div>
      </div>
      <div id="model-info-modal" className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="model-info-modal-title" hidden>
        <div className="modal-content model-info-modal-content">
          <h2 id="model-info-modal-title" className="modal-title">Ficha del modelo</h2>
          <p id="model-info-modal-subtitle" className="model-info-subtitle"></p>
          <div id="model-info-provider-block" className="model-info-block model-info-provider">
            <h3 className="model-info-block-title">Información del proveedor</h3>
            <div id="model-info-provider-content" className="model-info-provider-content"></div>
            <div id="model-info-refresh-row" className="model-info-actions">
              <button type="button" id="btn-model-info-refresh" className="btn btn-secondary">Refrescar desde proveedor</button>
              <span id="model-info-refresh-status" className="model-info-status"></span>
            </div>
          </div>
          <div id="model-info-user-block" className="model-info-block model-info-user">
            <h3 className="model-info-block-title">Datos de usuario</h3>
            <div className="model-info-field">
              <label className="model-info-label">
                <input type="checkbox" id="model-info-uncensored" />
                <span>Uncensored</span>
              </label>
            </div>
            <div className="model-info-field">
              <label className="model-info-label">Instrucciones que funcionan bien</label>
              <div id="model-info-instructions-list" className="model-info-instructions-list"></div>
              <button type="button" id="btn-add-instruction" className="btn btn-secondary btn-small">Añadir línea</button>
            </div>
            <div className="model-info-field">
              <label className="model-info-label">Tags</label>
              <div id="model-info-tags-container" className="model-info-tags-container">
                <div id="model-info-tags-chips" className="model-info-tags-chips"></div>
                <div className="model-info-tags-input-wrap">
                  <input type="text" id="model-info-tags-input" className="model-info-tags-input" placeholder="Escribe y pulsa Enter o elige de la lista" autoComplete="off" />
                  <div id="model-info-tags-suggestions" className="model-info-tags-suggestions" hidden></div>
                </div>
              </div>
            </div>
          </div>
          <div className="model-info-modal-actions">
            <button type="button" id="btn-model-info-save" className="btn btn-primary">Guardar</button>
            <button type="button" id="model-info-modal-close" className="btn btn-secondary">Cerrar</button>
          </div>
        </div>
      </div>
      <RuleEditModal />
      <div id="msg-text-context-menu" className="msg-text-context-menu" role="menu" hidden>
        <button type="button" className="msg-context-item" role="menuitem" data-action="illustrate-at">Generar imagen aquí</button>
        <button type="button" className="msg-context-item" role="menuitem" data-action="copy-selection" id="msg-text-copy" hidden>Copiar</button>
      </div>
      <div id="image-queue-context-menu" className="image-queue-context-menu" role="menu" hidden>
        <button type="button" className="msg-context-item" role="menuitem" data-action="delete">Eliminar</button>
      </div>
      <div id="workspace-profile-name-modal" className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="workspace-profile-name-title" hidden>
        <div className="modal-content workspace-profile-name-modal">
          <h2 id="workspace-profile-name-title" className="modal-title">Nombre del perfil</h2>
          <label id="workspace-profile-name-label" className="workspace-profile-name-label" htmlFor="workspace-profile-name-input">Cómo se llama este rig</label>
          <input type="text" id="workspace-profile-name-input" className="workspace-profile-name-input" maxLength="80" placeholder="Relato · faro" autoComplete="off" />
          <div className="workspace-profile-name-actions">
            <button type="button" id="workspace-profile-name-cancel" className="btn btn-secondary">Cancelar</button>
            <button type="button" id="workspace-profile-name-confirm" className="btn btn-primary">Guardar</button>
          </div>
        </div>
      </div>
    </>
    </AuthGate>
  );
}
