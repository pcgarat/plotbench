"""Reglas builtin de la biblioteca. FLUX y fotorrealismo Krea 2 no se pisan; la guía POV se reescribe desde fichero."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Rule
from app.services.rules.models import SCOPE_PLANNER

logger = logging.getLogger(__name__)

FLUX_PROMPT_GUIDE_RULE_ID = "a8f3c2e1-4b5d-4e6a-9c1f-7d2e8b0a4f31"
FLUX_PROMPT_GUIDE_TITLE = "Guía prompts FLUX"
KREA2_POV_GUIDE_RULE_ID = "2263d058-31a1-4249-81c2-bad16367b43b"
KREA2_POV_GUIDE_TITLE = "Guía Krea 2 POV"
KREA2_PHOTOREALISM_RULE_ID = "7b9e4c12-8a3d-4f61-9e2b-5c8d1a0f6e47"
KREA2_PHOTOREALISM_TITLE = "KREA 2 - FOTOREALISMO"

_SEED_DIR = Path(__file__).resolve().parents[3] / "config" / "seed"
FLUX_PROMPT_GUIDE_PATH = _SEED_DIR / "planner_flux_prompts.md"
KREA2_POV_GUIDE_PATH = _SEED_DIR / "planner_krea2_pov_prompts.md"
KREA2_PHOTOREALISM_PATH = _SEED_DIR / "planner_krea2_photorealism.md"

_BUILTIN_PLANNER_RULES = (
    (FLUX_PROMPT_GUIDE_RULE_ID, FLUX_PROMPT_GUIDE_TITLE, FLUX_PROMPT_GUIDE_PATH, False),
    (KREA2_POV_GUIDE_RULE_ID, KREA2_POV_GUIDE_TITLE, KREA2_POV_GUIDE_PATH, True),
    (KREA2_PHOTOREALISM_RULE_ID, KREA2_PHOTOREALISM_TITLE, KREA2_PHOTOREALISM_PATH, False),
)


def seed_builtin_rules(db: Session) -> int:
    """Crea reglas builtin que aún no existen. La guía POV se reescribe desde fichero."""
    created = 0
    for rule_id, title, path, update_existing in _BUILTIN_PLANNER_RULES:
        created += ensure_rule_from_file(
            db,
            rule_id=rule_id,
            title=title,
            path=path,
            scope=SCOPE_PLANNER,
            update_existing=update_existing,
        )
    return created


def ensure_rule_from_file(
    db: Session,
    *,
    rule_id: str,
    title: str,
    path: Path,
    scope: str,
    update_existing: bool = False,
) -> int:
    """Inserta una regla si falta el id. 1 si creó, 0 si ya estaba, faltaba fichero o solo actualizó."""
    existing = db.query(Rule).filter(Rule.id == rule_id).first()
    if existing is not None and not update_existing:
        return 0
    if not path.is_file():
        logger.warning("Seed de regla omitido: no existe %s", path)
        return 0
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        logger.warning("Seed de regla omitido: fichero vacío %s", path)
        return 0
    if existing is not None:
        if existing.content != content or existing.title != title:
            existing.content = content
            existing.title = title
            db.commit()
        return 0
    db.add(Rule(id=rule_id, title=title, content=content, scope=scope))
    db.commit()
    return 1
