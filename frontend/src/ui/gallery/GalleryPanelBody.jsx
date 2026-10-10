import { useEffect } from "react";
import { initImageGallery } from "../../app/galleryActions.js";

export function GalleryPanelBody() {
  useEffect(() => {
    initImageGallery();
  }, []);

  return (
    <>
      <div className="image-gallery-toolbar" id="image-gallery-toolbar">
        <label className="image-gallery-filter">
          <span>LLM</span>
          <select id="gallery-filter-prompt-model" className="param-control" aria-label="Filtrar por LLM">
            <option value="">Todos</option>
          </select>
        </label>
        <label className="image-gallery-filter">
          <span>Provider</span>
          <select id="gallery-filter-prompt-provider" className="param-control" aria-label="Filtrar por Provider">
            <option value="">Todos</option>
          </select>
        </label>
        <label className="image-gallery-filter">
          <span>Checkpoint</span>
          <select id="gallery-filter-forge-model" className="param-control" aria-label="Filtrar por Checkpoint">
            <option value="">Todos</option>
          </select>
        </label>
        <label className="image-gallery-filter">
          <span>Steps</span>
          <select id="gallery-filter-steps" className="param-control" aria-label="Filtrar por Steps">
            <option value="">Todos</option>
          </select>
        </label>
        <label className="image-gallery-filter">
          <span>Tamaño</span>
          <select id="gallery-filter-size" className="param-control" aria-label="Filtrar por Tamaño">
            <option value="">Todos</option>
          </select>
        </label>
        <label className="image-gallery-filter">
          <span>Modo</span>
          <select id="gallery-filter-mode" className="param-control" aria-label="Filtrar por Modo">
            <option value="">Todos</option>
          </select>
        </label>
        <label className="image-gallery-filter">
          <span>Seed</span>
          <select id="gallery-filter-seed" className="param-control" aria-label="Filtrar por Seed">
            <option value="">Todos</option>
          </select>
        </label>
        <label className="image-gallery-filter image-gallery-filter-prompt">
          <span>Prompt</span>
          <input type="search" id="gallery-filter-prompt-q" className="param-control" placeholder="Buscar en el prompt" aria-label="Buscar en el prompt" />
        </label>
      </div>
      <div className="image-gallery-scope" id="image-gallery-scope">
        <button type="button" id="gallery-scope-all" className="btn btn-secondary btn-small" aria-pressed="false">Todas las conversaciones</button>
        <span id="gallery-scope-conv-label" className="image-gallery-scope-label" hidden></span>
        <button type="button" id="gallery-purge-orphans" className="btn btn-secondary btn-small image-gallery-purge-orphans" title="Eliminar del disco las imágenes que no están incrustadas en ningún mensaje">Eliminar archivos huérfanos</button>
      </div>
      <div className="image-gallery-messages" id="image-gallery-messages" hidden></div>
      <div className="image-gallery-families" id="image-gallery-families" hidden>
        <label className="image-gallery-filter image-gallery-filter-batches" htmlFor="gallery-filter-batch-ids">
          <span>Lotes</span>
          <select
            id="gallery-filter-batch-ids"
            className="param-control"
            multiple
            size={4}
            aria-label="Filtrar por lotes de generación"
          ></select>
        </label>
      </div>
      <div className="image-gallery-grid" id="image-gallery-grid"></div>
      <div className="image-gallery-pager" id="image-gallery-pager"></div>
    </>
  );
}

export { initImageGallery };
