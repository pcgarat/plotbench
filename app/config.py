import os
from pathlib import Path

from pydantic import field_validator
from pydantic import Field
from pydantic_settings import BaseSettings

# Raíz del proyecto (donde está .env), para cargar .env aunque se arranque desde otro directorio
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_env_files_into_os() -> None:
    """
    Carga .env y .env.local en os.environ (solo claves que aún no estén definidas).
    Así, tanto si se arranca con run.py como con uvicorn app.main:app, el proceso
    tiene todas las variables y el sync puede llevarlas al .env si faltan (p. ej. MANCER_API_KEY).
    """
    for name in (".env", ".env.local"):
        path = _PROJECT_ROOT / name
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    if key and key not in os.environ:
                        value = value.strip().strip('"').strip("'")
                        os.environ[key] = value
        except OSError:
            pass


_load_env_files_into_os()

# Variables de entorno que, si existen en el sistema al arrancar y no están ya en .env, se añaden al archivo
ENV_VARS_TO_SYNC = [
    "PYTHON_VERSION",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_ORGANIZATION_ID",
    "OPENAI_PROJECT_ID",
    "CHROMA_HOST",
    "MANCER_API_KEY",
    "ABLIT_KEY",
    "ABLIT_BASE_URL",
    "NAN_API_KEY",
    "NAN_BASE_URL",
    "OLLAMA_HOST",
    "EMBEDDINGS_PROVIDER",
    "OLLAMA_EMBEDDING_MODEL",
    "DEFAULT_LLM_PROVIDER",
    "OLLAMA_HISTORY_TURNS",
    "DATABASE_URL",
    "ADMIN_PASSWORD",
    "VERBOSE",
    "FORGE_BASE_URL",
    "FORGE_DATA_PATH",
    "FORGE_STYLE_INIT_DIR",
    "FORGE_TIMEOUT_SECONDS",
    "FORGE_REACTOR_SOURCE_IMAGE",
    "FORGE_REACTOR_MODEL",
    "FORGE_REACTOR_SOURCE_FACES_INDEX",
    "FORGE_REACTOR_FACE_INDEX",
    "FORGE_REACTOR_UPSCALER",
    "FORGE_REACTOR_SCALE",
    "FORGE_REACTOR_UPSCALE_VISIBILITY",
    "FORGE_REACTOR_FACE_RESTORER",
    "FORGE_REACTOR_RESTORER_VISIBILITY",
    "FORGE_REACTOR_CODEFORMER_WEIGHT",
    "FORGE_REACTOR_RESTORE_FIRST",
    "FORGE_REACTOR_GENDER_SOURCE",
    "FORGE_REACTOR_GENDER_TARGET",
    "FORGE_REACTOR_DEVICE",
    "FORGE_REACTOR_MASK_FACE",
    "FORGE_REACTOR_SELECT_SOURCE",
    "FORGE_REACTOR_FACE_MODEL",
    "FORGE_REACTOR_SOURCE_FOLDER",
    "FORGE_REACTOR_RANDOM_IMAGE",
    "FORGE_REACTOR_UPSCALE_FORCE",
]


class Settings(BaseSettings):
    ollama_host: str = "http://localhost:11434"
    database_url: str = "sqlite:///./chatbot.db"
    admin_password: str = Field(default="admin", validation_alias="ADMIN_PASSWORD")
    verbose: bool = Field(False, validation_alias="VERBOSE")  # VERBOSE=1 o -v: RAG + LLM + ScenePlanner + Forge Neo en stderr
    # RAG con ChromaDB + embeddings con Ollama (modelo local)
    chroma_host: str = Field(default="http://localhost:8001", validation_alias="CHROMA_HOST")
    ollama_embedding_model: str = Field(
        default="mxbai-embed-large:latest",
        validation_alias="OLLAMA_EMBEDDING_MODEL",
    )
    # Por defecto se usa Ollama para embeddings. Si quieres OpenAI: EMBEDDINGS_PROVIDER=openai y OPENAI_API_KEY
    embeddings_provider: str = Field(default="ollama", validation_alias="EMBEDDINGS_PROVIDER")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com", validation_alias="OPENAI_BASE_URL")
    # Opcionales: organización y proyecto (usage se atribuye al proyecto). Ver https://developers.openai.com/api/reference/overview/
    openai_organization_id: str = Field(default="", validation_alias="OPENAI_ORGANIZATION_ID")
    openai_project_id: str = Field(
        default="proj_Db2LsLDFkhd2rVfSMJrSCE5j",
        validation_alias="OPENAI_PROJECT_ID",
    )
    # Número de pares usuario-asistente a enviar a Ollama como historial (0 = sin historial). Por defecto 10.
    ollama_history_turns: int = Field(default=10, validation_alias="OLLAMA_HISTORY_TURNS")

    # Multi-provider LLM
    default_llm_provider: str = Field(default="ollama", validation_alias="DEFAULT_LLM_PROVIDER")
    # Mancer (https://mancer.tech) - API compatible con OpenAI
    mancer_api_key: str = Field(default="", validation_alias="MANCER_API_KEY")
    # abliteration.ai (https://docs.abliteration.ai/) - API compatible con OpenAI
    ablit_key: str = Field(default="", validation_alias="ABLIT_KEY")
    ablit_base_url: str = Field(
        default="https://api.abliteration.ai",
        validation_alias="ABLIT_BASE_URL",
    )
    # NaN Builders (https://nan.builders/docs) - API compatible con OpenAI. base_url sin sufijo /v1
    nan_api_key: str = Field(default="", validation_alias="NAN_API_KEY")
    nan_base_url: str = Field(default="https://api.nan.builders", validation_alias="NAN_BASE_URL")

    # Forge Neo (ilustración de relatos) — ReplayLastGeneration
    forge_base_url: str = Field(
        default="http://127.0.0.1:7860",
        validation_alias="FORGE_BASE_URL",
    )
    forge_data_path: str = Field(default="", validation_alias="FORGE_DATA_PATH")
    forge_style_init_dir: str = Field(default="", validation_alias="FORGE_STYLE_INIT_DIR")
    forge_timeout_seconds: float = Field(
        default=600.0,
        validation_alias="FORGE_TIMEOUT_SECONDS",
    )
    forge_reactor_source_image: str = Field(
        default="",
        validation_alias="FORGE_REACTOR_SOURCE_IMAGE",
    )
    forge_reactor_model: str = Field(
        default="inswapper_128.onnx",
        validation_alias="FORGE_REACTOR_MODEL",
    )
    forge_reactor_face_restorer: str = Field(
        default="CodeFormer",
        validation_alias="FORGE_REACTOR_FACE_RESTORER",
    )
    forge_reactor_restorer_visibility: float = Field(
        default=1.0,
        validation_alias="FORGE_REACTOR_RESTORER_VISIBILITY",
    )
    forge_reactor_upscaler: str = Field(
        default="None",
        validation_alias="FORGE_REACTOR_UPSCALER",
    )
    forge_reactor_scale: float = Field(
        default=1.0,
        validation_alias="FORGE_REACTOR_SCALE",
    )
    forge_reactor_source_faces_index: str = Field(
        default="0",
        validation_alias="FORGE_REACTOR_SOURCE_FACES_INDEX",
    )
    forge_reactor_face_index: str = Field(
        default="0",
        validation_alias="FORGE_REACTOR_FACE_INDEX",
    )
    forge_reactor_upscale_visibility: float = Field(
        default=1.0,
        validation_alias="FORGE_REACTOR_UPSCALE_VISIBILITY",
    )
    forge_reactor_codeformer_weight: float = Field(
        default=0.5,
        validation_alias="FORGE_REACTOR_CODEFORMER_WEIGHT",
    )
    forge_reactor_restore_first: int = Field(
        default=1,
        validation_alias="FORGE_REACTOR_RESTORE_FIRST",
    )
    forge_reactor_gender_source: int = Field(
        default=0,
        validation_alias="FORGE_REACTOR_GENDER_SOURCE",
    )
    forge_reactor_gender_target: int = Field(
        default=0,
        validation_alias="FORGE_REACTOR_GENDER_TARGET",
    )
    forge_reactor_device: str = Field(
        default="CUDA",
        validation_alias="FORGE_REACTOR_DEVICE",
    )
    forge_reactor_mask_face: int = Field(
        default=1,
        validation_alias="FORGE_REACTOR_MASK_FACE",
    )
    forge_reactor_select_source: int = Field(
        default=0,
        validation_alias="FORGE_REACTOR_SELECT_SOURCE",
    )
    forge_reactor_face_model: str = Field(
        default="",
        validation_alias="FORGE_REACTOR_FACE_MODEL",
    )
    forge_reactor_source_folder: str = Field(
        default="",
        validation_alias="FORGE_REACTOR_SOURCE_FOLDER",
    )
    forge_reactor_random_image: int = Field(
        default=0,
        validation_alias="FORGE_REACTOR_RANDOM_IMAGE",
    )
    forge_reactor_upscale_force: int = Field(
        default=0,
        validation_alias="FORGE_REACTOR_UPSCALE_FORCE",
    )

    @field_validator("ollama_history_turns", mode="before")
    @classmethod
    def parse_ollama_history_turns(cls, v):
        """Si está vacío o no es válido, devuelve 10."""
        if v is None or v == "":
            return 10
        try:
            n = int(v)
            return max(0, n)  # 0 = sin historial; valores negativos se convierten en 0
        except (ValueError, TypeError):
            return 10

    class Config:
        env_file = str(_PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        # Asegurar que se lean las variables del .env (no solo del entorno del proceso)
        extra = "ignore"


def _escape_env_value(value: str) -> str:
    """Escapa un valor para una línea KEY=value en .env (comillas si hace falta)."""
    if any(c in value for c in " \t\n\"'#"):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def sync_env_to_dotenv(*, skip_if_pytest: bool = True) -> None:
    """
    Recorre las variables de ENV_VARS_TO_SYNC que existen en os.environ y, solo si esa
    variable no está ya en el .env, la añade al final del archivo. No borra ni modifica
    ninguna línea existente.
    Si skip_if_pytest es True (por defecto), no hace nada cuando se ejecuta bajo pytest.
    """
    if skip_if_pytest and os.environ.get("PYTEST_CURRENT_TEST"):
        return
    env_path = _PROJECT_ROOT / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines_all: list[str] = []
    keys_in_file: set[str] = set()
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                lines_all.append(line.rstrip("\n"))
                stripped = line.strip()
                if "=" in stripped and not stripped.startswith("#"):
                    key = stripped.split("=", 1)[0].strip()
                    if key and not key.startswith("#"):
                        keys_in_file.add(key)
    new_lines = []
    for var in ENV_VARS_TO_SYNC:
        if var in os.environ and os.environ[var] is not None and var not in keys_in_file:
            val = _escape_env_value(os.environ[var])
            new_lines.append(f"{var}={val}")
    if new_lines:
        parts = lines_all + ([""] if lines_all else []) + new_lines
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts) + "\n")


settings = Settings()
