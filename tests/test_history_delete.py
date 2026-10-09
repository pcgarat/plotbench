"""Borrado del historial: conversación completa o subárbol propio de un fork."""
from app import crud
from app.models import Conversation
from app.services import history_delete as hd


def _thread(db, title="Origen"):
    origin = crud.create_conversation(db, title=title, model_id="m")
    u1 = crud.add_message(db, origin.id, "user", "p1")
    a1 = crud.add_message(db, origin.id, "assistant", "r1")
    u2 = crud.add_message(db, origin.id, "user", "p2")
    a2 = crud.add_message(db, origin.id, "assistant", "r2")
    return origin, {"u1": u1, "a1": a1, "u2": u2, "a2": a2}


def _own_ids(db, conversation_id):
    return {m.id for m in crud.get_messages(db, conversation_id)}


def test_subtree_ids_incluye_nodo_y_descendientes(db_session):
    _, msgs = _thread(db_session)
    own = crud.get_messages(db_session, msgs["a1"].conversation_id)
    ids = hd.subtree_message_ids(own, msgs["a1"].id)
    assert ids == {msgs["a1"].id, msgs["u2"].id, msgs["a2"].id}


def test_borrar_nodo_raiz_manda_conversacion_y_forks_descendientes_a_papelera(db_session):
    origin, msgs = _thread(db_session)
    child = crud.fork_conversation(db_session, origin.id, msgs["a1"].id)
    crud.add_message(db_session, child.id, "user", "fq")
    fork_a = crud.add_message(db_session, child.id, "assistant", "fr")
    grand = crud.fork_conversation(db_session, child.id, fork_a.id)
    crud.add_message(db_session, grand.id, "user", "gq")
    crud.add_message(db_session, grand.id, "assistant", "gr")

    result = hd.delete_history_nodes(db_session, [msgs["a2"].id])

    assert set(result.trashed_conversation_ids) == {origin.id, child.id, grand.id}
    assert result.deleted_message_ids == []
    assert crud.get_conversation(db_session, origin.id) is None
    assert crud.get_conversation(db_session, child.id) is None
    assert crud.get_conversation(db_session, grand.id) is None
    origin_row = (
        db_session.query(Conversation).filter(Conversation.id == origin.id).one()
    )
    assert origin_row.deleted_at is not None
    assert _own_ids(db_session, origin.id) == {
        msgs["u1"].id,
        msgs["a1"].id,
        msgs["u2"].id,
        msgs["a2"].id,
    }


def test_borrar_nodo_fork_solo_subarbol_propio_y_forks_colgados(db_session):
    origin, msgs = _thread(db_session)
    child = crud.fork_conversation(db_session, origin.id, msgs["a1"].id)
    fu1 = crud.add_message(db_session, child.id, "user", "fq1")
    fa1 = crud.add_message(db_session, child.id, "assistant", "fr1")
    fu2 = crud.add_message(db_session, child.id, "user", "fq2")
    fa2 = crud.add_message(db_session, child.id, "assistant", "fr2")
    fu1_id, fa1_id, fu2_id, fa2_id = fu1.id, fa1.id, fu2.id, fa2.id
    grand = crud.fork_conversation(db_session, child.id, fa2.id)
    crud.add_message(db_session, grand.id, "user", "gq")
    crud.add_message(db_session, grand.id, "assistant", "gr")
    grand_id = grand.id

    result = hd.delete_history_nodes(db_session, [fa2_id])

    assert crud.get_conversation(db_session, grand_id) is None
    assert crud.get_conversation(db_session, origin.id) is not None
    assert crud.get_conversation(db_session, child.id) is not None
    remaining = _own_ids(db_session, child.id)
    assert fa1_id in remaining
    assert fu1_id in remaining
    assert fa2_id not in remaining
    assert fu2_id not in remaining
    assert set(result.trashed_conversation_ids) == {grand_id}
    assert set(result.deleted_message_ids) == {fu2_id, fa2_id}
    assert _own_ids(db_session, origin.id) == {
        msgs["u1"].id,
        msgs["a1"].id,
        msgs["u2"].id,
        msgs["a2"].id,
    }


def test_borrar_primer_assistant_del_fork_vacia_y_tira_la_variante(db_session):
    origin, msgs = _thread(db_session)
    child = crud.fork_conversation(db_session, origin.id, msgs["a1"].id)
    crud.add_message(db_session, child.id, "user", "fq")
    fa = crud.add_message(db_session, child.id, "assistant", "fr")

    result = hd.delete_history_nodes(db_session, [fa.id])

    assert child.id in result.trashed_conversation_ids
    assert crud.get_conversation(db_session, child.id) is None
    assert crud.get_conversation(db_session, origin.id) is not None
    assert _own_ids(db_session, origin.id) == {
        msgs["u1"].id,
        msgs["a1"].id,
        msgs["u2"].id,
        msgs["a2"].id,
    }


def test_multiselect_deduplica_misma_conversacion_raiz(db_session):
    origin, msgs = _thread(db_session)
    other, other_msgs = _thread(db_session, title="Otra")

    result = hd.delete_history_nodes(db_session, [msgs["a1"].id, msgs["a2"].id, other_msgs["a1"].id])

    assert set(result.trashed_conversation_ids) == {origin.id, other.id}
    assert result.deleted_message_ids == []


def test_ids_inexistentes_no_tocan_nada(db_session):
    origin, msgs = _thread(db_session)
    result = hd.delete_history_nodes(db_session, ["no-existe"])
    assert result.trashed_conversation_ids == []
    assert result.deleted_message_ids == []
    assert crud.get_conversation(db_session, origin.id) is not None
    assert msgs["a1"].id in _own_ids(db_session, origin.id)
