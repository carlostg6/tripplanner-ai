"""Lambdas de usuario y preferencias + trigger PostConfirmation de Cognito."""
import logging

from common import db
from common.http import handler, to_plain
from common.validation import validate_preferences, validate_profile

logger = logging.getLogger()


def _ensure_profile(user_id, email=None, name=None):
    item = db.get(user_id, "PROFILE")
    if item:
        return item
    ts = db.now_iso()
    item = {"PK": db.user_pk(user_id), "SK": "PROFILE", "entityType": "USER",
            "userId": user_id, "email": email, "name": name or (email or "").split("@")[0],
            "createdAt": ts, "updatedAt": ts}
    item = {k: v for k, v in item.items() if v is not None}
    db.put(item)
    return item


@handler
def get_profile(req):
    item = _ensure_profile(req.user_id, req.email)
    return 200, {"profile": to_plain(db.clean(item))}


@handler
def update_profile(req):
    data = validate_profile(req.body)
    _ensure_profile(req.user_id, req.email)
    item = db.update(req.user_id, "PROFILE", data)
    return 200, {"profile": to_plain(db.clean(item))}


@handler
def get_preferences(req):
    item = db.get(req.user_id, "PREFS")
    return 200, {"preferences": to_plain(db.clean(item)) if item else {}}


@handler
def put_preferences(req):
    data = validate_preferences(req.body)
    current = db.get(req.user_id, "PREFS") or {}
    ts = db.now_iso()
    item = {**current, **data, "PK": db.user_pk(req.user_id), "SK": "PREFS",
            "entityType": "PREFERENCES", "userId": req.user_id, "updatedAt": ts,
            "createdAt": current.get("createdAt", ts)}
    db.put(item)
    return 200, {"preferences": to_plain(db.clean(item))}


def post_confirmation(event, context):
    """Trigger de Cognito: crea el perfil del usuario al confirmar el registro."""
    try:
        attrs = event["request"]["userAttributes"]
        _ensure_profile(attrs["sub"], attrs.get("email"), attrs.get("name"))
    except Exception:  # nunca bloquear el registro
        logger.exception("No se pudo crear el perfil")
    return event
