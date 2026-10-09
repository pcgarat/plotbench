from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ----- Models -----
class ModelInfo(BaseModel):
    """Información básica de un modelo (compatibilidad)."""
    name: str


class ProviderModelInfo(BaseModel):
    """Información extendida de un modelo con proveedor."""
    name: str
    provider: str
    display_name: str | None = None
    context_length: int | None = None
    pricing: dict[str, float] | None = None


class ProviderInfo(BaseModel):
    """Información de un proveedor de LLM."""
    name: str
    available: bool = True


# ----- Model info (ficha por modelo: provider_info + user_info) -----
class ModelInfoUserInfo(BaseModel):
    """Datos que el usuario asocia a un modelo. instructions = reglas resueltas desde instruction_ids."""
    uncensored: bool = False
    instructions: list["RuleItem"] = Field(default_factory=list)  # Reglas resueltas (rule_id, title, content)
    instruction_ids: list[str] = Field(default_factory=list)  # Ids de reglas en la biblioteca
    tags: list[str] = Field(default_factory=list)


class ModelInfoResponse(BaseModel):
    """Respuesta de GET /api/providers/{provider}/models/.../info."""
    provider_info: dict[str, Any] = Field(default_factory=dict)
    user_info: ModelInfoUserInfo = Field(default_factory=lambda: ModelInfoUserInfo())


class ModelInfoUpdateRequest(BaseModel):
    """Body de PUT/PATCH para actualizar solo user_info (todos los campos opcionales). Límites aplicados en backend."""
    uncensored: Optional[bool] = None
    instructions: Optional[list[str]] = None  # Legado
    instruction_ids: Optional[list[str]] = None  # Ids de reglas (biblioteca)
    tags: Optional[list[str]] = None


class TagsResponse(BaseModel):
    """Respuesta de GET /api/models/tags (lista de tags únicos para autocompletado)."""
    tags: list[str] = Field(default_factory=list)


class ProviderCapabilitiesResponse(BaseModel):
    """Respuesta de GET /api/providers/{provider}/capabilities."""
    capabilities: list[str] = Field(default_factory=list)


class ModelContractThinkingOut(BaseModel):
    kind: str
    values: list[str] = Field(default_factory=list)
    can_disable: bool = True
    true_maps_to: str | None = None
    default: Any = None


class ModelContractCapabilitiesOut(BaseModel):
    vision: bool = False
    tools: bool = False
    structured_output: bool = False
    thinking: ModelContractThinkingOut


class ModelContractRecipeOut(BaseModel):
    id: str
    label: str
    params: dict[str, Any] = Field(default_factory=dict)


class ModelContractResponse(BaseModel):
    """Respuesta de GET /api/providers/{provider}/models/{model_id}/contract."""
    provider: str
    model: str
    capabilities: ModelContractCapabilitiesOut
    params: dict[str, Any] = Field(default_factory=dict)
    recipes: list[ModelContractRecipeOut] = Field(default_factory=list)
    quirks: list[str] = Field(default_factory=list)


class StreamUsageInfo(BaseModel):
    """
    Uso de tokens en el stream (normalizado para todos los proveedores).
    Los proveedores mapean sus campos (Ollama: prompt_eval_count/eval_count,
    Mancer: usage.prompt_tokens/completion_tokens) a este esquema.
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0


# ----- Rules (biblioteca) -----
class RuleCreate(BaseModel):
    """Body para crear una regla en la biblioteca."""
    title: str = ""
    content: str = ""
    scope: Literal["chat", "planner"] = "chat"


class RuleUpdate(BaseModel):
    """Body para actualizar una regla (todos opcionales)."""
    title: Optional[str] = None
    content: Optional[str] = None


class RuleOut(BaseModel):
    """Regla devuelta por la API (biblioteca)."""
    id: str
    title: str
    content: str
    scope: Literal["chat", "planner"] = "chat"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ----- Conversation -----
class RuleItem(BaseModel):
    """Ítem de regla en una conversación: puede ser referencia (rule_id) o inline (title+content)."""
    rule_id: Optional[str] = None  # Si existe, se resuelve desde la biblioteca
    title: str = ""
    content: str = ""


ConversationKind = Literal["chat", "prompt_generator"]


class ConversationCreate(BaseModel):
    title: str = "Nueva conversación"
    auto_title: bool = False
    model_id: str = "llama3.2"
    provider: str = "ollama"  # ollama | mancer | openai
    kind: ConversationKind = "chat"
    system_instruction_global: Optional[str] = None
    system_instructions: Optional[list[RuleItem]] = None  # Lista de reglas (título + contenido)
    inject_instruction_every: Optional[int] = None  # Deprecado: se ignora. Las instrucciones se envían siempre.
    images: Optional["WorkspaceImagesSnapshot"] = None


class ConversationFork(BaseModel):
    """Crea una conversación vacía cuyo historial se resuelve desde un mensaje origen."""
    message_id: str = Field(..., min_length=1)


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    auto_title: Optional[bool] = None
    model_id: Optional[str] = None
    provider: Optional[str] = None  # ollama | mancer | openai
    system_instruction_global: Optional[str] = None
    system_instructions: Optional[list[RuleItem]] = None
    inject_instruction_every: Optional[int] = None  # Deprecado: se ignora.
    model_params: Optional[dict[str, Any]] = None  # Parámetros del modelo guardados por el usuario en esta conversación
    history_turns: Optional[int] = None  # Pares user+assistant a enviar en el prompt; null = default 5
    instruction_override: Optional[str] = None  # Instrucción solo para el siguiente mensaje; último valor por conversación
    active_leaf_message_id: Optional[str] = None  # Hoja del intento visible; no reordena la lista
    images: Optional["WorkspaceImagesSnapshot"] = None  # Ajustes del panel Imágenes


class MessageInChat(BaseModel):
    role: str
    content: str
    id: Optional[str] = None
    parent_id: Optional[str] = None
    debug_request: Optional[str] = None  # JSON enviado al LLM (solo assistant)
    debug_response: Optional[str] = None  # Raw del stream (solo assistant)


class ConversationOut(BaseModel):
    id: str
    title: str
    auto_title: bool = False
    model_id: str
    provider: str = "ollama"  # ollama | mancer | openai
    kind: ConversationKind = "chat"
    prompt_brief: Optional[dict[str, Any]] = None
    system_instruction_global: Optional[str] = None
    system_instructions: Optional[list[RuleItem]] = None
    inject_instruction_every: Optional[int] = None
    model_params: Optional[dict[str, Any]] = None
    history_turns: Optional[int] = None  # Pares user+assistant en el prompt; null = default 5
    instruction_override: Optional[str] = None  # Último valor de instrucción por mensaje en esta conversación
    active_leaf_message_id: Optional[str] = None
    images: Optional["WorkspaceImagesSnapshot"] = None
    forked_from_conversation_id: Optional[str] = None
    forked_from_message_id: Optional[str] = None
    inherited_messages: list[MessageInChat] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    messages: list[MessageInChat] = []

    class Config:
        from_attributes = True


class ConversationListItem(BaseModel):
    id: str
    title: str
    auto_title: bool = False
    model_id: str
    provider: str = "ollama"  # ollama | mancer | openai
    kind: ConversationKind = "chat"
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    deleted_at: datetime | None = None
    forked_from_conversation_id: Optional[str] = None

    class Config:
        from_attributes = True


# Qué guardar en ChromaDB: "none" nada, "user" solo mensajes usuario, "assistant" solo respuestas, "both" ambos
SaveToChromadbKind = Literal["none", "user", "assistant", "both"]


# ----- Messages -----
class MessageSend(BaseModel):
    content: str = Field(..., min_length=1)
    parent_message_id: Optional[str] = None  # Ancla del intento; null = continuar desde la hoja activa
    instruction_override: Optional[str] = None
    system_instruction_global: Optional[str] = None
    inject_instruction_every: Optional[int] = None  # Deprecado: se ignora.
    save_to_chromadb: SaveToChromadbKind = "user"  # qué indexar en Chroma: none, user, assistant, both
    # Solo incluir parámetros que el usuario ha modificado; si vacío o ausente, no se envían extras.
    model_params: Optional[dict[str, Any]] = None


class MessageResponse(BaseModel):
    role: str
    content: str
    id: Optional[str] = None

    class Config:
        from_attributes = True


class MessageHistoryItem(BaseModel):
    id: str
    conversation_id: str
    conversation_title: str
    parent_id: Optional[str] = None
    content_preview: str
    created_at: datetime
    latest_image_at: datetime | None = None

    class Config:
        from_attributes = True


class MessageHistoryListResponse(BaseModel):
    items: list[MessageHistoryItem]
    total: int
    limit: int
    offset: int
    search_in: Optional[Literal["title", "content"]] = None


class MessageTreeNode(BaseModel):
    id: str
    conversation_id: str
    conversation_title: str
    content_preview: str
    created_at: datetime
    parent_message_id: Optional[str] = None
    is_fork_edge: bool = False
    has_children: bool = False
    sibling_index: Optional[int] = None
    sibling_count: Optional[int] = None
    active_leaf_message_id: Optional[str] = None


class MessageTreeListResponse(BaseModel):
    items: list[MessageTreeNode]
    total: int
    limit: int
    offset: int


class HistoryDeleteRequest(BaseModel):
    message_ids: list[str] = Field(default_factory=list)


class HistoryDeleteResponse(BaseModel):
    trashed_conversation_ids: list[str] = Field(default_factory=list)
    deleted_message_ids: list[str] = Field(default_factory=list)


class ForgePanelParamFields(BaseModel):
    """steps/width/height/seed opcionales del panel Imágenes (None = replay del último gen)."""

    steps: Optional[int] = Field(
        default=None,
        ge=1,
        le=150,
        description="Override de steps en Forge; None = usar el del último gen.",
    )
    width: Optional[int] = Field(
        default=None,
        ge=64,
        le=4096,
        description="Override de width en Forge; None = usar el del último gen.",
    )
    height: Optional[int] = Field(
        default=None,
        ge=64,
        le=4096,
        description="Override de height en Forge; None = usar el del último gen.",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Override de seed en Forge (-1 = aleatorio); None = usar el del último gen.",
    )

    @field_validator("steps", "width", "height", "seed", mode="before")
    @classmethod
    def _blank_forge_param_to_none(cls, value):
        return None if value == "" else value


class ReactorPanelSettings(BaseModel):
    """Prefs ReActor del panel Imágenes; vacío = usar defaults de .env."""

    enabled: bool = False
    female_enabled: bool = False
    female_face_model: str = Field(default="", max_length=256)
    male_enabled: bool = False
    male_face_model: str = Field(default="", max_length=256)
    model: Optional[str] = Field(default=None, max_length=256)
    source_faces_index: Optional[str] = Field(default=None, max_length=64)
    face_index: Optional[str] = Field(default=None, max_length=64)
    upscaler: Optional[str] = Field(default=None, max_length=256)
    scale: Optional[float] = Field(default=None, ge=0.1, le=8.0)
    upscale_visibility: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    face_restorer: Optional[str] = Field(default=None, max_length=64)
    restorer_visibility: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    codeformer_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    restore_first: Optional[int] = Field(default=None, ge=0, le=1)
    gender_source: Optional[int] = Field(default=None, ge=0, le=2)
    gender_target: Optional[int] = Field(default=None, ge=0, le=2)
    device: Optional[str] = Field(default=None, max_length=32)
    mask_face: Optional[int] = Field(default=None, ge=0, le=1)
    select_source: Optional[int] = Field(default=None, ge=0, le=2)
    face_model: Optional[str] = Field(default=None, max_length=256)
    source_folder: Optional[str] = Field(default=None, max_length=512)
    random_image: Optional[int] = Field(default=None, ge=0, le=1)
    upscale_force: Optional[int] = Field(default=None, ge=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def _blank_optional_numerics_to_none(cls, data):
        if not isinstance(data, dict):
            return data
        numeric_keys = (
            "scale",
            "upscale_visibility",
            "restorer_visibility",
            "codeformer_weight",
            "restore_first",
            "gender_source",
            "gender_target",
            "mask_face",
            "select_source",
            "random_image",
            "upscale_force",
        )
        out = dict(data)
        for key in numeric_keys:
            if out.get(key) == "":
                out[key] = None
        return out


class ReactorDefaultsResponse(BaseModel):
    """Valores por defecto ReActor leídos de .env (autorrelleno del panel)."""

    defaults: dict[str, Any] = Field(default_factory=dict)


class IllustrateRequest(ForgePanelParamFields):
    """Opciones del panel Imágenes para POST .../illustrate."""

    images_per_response: int = Field(default=2, ge=1)
    batch_size: int = Field(
        default=10,
        ge=1,
        description=(
            "Tamaño de lote para planificar prompts y generar imágenes. "
            "Si images_per_response supera este valor, se procesa en lotes."
        ),
    )
    prompt_provider: str = Field(default="ollama", min_length=1)
    prompt_model: str = Field(default="", description="Obligatorio salvo use_chat_config.")
    prompt_model_params: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Params del LLM planificador. Sin use_chat_config: overlay/receta del panel. "
            "Con use_chat_config: params vivos del chat (si vacío, se usan los de la conversación)."
        ),
    )
    retries: int = Field(default=1, ge=0, le=10)
    prompt: str = Field(
        default="",
        max_length=4000,
        description="Texto opcional concatenado a cada prompt de escena antes de enviar a Forge.",
    )
    prompt_system_instructions: str = Field(
        default="",
        max_length=64_000,
        description="Instrucciones adicionales de sistema para el LLM que planifica escenas/prompts.",
    )
    use_chat_config: bool = Field(
        default=False,
        description=(
            "Si true, el planificador usa provider, modelo y reglas de la conversación; "
            "prompt_model_params vivos del body (si hay) o los guardados en la conversación; "
            "las instrucciones del planificador se concatenan igualmente."
        ),
    )
    include_prompt_debug: bool = Field(
        default=False,
        description="Si true, emite eventos llm_debug (request/response del planificador) por llamada al LLM.",
    )
    visual_consistency: bool = Field(
        default=True,
        description=(
            "Si true, el planificador reutiliza tokens de identidad (edad, vestuario, aspecto) "
            "entre las escenas del mensaje. Si false, prioriza variedad de look."
        ),
    )
    scene_selection_strategy: str = Field(
        default="distributed",
        description=(
            "Estrategia de selección de escenas: "
            "'distributed' (huecos), 'llm_erotic_story' (narrativa erótica) "
            "o 'llm_pornographic_peaks' (picos pornográficos)."
        ),
    )
    reactor: ReactorPanelSettings = Field(default_factory=ReactorPanelSettings)
    debug: bool = False

    @field_validator("scene_selection_strategy", mode="before")
    @classmethod
    def _normalize_scene_selection_strategy(cls, value):
        from app.services.image_illustration.scene_selection import (
            normalize_scene_selection_strategy_id,
        )

        return normalize_scene_selection_strategy_id(
            value if isinstance(value, str) or value is None else str(value)
        )

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_reactor_enabled(cls, data):
        if not isinstance(data, dict):
            return data
        if "reactor_enabled" not in data:
            return data
        migrated = dict(data)
        legacy = bool(migrated.pop("reactor_enabled"))
        reactor = migrated.get("reactor")
        if isinstance(reactor, dict):
            reactor = dict(reactor)
            reactor.setdefault("enabled", legacy)
            migrated["reactor"] = reactor
        else:
            migrated["reactor"] = {"enabled": legacy}
        return migrated

    @model_validator(mode="after")
    def _require_prompt_model_unless_chat_config(self):
        if not self.use_chat_config and not (self.prompt_model or "").strip():
            raise ValueError("prompt_model es obligatorio si use_chat_config es false")
        return self


class IllustrateAtRequest(IllustrateRequest):
    """Una imagen en un párrafo concreto (click derecho / selección)."""

    paragraph_index: int = Field(ge=0, description="Índice de párrafo del mapa de cobertura.")
    selected_excerpt: str = Field(
        default="",
        max_length=2000,
        description="Texto seleccionado como foco de la escena; vacío = todo el párrafo.",
    )


class GenerateRemainingRequest(ForgePanelParamFields):
    """Opciones para regenerar anclas/placeholders pendientes sin re-planificar."""

    retries: int = Field(default=1, ge=0, le=10)
    batch_size: int = Field(
        default=10,
        ge=1,
        description="Tamaño de lote al regenerar imágenes pendientes en Forge.",
    )
    reactor: ReactorPanelSettings = Field(default_factory=ReactorPanelSettings)
    debug: bool = False

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_reactor_enabled(cls, data):
        if not isinstance(data, dict):
            return data
        if "reactor_enabled" not in data:
            return data
        migrated = dict(data)
        legacy = bool(migrated.pop("reactor_enabled"))
        reactor = migrated.get("reactor")
        if isinstance(reactor, dict):
            reactor = dict(reactor)
            reactor.setdefault("enabled", legacy)
            migrated["reactor"] = reactor
        else:
            migrated["reactor"] = {"enabled": legacy}
        return migrated


class ForgeLastGenerationParamsResponse(BaseModel):
    """Params del último gen de Forge para autorrellenar el panel Imágenes."""

    available: bool = False
    steps: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    seed: Optional[int] = None
    mode: Optional[str] = None
    detail: Optional[str] = None


class MessageContentUpdateResponse(BaseModel):
    """Content actualizado tras editar ilustraciones de un mensaje."""

    id: str
    content: str
    deleted_files: int = 0


class IllustratedImageMetaResponse(BaseModel):
    """Metadatos de generación Forge de una imagen ilustrada."""

    filename: str
    scene_id: Optional[str] = None
    mode: str = "txt2img"
    params: dict = Field(default_factory=dict)
    created_at: Optional[str] = None
    prompt_model: Optional[str] = None
    prompt_provider: Optional[str] = None
    conversation_id: Optional[str] = None
    conversation_title: Optional[str] = None
    message_id: Optional[str] = None


class IllustratedImageListItem(BaseModel):
    """Ítem de la galería: miniatura + params clave + enlace al chat."""

    filename: str
    url: str
    scene_id: Optional[str] = None
    mode: str = "txt2img"
    prompt: str = ""
    steps: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    seed: Optional[int] = None
    sampler_name: Optional[str] = None
    forge_model: Optional[str] = None
    prompt_model: Optional[str] = None
    prompt_provider: Optional[str] = None
    batch_id: Optional[str] = None
    conversation_id: str
    conversation_title: str
    message_id: str
    created_at: Optional[str] = None
    params: dict = Field(default_factory=dict)


class IllustratedImageListResponse(BaseModel):
    items: list[IllustratedImageListItem]
    total: int
    limit: int
    offset: int


class IllustratedImageBatchFacet(BaseModel):
    batch_id: str
    image_count: int = 0
    created_at: Optional[str] = None


class IllustratedImageFacetsResponse(BaseModel):
    prompt_providers: list[str] = Field(default_factory=list)
    prompt_models: list[str] = Field(default_factory=list)
    forge_models: list[str] = Field(default_factory=list)
    steps: list[int] = Field(default_factory=list)
    seeds: list[int] = Field(default_factory=list)
    sizes: list[str] = Field(default_factory=list)
    modes: list[str] = Field(default_factory=list)
    batches: list[IllustratedImageBatchFacet] = Field(default_factory=list)
    has_missing_prompt_llm: bool = False


class IllustratedImageFilenameListResponse(BaseModel):
    filenames: list[str] = Field(default_factory=list)


class IllustratedImageMessageSummary(BaseModel):
    message_id: str
    role: str = "assistant"
    created_at: Optional[str] = None
    excerpt: str = ""
    image_count: int = 0


class IllustratedImageMessageListResponse(BaseModel):
    items: list[IllustratedImageMessageSummary] = Field(default_factory=list)


class ImageGenerationJobListItem(BaseModel):
    id: str
    status: str
    conversation_id: str
    conversation_title: str
    message_id: str
    message_excerpt: str = ""
    scene_id: str
    forge_prompt: str = ""
    prompt_model: Optional[str] = None
    prompt_provider: Optional[str] = None
    batch_id: Optional[str] = None
    error_message: Optional[str] = None
    result_filename: Optional[str] = None
    rules: dict = Field(default_factory=dict)
    forge_mode: str = "txt2img"
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ImageGenerationBatchProgress(BaseModel):
    batch_id: str
    completed: int = 0
    total: int = 0
    created_at: Optional[str] = None


class ImageGenerationJobListResponse(BaseModel):
    items: list[ImageGenerationJobListItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
    active_count: int = 0
    paused: bool = False
    batch_progress: list[ImageGenerationBatchProgress] = Field(default_factory=list)


class ImageGenerationQueueRunStateResponse(BaseModel):
    paused: bool = False


class ImageGenerationJobDeleteRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=200)


class ImageGenerationJobDeleteResponse(BaseModel):
    deleted: int = 0
    ids: list[str] = Field(default_factory=list)


class IllustratedImageOrphansResponse(BaseModel):
    count: int = 0


class IllustratedImageOrphansPurgeResponse(BaseModel):
    deleted_files: int = 0
    deleted_meta: int = 0


class PurgeDeletedConversationsResponse(BaseModel):
    deleted: int = 0
    ids: list[str] = Field(default_factory=list)


class WorkspaceImagesSnapshot(ForgePanelParamFields):
    """Prefs del panel Imágenes (sin debug ni cromo de UI)."""

    enabled: bool = False
    use_chat_config: bool = False
    visual_consistency: bool = True
    scene_selection_strategy: str = "distributed"
    images_per_response: int = 2
    batch_size: int = 10
    retries: int = 1
    prompt: str = ""
    prompt_system_instructions: list[RuleItem] = Field(default_factory=list)
    prompt_provider: str = ""
    prompt_model: str = ""
    prompt_model_params: dict[str, Any] = Field(default_factory=dict)
    reactor: ReactorPanelSettings = Field(default_factory=ReactorPanelSettings)

    @field_validator("prompt_system_instructions", mode="before")
    @classmethod
    def _coerce_prompt_system_instructions(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            text = value.strip()
            return [{"title": "Instrucciones", "content": text}] if text else []
        return value

    @field_validator("scene_selection_strategy", mode="before")
    @classmethod
    def _normalize_scene_selection_strategy(cls, value):
        from app.services.image_illustration.scene_selection import (
            normalize_scene_selection_strategy_id,
        )

        return normalize_scene_selection_strategy_id(
            value if isinstance(value, str) or value is None else str(value)
        )


class WorkspaceSnapshotIn(BaseModel):
    """Cuerpo del rig. El servicio recorta y valida."""

    provider: str = "ollama"
    model_id: str = ""
    model_params: dict[str, Any] = Field(default_factory=dict)
    params_excluded: list[str] = Field(default_factory=list)
    history_turns: int = 5
    system_instructions: list[RuleItem] = Field(default_factory=list)
    images: WorkspaceImagesSnapshot = Field(default_factory=WorkspaceImagesSnapshot)


class WorkspaceProfileCreate(BaseModel):
    name: str
    snapshot: WorkspaceSnapshotIn


class WorkspaceProfileUpdate(BaseModel):
    name: Optional[str] = None
    snapshot: Optional[WorkspaceSnapshotIn] = None


class WorkspaceProfileOut(BaseModel):
    id: str
    name: str
    snapshot: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PlannerRulePresetSnapshot(BaseModel):
    """Selección de reglas del planificador (sin cromo de UI)."""

    rules: list[RuleItem] = Field(default_factory=list)

    @field_validator("rules", mode="before")
    @classmethod
    def _coerce_rules(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            text = value.strip()
            return [{"title": "Instrucciones", "content": text}] if text else []
        return value


class PlannerRulePresetCreate(BaseModel):
    name: str
    snapshot: PlannerRulePresetSnapshot = Field(default_factory=PlannerRulePresetSnapshot)


class PlannerRulePresetUpdate(BaseModel):
    name: Optional[str] = None
    snapshot: Optional[PlannerRulePresetSnapshot] = None


class PlannerRulePresetOut(BaseModel):
    id: str
    name: str
    snapshot: dict[str, Any]
    created_at: datetime
    updated_at: datetime


ConversationCreate.model_rebuild()
ConversationUpdate.model_rebuild()
ConversationOut.model_rebuild()
