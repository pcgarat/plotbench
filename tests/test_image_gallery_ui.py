"""Vista de galería de imágenes generadas (listado, filtros, lightbox)."""
from tests.frontend_source import frontend_markup, frontend_source

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STYLE_CSS = ROOT / "frontend" / "src" / "styles" / "style.css"


def test_gallery_entry_and_panel_exist_in_html():
    html = frontend_markup()
    assert 'id="btn-image-gallery"' in html
    assert 'id="btn-center-chat"' in html
    assert 'id="image-gallery-panel"' in html
    assert 'id="chat-column"' in html
    assert 'id="image-gallery-grid"' in html
    assert 'id="image-gallery-lightbox"' in html
    assert 'id="gallery-filter-prompt-model"' in html
    assert 'id="gallery-filter-forge-model"' in html
    assert 'id="gallery-filter-steps"' in html
    assert 'id="gallery-filter-size"' in html
    assert 'id="gallery-filter-mode"' in html
    assert 'id="gallery-filter-seed"' in html
    assert 'id="gallery-filter-prompt-q"' in html
    assert 'id="conversation-image-filter-notice"' in html
    assert 'id="conversation-image-filter-notice-dismiss"' in html
    assert 'class="chat-image-filter-notice-open"' in html
    assert 'id="gallery-scope-all"' in html
    assert 'id="gallery-scope-conv-label"' in html
    assert 'id="center-panels-empty"' in html
    assert 'id="center-panels-splitter"' in html
    header = html[html.index('class="chat-panel-header"') : html.index('id="center-panels-empty"')]
    left = html[html.index('id="column-left"') : html.index("</aside>")]
    actions = html[html.index('class="chat-session-actions"') : html.index('id="center-panels-empty"')]
    assert 'id="btn-center-chat"' in header
    assert 'id="btn-image-gallery"' in header
    assert 'id="btn-image-queue"' in header
    assert 'id="btn-history-messages"' not in header
    assert 'id="btn-center-chat"' not in left
    assert 'id="btn-image-gallery"' not in left
    assert 'id="btn-image-queue"' not in left
    assert 'id="btn-history-messages"' not in left
    assert "<ConversationsList" in left
    chat_btn = actions.index('id="btn-center-chat"')
    gallery_btn = actions.index('id="btn-image-gallery"')
    queue_btn = actions.index('id="btn-image-queue"')
    delete_btn = actions.index('id="btn-clear-memory"')
    assert chat_btn < gallery_btn < queue_btn < delete_btn
    assert 'class="center-view-toggle"' in actions
    assert 'id="gallery-view-title"' not in html
    panel = html.index('id="image-gallery-panel"')
    queue_panel = html.index('id="image-queue-panel"')
    chat = html.index('id="chat-column"')
    splitter = html.index('id="center-panels-splitter"')
    assert chat < splitter < panel < queue_panel
    assert 'id="image-queue-list"' in html
    assert 'id="image-queue-pause-toggle"' in html
    assert 'id="image-queue-paused-label"' in html
    assert 'id="image-queue-cancel-all"' in html
    assert 'id="gallery-purge-orphans"' in html
    assert 'scroll-y-reveal' in html
    assert 'id="messages-container"' in html
    assert 'status: "pending"' in html
    assert "Pendientes" in html
    assert "setQueueFilter" in html


def test_gallery_js_loads_list_and_opens_lightbox():
    js = frontend_source()
    assert "initImageGallery" in js
    assert "setGalleryPanelVisible" in js
    assert "setChatPanelVisible" in js
    assert "/illustrated-images/facets" in js
    assert "/illustrated-images?" in js
    assert "openGalleryLightbox" in js
    assert "openConversationAtMessage" in js
    assert "refreshGalleryAfterScopeChange" in js
    assert "gallery-scope-all" in js
    assert "illustrated-images/messages" in js
    assert "conversation_id" in js
    assert "data-center-gallery" in js
    assert "data-center-queue" in js
    assert "data-center-chat" in js
    assert "setQueuePanelVisible" in js
    assert "loadImageQueuePage" in js
    assert "bindScrollReveal" in js
    assert "is-scrollbar-visible" in js
    assert "deleteImageQueueJobs" in js
    assert "image-queue-delete-btn" in js
    assert "image-queue-context-menu" in js
    assert "toggleImageQueuePaused" in js
    assert "image-queue-pause-toggle" in js
    assert "cancelAllActiveImageQueueJobs" in js
    assert "image-generation-queue/cancel-active" in js
    assert "purgeOrphanIllustratedFiles" in js
    assert "illustrated-images/orphans/purge" in js
    assert "gallery-purge-orphans" in js
    assert "gallery-open-message" in js
    assert "openConversationAtIllustration" in js
    assert "highlightIllustrationInConversation" in js
    assert "initCenterPanelSplit" in js
    assert "centerChatGalleryShare" in js
    assert "applyCenterPanelShare" in js
    assert "btn-image-gallery" in js
    assert "btn-center-chat" in js
    assert "ArrowLeft" in js
    assert "gallery-page-input" in js
    assert "goToGalleryPage" in js
    assert "galleryOffsetForPage" in js
    assert "galleryTotalPages" in js


def test_open_conversation_does_not_close_gallery():
    from tests.frontend_source import frontend_file
    session = frontend_file("app/sessionActions.js")
    open_fn = session.split("export async function openConversation")[1].split("export async function openConsultaTurn")[0]
    assert "exitGalleryView" not in open_fn
    assert "isGalleryPanelVisible" in open_fn
    assert "setChatPanelVisible(true)" in open_fn
    new_fn = session.split("export async function newConversation")[1].split("export async function newPromptGeneratorConversation")[0]
    assert "exitGalleryView" not in new_fn
    assert "setChatPanelVisible(true)" in new_fn


def test_gallery_css_toggles_panels_independently():
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert "html[data-center-chat=\"off\"] .chat-column" in css
    assert "html[data-center-gallery=\"on\"] #image-gallery-panel" in css
    assert "html[data-center-gallery=\"on\"] .column-right" not in css
    assert ".image-gallery-grid" in css
    assert ".image-gallery-lightbox" in css
    assert ".image-gallery-messages" in css
    assert ".image-gallery-msg-chip" in css
    assert ".image-gallery-families" in css
    assert ".image-gallery-filter-batches" in css
    assert ".image-gallery-page-input" in css
    assert ".image-gallery-pager-jump" in css
    assert ".chat-image-filter-notice-wrap" in css
    assert ".chat-image-filter-notice-dismiss" in css
    assert ".chat-illustration-frame.is-gallery-filter-hidden" in css
    assert ".center-panel-toggles" in css
    toggles = css[css.index(".center-panel-toggles") : css.index(".center-panel-toggles") + 220]
    assert "inline-flex" in toggles
    assert "flex-direction: column" not in toggles
    assert ".center-view-toggle" in css
    assert ".center-view-toggle[aria-pressed=\"true\"]" in css
    assert ".center-view-toggle-text" in css
    assert "@container chat-title" in css
    assert ".center-panels-empty" in css
    assert ".center-panels-splitter" in css
    assert ".scroll-y-reveal" in css
    assert ".scroll-y-reveal.is-scrollbar-visible" in css
    scroll_reveal = css[css.index(".scroll-y-reveal") : css.index(".scroll-y-reveal") + 500]
    assert "scrollbar-gutter: stable" in scroll_reveal
    assert "scrollbar-width: none" not in scroll_reveal
    assert "--center-chat-share" in css
    assert "--center-gallery-share" in css
    assert "ns-resize" in css
    chunk = css[
        css.index("html[data-center-chat=\"off\"] .chat-column") : css.index(
            "html[data-center-chat=\"off\"] .chat-column"
        )
        + 200
    ]
    assert "display: none" in chunk or "display:none" in chunk


def test_gallery_thumbs_keep_original_aspect_ratio():
    """Las miniaturas no deben recortarse a un recuadro fijo (cover + alto fijo)."""
    css = STYLE_CSS.read_text(encoding="utf-8")
    js = frontend_source()
    block = re.search(r"\.image-gallery-card img\s*\{([^}]+)\}", css)
    assert block, "Falta regla .image-gallery-card img"
    body = block.group(1)
    assert "object-fit: cover" not in body
    assert not re.search(r"\bheight\s*:\s*\d+px", body), (
        "Un alto fijo aplasta retrato y panorama al mismo recuadro"
    )
    assert re.search(r"height\s*:\s*auto", body)
    assert "object-fit: contain" in body
    assert not re.search(r"aspect-ratio\s*:\s*[\d.]+", body)
    render = frontend_source()
    assert 'width="' in render
    assert "item.width" in render
    assert "item.height" in render
    assert "function renderGalleryGrid" in render


def test_gallery_cards_do_not_overflow_grid_rows():
    """Retrato y paisaje juntos no deben pintar unas tarjetas encima de otras.

    min-height en el img hace cíclico el track sizing del grid: la fila queda
    más baja que la imagen y la tarjeta (button) se desborda a la fila siguiente.
    """
    css = STYLE_CSS.read_text(encoding="utf-8")
    js = frontend_source()
    img = re.search(r"\.image-gallery-card img\s*\{([^}]+)\}", css)
    assert img, "Falta regla .image-gallery-card img"
    img_body = img.group(1)
    assert "min-height" not in img_body, (
        "min-height en el thumb subestima la fila y las tarjetas se pisan"
    )
    card = re.search(r"\.image-gallery-card\s*\{([^}]+)\}", css)
    assert card, "Falta regla .image-gallery-card"
    card_body = card.group(1)
    assert "width: 100%" in card_body
    assert "min-width: 0" in card_body
    assert "height: max-content" in card_body
    assert "appearance: none" in card_body
    grid = re.search(r"\.image-gallery-grid\s*\{([^}]+)\}", css)
    assert grid, "Falta regla .image-gallery-grid"
    assert "align-items: start" in grid.group(1)
    render = frontend_source()
    assert "aspect-ratio:" in render
    assert "item.width" in render
    assert "item.height" in render


def test_gallery_lightbox_navigates_across_pages():
    """El visor recorre toda la colección, no solo la página visible."""
    js = frontend_source()
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert "galleryTotal" in js
    assert "galleryPageOffsetForAbsolute" in js
    assert "loadGalleryPage" in js
    assert "silent: true" in js or "silent: true" in js.replace(" ", "")
    assert "Cargando…" in js
    assert "total > 1" in js
    assert "prev.disabled" in js
    assert "next.disabled" in js
    assert "function galleryPageOffsetForAbsolute" in js
    assert "GALLERY_PAGE_SIZE" in js
    assert ".image-gallery-lightbox-nav:disabled" in css


def test_chat_photo_opens_gallery_viewer():
    """Pulsar una foto del chat abre el mismo visor de la galería, con sus datos."""
    from tests.frontend_source import frontend_file

    js = frontend_source()
    gallery = frontend_file("app/galleryActions.js")
    app = frontend_file("App.jsx")
    assert "openChatImageViewer" in js
    assert "bindChatIllustrationViewerOpen" in js
    assert "collectChatIllustrationItems" in gallery
    assert "chatViewerItems" in gallery
    assert "imageViewerSource" in gallery
    assert "getIllustratedMeta" in gallery
    assert "renderIllustrationMetaBody" in gallery
    # El visor vive en la raíz: la galería puede estar cerrada.
    assert 'id="image-gallery-lightbox"' in app.replace("className=", "class=")
    assert 'id="image-gallery-lightbox"' not in frontend_file("ui/gallery/GalleryPanelBody.jsx")


def test_index_serves_gallery_button(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="btn-image-gallery"' in frontend_markup()
    assert 'id="btn-center-chat"' in frontend_markup()
    assert 'id="image-gallery-lightbox"' in frontend_markup()
    assert 'id="center-panels-splitter"' in frontend_markup()
    assert 'id="gallery-filter-seed"' in frontend_markup()
    assert 'id="conversation-image-filter-notice"' in frontend_markup()


def test_gallery_toolbar_filters_apply_to_conversation_images():
    js = frontend_source()
    html = frontend_markup()
    assert 'id="gallery-filter-seed"' in html
    assert "hasActiveGalleryToolbarFilters" in js
    assert "appendGalleryToolbarFilters" in js
    assert "refreshConversationImageFilter" in js
    assert "scheduleConversationImageFilter" in js
    assert "applyIllustrationFilterToRoot" in js
    assert "is-gallery-filter-hidden" in js
    assert "syncImageFilterNotice" in js
    assert "illustrated-images/matching-filenames" in js
    assert "gallery-filter-seed" in js
    assert "conversation_id" in js
    assert "syncImageFilterNotice" in js
    assert "conversation-image-filter-notice" in js
    assert "hasActiveGalleryToolbarFilters" in js
    assert "scheduleConversationImageFilter" in js
    assert "onGalleryToolbarFilterChange" in js
    assert "clearGalleryToolbarFilters" in js
    assert "conversation-image-filter-notice-dismiss" in js
    assert "setGalleryPanelVisible(true)" in js
    assert "chat-image-filter-notice-open" in js


def test_gallery_lightbox_goes_to_the_photo_in_the_message():
    """Ir al mensaje del visor debe anclar la foto, no el inicio del mensaje."""
    from tests.frontend_source import frontend_file

    gallery = frontend_file("app/galleryActions.js")
    lightbox = gallery.split("export function renderGalleryLightbox")[1].split(
        "export function openGalleryLightbox"
    )[0]
    assert "closeGalleryLightbox()" in lightbox
    assert "goToConversationTarget" in lightbox
    assert "item.filename" in lightbox
    assert "item.scene_id" in lightbox
    assert "openConversationAtMessage(" not in lightbox
    assert "pendingReveal" not in lightbox

    session = frontend_file("app/sessionActions.js")
    assert "findMessageWithIllustration" in session
    assert "goToConversationTarget" in session
    go_photo = session.split("export async function openConversationAtIllustration")[1].split(
        "export async function deleteMessageFromHistory"
    )[0]
    assert "queueRevealInMessages(conversationId, messageId, options)" in go_photo
    assert "revealMessageInConversation(conversationId, messageId, options)" in go_photo
    queue_fn = session.split("function queueRevealInMessages")[1].split(
        "export async function goToConversationTarget"
    )[0]
    assert "filename" in queue_fn
    assert "sceneId" in queue_fn
    assert "conversationId" in queue_fn
    pane = frontend_file("ui/messages/MessagesPane.jsx")
    reveal = pane.split("export function applyRevealInMessages")[1].split(
        "function illustrationRevealIsStable"
    )[0]
    assert "highlightIllustrationInConversation" in reveal
    assert "findMessageWithIllustration" in reveal
    assert "pending.conversationId" in reveal
    locate = frontend_file("lib/illustrationLocate.js")
    assert 'alt="escena ' in locate
    assert "findChatIllustration" in locate
    set_fn = session.split("export async function setCurrentConversation")[1].split(
        "let saveRulesDebounceTimer"
    )[0]
    assert "skipScroll" in set_fn

    queue = frontend_file("app/queueActions.js")
    assert "goToConversationTarget" in queue
    assert 'data-filename="' in queue
    assert "openConversationAtMessage(convId" not in queue
