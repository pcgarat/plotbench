from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# SQLite: varios writers (stream NDJSON + UI) sin 'database is locked' inmediato.
# timeout = espera del driver; busy_timeout/WAL = pragmas por conexión.
connect_args = {}
_SQLITE_BUSY_TIMEOUT_MS = 30_000
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = _SQLITE_BUSY_TIMEOUT_MS / 1000.0

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_on_connect(dbapi_conn, _connection_record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
        cur.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401
    from app import models_user  # noqa: F401
    Base.metadata.create_all(bind=engine)
    # Multi-usuario: columnas user_id
    with engine.connect() as conn:
        for table, col_def in (
            ("conversations", "user_id VARCHAR(36)"),
            ("rules", "user_id VARCHAR(36)"),
            ("workspace_profiles", "user_id VARCHAR(36)"),
            ("planner_rule_presets", "user_id VARCHAR(36)"),
        ):
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_def}"))
                conn.commit()
            except Exception:
                conn.rollback()
    # Migración: añadir inject_instruction_every si no existe
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN inject_instruction_every INTEGER"))
            conn.commit()
        except Exception:
            conn.rollback()
    # Migración: añadir debug_request_json y debug_response_raw en messages
    with engine.connect() as conn:
        for col in ("debug_request_json", "debug_response_raw"):
            try:
                conn.execute(text(f"ALTER TABLE messages ADD COLUMN {col} TEXT"))
                conn.commit()
            except Exception:
                conn.rollback()
    # Migración: añadir provider en conversations (default "ollama")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN provider VARCHAR(64) DEFAULT 'ollama' NOT NULL"))
            conn.commit()
        except Exception:
            conn.rollback()
    # Migración: añadir model_params en conversations (JSON guardado por conversación)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN model_params TEXT"))
            conn.commit()
        except Exception:
            conn.rollback()
    # Migración: añadir system_instructions en conversations (JSON lista de reglas) - legado
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN system_instructions TEXT"))
            conn.commit()
        except Exception:
            conn.rollback()
    # Migración: añadir instruction_ids (solo referencias a rules; fuente de verdad)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN instruction_ids TEXT"))
            conn.commit()
        except Exception:
            conn.rollback()
    # Migración: history_turns en conversations (pares user+assistant a enviar en el prompt; default 5)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN history_turns INTEGER"))
            conn.commit()
        except Exception:
            conn.rollback()
    # Migración: instruction_override en conversations (último valor por conversación para instrucción por mensaje)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN instruction_override TEXT"))
            conn.commit()
        except Exception:
            conn.rollback()
    # Crear tabla rules (biblioteca de reglas unificada)
    Base.metadata.create_all(bind=engine)
    # Migración: last_message_at para ordenar por última escritura, no por último click
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN last_message_at DATETIME"))
            conn.commit()
        except Exception:
            conn.rollback()
        else:
            try:
                conn.execute(text(
                    "UPDATE conversations SET last_message_at = (SELECT MAX(created_at) FROM messages WHERE messages.conversation_id = conversations.id)"
                ))
                conn.commit()
            except Exception:
                conn.rollback()
    # Soft-delete de conversaciones (papelera)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN deleted_at DATETIME"))
            conn.commit()
        except Exception:
            conn.rollback()
    # Ámbito de reglas: chat (default) | planner
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE rules ADD COLUMN scope VARCHAR(32) DEFAULT 'chat' NOT NULL"))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("UPDATE rules SET scope = 'chat' WHERE scope IS NULL OR scope = ''"))
            conn.commit()
        except Exception:
            conn.rollback()
    # Árbol de intentos: parent_id en messages y hoja activa en conversations
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE messages ADD COLUMN parent_id VARCHAR(36)"))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN active_leaf_message_id VARCHAR(36)"))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conv_ids = conn.execute(
                text(
                    """
                    SELECT c.id FROM conversations c
                    WHERE EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id)
                      AND NOT EXISTS (
                        SELECT 1 FROM messages m2
                        WHERE m2.conversation_id = c.id AND m2.parent_id IS NOT NULL
                      )
                    """
                )
            ).fetchall()
            for (cid,) in conv_ids:
                rows = conn.execute(
                    text(
                        "SELECT id FROM messages WHERE conversation_id = :cid ORDER BY created_at, id"
                    ),
                    {"cid": cid},
                ).fetchall()
                prev = None
                for (mid,) in rows:
                    if prev is not None:
                        conn.execute(
                            text("UPDATE messages SET parent_id = :pid WHERE id = :mid"),
                            {"pid": prev, "mid": mid},
                        )
                    prev = mid
                if prev is not None:
                    conn.execute(
                        text(
                            "UPDATE conversations SET active_leaf_message_id = :leaf "
                            "WHERE id = :cid AND active_leaf_message_id IS NULL"
                        ),
                        {"leaf": prev, "cid": cid},
                    )
            conn.commit()
        except Exception:
            conn.rollback()
    # Variante: historial resuelto desde un mensaje de otra conversación
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN forked_from_conversation_id VARCHAR(36)"))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN forked_from_message_id VARCHAR(36)"))
            conn.commit()
        except Exception:
            conn.rollback()
    # LLM que planificó el prompt de cada imagen ilustrada
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE illustrated_images ADD COLUMN prompt_model VARCHAR(128)"))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE illustrated_images ADD COLUMN prompt_provider VARCHAR(64)"))
            conn.commit()
        except Exception:
            conn.rollback()
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE conversations ADD COLUMN auto_title BOOLEAN NOT NULL DEFAULT 0"
            ))
            conn.commit()
        except Exception:
            conn.rollback()
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN images TEXT"))
            conn.commit()
        except Exception:
            conn.rollback()
    with engine.connect() as conn:
        try:
            conn.execute(
                text(
                    "ALTER TABLE conversations ADD COLUMN kind VARCHAR(32) DEFAULT 'chat' NOT NULL"
                )
            )
            conn.commit()
        except Exception:
            conn.rollback()
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN prompt_brief TEXT"))
            conn.commit()
        except Exception:
            conn.rollback()
    # Título de mensaje (primera frase alfanumérica): columna + backfill único.
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE messages ADD COLUMN title VARCHAR(80)"))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            from app.services.message_title import derive_message_title

            pending = conn.execute(
                text("SELECT id, content FROM messages WHERE title IS NULL")
            ).fetchall()
            for mid, content in pending:
                conn.execute(
                    text("UPDATE messages SET title = :t WHERE id = :mid"),
                    {"t": derive_message_title(content), "mid": mid},
                )
            conn.commit()
        except Exception:
            conn.rollback()
    # Backfill: los títulos antiguos se guardaron sin espacios ("Holamundo"); se recalculan
    # los que no tienen espacios pero cuyo contenido sí, y solo mientras queden filas así.
    with engine.connect() as conn:
        try:
            from app.services.message_title import derive_message_title

            pending = conn.execute(
                text(
                    "SELECT id, content, title FROM messages "
                    "WHERE title IS NULL OR (instr(title, ' ') = 0 AND instr(content, ' ') > 0)"
                )
            ).fetchall()
            for mid, content, stored in pending:
                expected = derive_message_title(content)
                if (stored or "") != expected:
                    conn.execute(
                        text("UPDATE messages SET title = :t WHERE id = :mid"),
                        {"t": expected, "mid": mid},
                    )
            conn.commit()
        except Exception:
            conn.rollback()
