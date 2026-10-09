import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db import Base


def generate_uuid():
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    KIND_CHAT = "chat"
    KIND_PROMPT_GENERATOR = "prompt_generator"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(512), nullable=False, default="Nueva conversación")
    auto_title = Column(Boolean, nullable=False, default=False)
    kind = Column(String(32), nullable=False, default=KIND_CHAT)
    model_id = Column(String(128), nullable=False, default="llama3.2")
    provider = Column(String(64), nullable=False, default="ollama")  # ollama | mancer
    system_instruction_global = Column(Text, nullable=True)  # Legado: una sola instrucción
    instruction_ids = Column(Text, nullable=True)  # JSON: lista de rule_id (referencias a rules). Fuente de verdad.
    system_instructions = Column(Text, nullable=True)  # Deprecado: antes se guardaba JSON con title+content; se mantiene para migración/legado
    inject_instruction_every = Column(Integer, nullable=True)  # Deprecado: se ignora. Las instrucciones se envían siempre.
    model_params = Column(Text, nullable=True)  # JSON: param_id -> value (parámetros guardados por el usuario en esta conversación)
    images = Column(Text, nullable=True)  # JSON: snapshot del panel Imágenes (igual que el resto de ajustes)
    prompt_brief = Column(Text, nullable=True)  # JSON: PromptBrief (solo prompt_generator)
    history_turns = Column(Integer, nullable=True)  # Número de pares user+assistant a enviar en el prompt; null/0 = usar default 5
    instruction_override = Column(Text, nullable=True)  # Instrucción solo para el siguiente mensaje; último valor por conversación
    active_leaf_message_id = Column(String(36), nullable=True)  # Hoja del camino de intento que se está viendo
    forked_from_conversation_id = Column(String(36), nullable=True, index=True)
    forked_from_message_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # soft-delete; null = activa

    messages = relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.created_at",
        cascade="all, delete-orphan",
    )


class Rule(Base):
    """Regla reutilizable de la biblioteca. scope=chat (conversación/modelo) o planner (ilustración).

    user_id NULL = catálogo compartido (builtin). user_id set = regla privada del usuario.
    """
    __tablename__ = "rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(512), nullable=False, default="")
    content = Column(Text, nullable=False, default="")
    scope = Column(String(32), nullable=False, default="chat")  # chat | planner
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    role = Column(String(32), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    # Título derivado de la primera frase del contenido (solo alfanumérico); buscable/ordenable.
    title = Column(String(80), nullable=True, index=True)
    instruction_override = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Debug: payload enviado a Ollama (solo mensajes assistant)
    debug_request_json = Column(Text, nullable=True)
    # Debug: raw del stream (líneas NDJSON enviadas al cliente)
    debug_response_raw = Column(Text, nullable=True)

    conversation = relationship("Conversation", back_populates="messages")
    illustrated_images = relationship(
        "IllustratedImage",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class IllustratedImage(Base):
    """Metadatos de una imagen generada (params Forge + prompt) ligada a un mensaje."""

    __tablename__ = "illustrated_images"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(
        String(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = Column(String(255), nullable=False, unique=True)
    scene_id = Column(String(64), nullable=True)
    mode = Column(String(32), nullable=False, default="txt2img")
    params_json = Column(Text, nullable=False, default="{}")
    prompt_model = Column(String(128), nullable=True)
    prompt_provider = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("Message", back_populates="illustrated_images")


class ImageGenerationJob(Base):
    """Trabajo encolado para generar una imagen con Forge."""

    __tablename__ = "image_generation_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id = Column(
        String(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scene_id = Column(String(64), nullable=False)
    batch_id = Column(String(36), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    forge_prompt = Column(Text, nullable=False, default="")
    forge_mode = Column(String(32), nullable=False, default="txt2img")
    forge_body_json = Column(Text, nullable=False, default="{}")
    rules_json = Column(Text, nullable=False, default="{}")
    prompt_model = Column(String(128), nullable=True)
    prompt_provider = Column(String(64), nullable=True)
    retries_remaining = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    result_filename = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class WorkspaceProfileRecord(Base):
    """Perfil de workspace: snapshot JSON de modelo, reglas, params e imágenes."""

    __tablename__ = "workspace_profiles"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_workspace_profiles_user_name"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(80), nullable=False)
    snapshot_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlannerRulePresetRecord(Base):
    """Preset nombrado de la selección de reglas del planificador."""

    __tablename__ = "planner_rule_presets"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_planner_rule_presets_user_name"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(80), nullable=False)
    snapshot_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
