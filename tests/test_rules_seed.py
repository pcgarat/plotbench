"""Seed de reglas builtin del planificador (guías FLUX, Krea 2 POV y fotorrealismo)."""
from pathlib import Path

from app.crud import delete_rule, get_rule, update_rule
from app.services.rules.models import SCOPE_CHAT, SCOPE_PLANNER
from app.services.rules.seed import (
    FLUX_PROMPT_GUIDE_PATH,
    FLUX_PROMPT_GUIDE_RULE_ID,
    FLUX_PROMPT_GUIDE_TITLE,
    KREA2_PHOTOREALISM_PATH,
    KREA2_PHOTOREALISM_RULE_ID,
    KREA2_PHOTOREALISM_TITLE,
    KREA2_POV_GUIDE_PATH,
    KREA2_POV_GUIDE_RULE_ID,
    KREA2_POV_GUIDE_TITLE,
    NO_MORALIZE_PATH,
    NO_MORALIZE_RULE_ID,
    NO_MORALIZE_TITLE,
    ensure_rule_from_file,
    seed_builtin_rules,
)

_SEED = Path(__file__).resolve().parents[1] / "config" / "seed" / "planner_flux_prompts.md"
_KREA2_SEED = Path(__file__).resolve().parents[1] / "config" / "seed" / "planner_krea2_pov_prompts.md"
_KREA2_PHOTO_SEED = Path(__file__).resolve().parents[1] / "config" / "seed" / "planner_krea2_photorealism.md"
_NO_MORALIZE_SEED = (
    Path(__file__).resolve().parents[1] / "config" / "seed" / "chat_no_moralize.md"
)


def _assert_planner_prompt_contract(text: str) -> None:
    assert "SOLO al string `prompt`" in text
    assert "JSON del planificador" in text
    assert "No preguntes al usuario" in text
    assert "negative prompt" in text.lower()
    assert "No uses formato markdown de respuesta" in text
    assert "preguntar antes de generar" not in text.lower()
    assert "¿Quieres un cartel" not in text
    assert "illustrate" in text
    assert len(text) < 12_000


def test_seed_file_is_planner_contract_not_raw_download():
    text = _SEED.read_text(encoding="utf-8")
    _assert_planner_prompt_contract(text)
    assert "NO decide qué momentos ilustrar" in text
    assert "no suavices ni eufemices" in text
    assert "salvo que el relato" in text


def test_krea2_pov_seed_file_is_planner_contract():
    text = _KREA2_SEED.read_text(encoding="utf-8")
    _assert_planner_prompt_contract(text)
    assert "Krea 2" in text
    assert "Describe las imágenes así" in text
    assert "Empieza cada prompt con `POV.`" in text
    assert "ahead" in text
    assert "filling the view" in text
    assert "looks into the viewer's eyes" in text
    assert "shot of Paco" not in text
    assert "No uses:" not in text
    assert "Cómo se describe" not in text
    assert "No basta" not in text
    assert "moodboard" not in text.lower()
    assert "style reference" not in text.lower()
    assert len(text) < 4000


def test_no_moralize_seed_file_is_chat_contract():
    text = _NO_MORALIZE_SEED.read_text(encoding="utf-8")
    assert "moral" in text.lower()
    assert "No añadas juicios morales" in text
    assert "como IA no puedo" in text
    assert len(text) < 2000


def test_krea2_photorealism_seed_file_is_planner_contract():
    text = _KREA2_PHOTO_SEED.read_text(encoding="utf-8")
    _assert_planner_prompt_contract(text)
    assert "Krea 2" in text
    assert "KREA 2 - FOTOREALISMO" in text
    assert "photograph" in text
    assert "shallow depth of field" in text
    assert "Forge" not in text
    assert "CFG" not in text
    assert "moodboard" not in text.lower()
    assert "style reference" not in text.lower()
    assert "Convierte esta narrativa" not in text
    assert len(text) < 6000


def test_seed_creates_planner_rule_when_missing(db_session):
    assert get_rule(db_session, FLUX_PROMPT_GUIDE_RULE_ID) is None
    assert get_rule(db_session, KREA2_POV_GUIDE_RULE_ID) is None
    assert get_rule(db_session, NO_MORALIZE_RULE_ID) is None
    assert get_rule(db_session, KREA2_PHOTOREALISM_RULE_ID) is None
    created = seed_builtin_rules(db_session)
    assert created == 4
    rule = get_rule(db_session, FLUX_PROMPT_GUIDE_RULE_ID)
    assert rule is not None
    assert rule.title == FLUX_PROMPT_GUIDE_TITLE
    assert rule.scope == SCOPE_PLANNER
    assert "prosa" in rule.content.lower() or "prompt" in rule.content.lower()
    assert rule.content == FLUX_PROMPT_GUIDE_PATH.read_text(encoding="utf-8").strip()
    krea = get_rule(db_session, KREA2_POV_GUIDE_RULE_ID)
    assert krea is not None
    assert krea.title == KREA2_POV_GUIDE_TITLE
    assert krea.scope == SCOPE_PLANNER
    assert krea.content == KREA2_POV_GUIDE_PATH.read_text(encoding="utf-8").strip()
    no_moralize = get_rule(db_session, NO_MORALIZE_RULE_ID)
    assert no_moralize is not None
    assert no_moralize.title == NO_MORALIZE_TITLE
    assert no_moralize.scope == SCOPE_CHAT
    assert no_moralize.content == NO_MORALIZE_PATH.read_text(encoding="utf-8").strip()
    photo = get_rule(db_session, KREA2_PHOTOREALISM_RULE_ID)
    assert photo is not None
    assert photo.title == KREA2_PHOTOREALISM_TITLE
    assert photo.scope == SCOPE_PLANNER
    assert photo.content == KREA2_PHOTOREALISM_PATH.read_text(encoding="utf-8").strip()


def test_seed_is_idempotent_and_does_not_overwrite(db_session):
    seed_builtin_rules(db_session)
    update_rule(db_session, FLUX_PROMPT_GUIDE_RULE_ID, content="editado por el usuario")
    update_rule(db_session, KREA2_PHOTOREALISM_RULE_ID, content="fotorrealismo editado")
    created = seed_builtin_rules(db_session)
    assert created == 0
    rule = get_rule(db_session, FLUX_PROMPT_GUIDE_RULE_ID)
    assert rule.content == "editado por el usuario"
    assert rule.title == FLUX_PROMPT_GUIDE_TITLE
    photo = get_rule(db_session, KREA2_PHOTOREALISM_RULE_ID)
    assert photo.content == "fotorrealismo editado"
    assert photo.title == KREA2_PHOTOREALISM_TITLE


def test_seed_refreshes_krea2_pov_guide_from_file(db_session):
    seed_builtin_rules(db_session)
    update_rule(db_session, KREA2_POV_GUIDE_RULE_ID, content="texto viejo y largo de POV")
    assert seed_builtin_rules(db_session) == 0
    krea = get_rule(db_session, KREA2_POV_GUIDE_RULE_ID)
    assert krea.content == KREA2_POV_GUIDE_PATH.read_text(encoding="utf-8").strip()
    assert "filling the view" in krea.content


def test_seed_recreates_after_delete(db_session):
    seed_builtin_rules(db_session)
    assert delete_rule(db_session, FLUX_PROMPT_GUIDE_RULE_ID) is True
    assert seed_builtin_rules(db_session) == 1
    assert get_rule(db_session, FLUX_PROMPT_GUIDE_RULE_ID) is not None


def test_seed_skips_missing_file(db_session, tmp_path):
    missing = tmp_path / "no-existe.md"
    n = ensure_rule_from_file(
        db_session,
        rule_id="11111111-1111-4111-8111-111111111111",
        title="X",
        path=missing,
        scope=SCOPE_PLANNER,
    )
    assert n == 0
    assert get_rule(db_session, "11111111-1111-4111-8111-111111111111") is None


def test_startup_function_seeds_builtin_rules():
    import inspect

    from app.main import startup

    assert "seed_builtin_rules" in inspect.getsource(startup)


def test_startup_seeds_planner_rule_not_chat(client):
    chat = client.get("/api/rules").json()
    assert all(item["id"] != FLUX_PROMPT_GUIDE_RULE_ID for item in chat)
    assert all(item["id"] != KREA2_POV_GUIDE_RULE_ID for item in chat)
    assert all(item["id"] != KREA2_PHOTOREALISM_RULE_ID for item in chat)
    planner = client.get("/api/rules", params={"scope": "planner"}).json()
    match = [item for item in planner if item["id"] == FLUX_PROMPT_GUIDE_RULE_ID]
    assert len(match) == 1
    assert match[0]["title"] == FLUX_PROMPT_GUIDE_TITLE
    assert match[0]["scope"] == SCOPE_PLANNER
    krea = [item for item in planner if item["id"] == KREA2_POV_GUIDE_RULE_ID]
    assert len(krea) == 1
    assert krea[0]["title"] == KREA2_POV_GUIDE_TITLE
    assert krea[0]["scope"] == SCOPE_PLANNER
    photo = [item for item in planner if item["id"] == KREA2_PHOTOREALISM_RULE_ID]
    assert len(photo) == 1
    assert photo[0]["title"] == KREA2_PHOTOREALISM_TITLE
    assert photo[0]["scope"] == SCOPE_PLANNER


def test_startup_seeds_no_moralize_in_chat_scope(client):
    """La regla «No moralizar» es de chat: debe listarse en la biblioteca del panel, no en planner."""
    chat = client.get("/api/rules").json()
    rule = [item for item in chat if item["id"] == NO_MORALIZE_RULE_ID]
    assert len(rule) == 1
    assert rule[0]["title"] == NO_MORALIZE_TITLE
    assert rule[0]["scope"] == SCOPE_CHAT
    planner = client.get("/api/rules", params={"scope": "planner"}).json()
    assert all(item["id"] != NO_MORALIZE_RULE_ID for item in planner)
