"""Endpoint del flujo prompt generator (txt2img)."""

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db
from app.ownership import require_owned_conversation
from app.routers.api_conversations import _message_in_chat
from app.schemas import MessageInChat
from app.services.prompt_generator.turn import run_turn

router = APIRouter(prefix="/api", tags=["prompt-generator"])


class PromptGeneratorTurnIn(BaseModel):
    message: Optional[str] = None
    force: bool = False
    model_params: Optional[dict[str, Any]] = Field(
        default=None,
        description="Params de generación vivos de la UI (prioridad sobre los de la conversación).",
    )
    provider: Optional[str] = Field(default=None, description="Proveedor vivo de la UI; manda y se persiste.")
    model: Optional[str] = Field(default=None, description="Modelo vivo de la UI; manda y se persiste.")

    @model_validator(mode="before")
    @classmethod
    def _accept_content_alias(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("message") is None and data.get("content") is not None:
            out = dict(data)
            out["message"] = out.get("content")
            return out
        return data


class PromptGeneratorTurnOut(BaseModel):
    assistant_text: str
    phase: Literal["interview", "prompt"]
    prompt: Optional[str] = None
    brief: dict[str, Any]
    user_message: Optional[MessageInChat] = None
    assistant_message: MessageInChat


@router.post(
    "/conversations/{conversation_id}/prompt-generator/turn",
    response_model=PromptGeneratorTurnOut,
)
def prompt_generator_turn(
    conversation_id: str,
    body: PromptGeneratorTurnIn,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    require_owned_conversation(db, conversation_id, user)
    try:
        result = run_turn(
            db,
            conversation_id,
            message=body.message,
            force=body.force,
            model_params=body.model_params,
            provider=body.provider,
            model_id=body.model,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Respuesta inválida del modelo: {exc}")

    return PromptGeneratorTurnOut(
        assistant_text=result.assistant_text,
        phase=result.phase,  # type: ignore[arg-type]
        prompt=result.prompt,
        brief=result.brief,
        user_message=_message_in_chat(result.user_message) if result.user_message else None,
        assistant_message=_message_in_chat(result.assistant_message),
    )
