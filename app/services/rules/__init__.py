"""Biblioteca de reglas parametrizada por ámbito (chat | planner)."""

from app.services.rules.compose import concat_instruction_texts
from app.services.rules.models import RULE_SCOPES, SCOPE_CHAT, SCOPE_PLANNER
from app.services.rules.seed import (
    FLUX_PROMPT_GUIDE_RULE_ID,
    KREA2_PHOTOREALISM_RULE_ID,
    KREA2_POV_GUIDE_RULE_ID,
    seed_builtin_rules,
)

__all__ = [
    "RULE_SCOPES",
    "SCOPE_CHAT",
    "SCOPE_PLANNER",
    "FLUX_PROMPT_GUIDE_RULE_ID",
    "KREA2_PHOTOREALISM_RULE_ID",
    "KREA2_POV_GUIDE_RULE_ID",
    "concat_instruction_texts",
    "seed_builtin_rules",
]
