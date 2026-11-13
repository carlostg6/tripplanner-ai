"""Acceso a DynamoDB (diseño de tabla única).

PK               SK                       Entidad
USER#<sub>       PROFILE                  Usuario
USER#<sub>       PREFS                    Preferencias
USER#<sub>       TRIP#<tripId>            Viaje
USER#<sub>       ITIN#<tripId>            Itinerario (1 por viaje)
USER#<sub>       RES#<reservationId>      Reserva

GSI1 (reservas por viaje):  GSI1PK = TRIP#<tripId>   GSI1SK = RES#<createdAt>#<id>

La PK siempre es el `sub` del usuario autenticado, así que cada usuario
solo puede leer y modificar sus propios elementos (aislamiento por diseño).
"""
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

from .http import ApiError

_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _table


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def user_pk(user_id):
    return f"USER#{user_id}"


_INTERNAL = {"PK", "SK", "GSI1PK", "GSI1SK"}


def clean(item):
    if not item:
        return item
    return {k: v for k, v in item.items() if k not in _INTERNAL}


def get(user_id, sk):
    return table().get_item(Key={"PK": user_pk(user_id), "SK": sk}).get("Item")


def query_prefix(user_id, prefix, limit=100):
    items, kwargs = [], {
        "KeyConditionExpression": Key("PK").eq(user_pk(user_id)) & Key("SK").begins_with(prefix),
        "Limit": limit,
    }
    while True:
        resp = table().query(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp or len(items) >= limit:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items[:limit]


def query_trip_reservations(trip_id):
    resp = table().query(IndexName="GSI1",
                         KeyConditionExpression=Key("GSI1PK").eq(f"TRIP#{trip_id}"))
    return resp.get("Items", [])


def put_new(item):
    from botocore.exceptions import ClientError
    try:
        table().put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ApiError(409, "ALREADY_EXISTS", "El recurso ya existe.")
        raise


def put(item):
    table().put_item(Item=item)


def update(user_id, sk, fields: dict):
    """Actualiza solo campos permitidos; falla con 404 si el elemento no existe."""
    from botocore.exceptions import ClientError
    fields = {**fields, "updatedAt": now_iso()}
    names, values, sets = {}, {}, []
    for i, (k, v) in enumerate(fields.items()):
        names[f"#f{i}"] = k
        values[f":v{i}"] = v
        sets.append(f"#f{i} = :v{i}")
    try:
        resp = table().update_item(
            Key={"PK": user_pk(user_id), "SK": sk},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression="attribute_exists(PK)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ApiError(404, "NOT_FOUND", "El recurso no existe.")
        raise
    return resp["Attributes"]


def delete(user_id, sk):
    """Elimina un elemento del usuario; 404 si no existe. Devuelve el elemento borrado."""
    from botocore.exceptions import ClientError
    try:
        resp = table().delete_item(Key={"PK": user_pk(user_id), "SK": sk},
                                   ConditionExpression="attribute_exists(PK)", ReturnValues="ALL_OLD")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ApiError(404, "NOT_FOUND", "El recurso no existe.")
        raise
    return resp.get("Attributes")


def require_trip(user_id, trip_id):
    if not trip_id or not isinstance(trip_id, str) or len(trip_id) > 64:
        raise ApiError(400, "VALIDATION_ERROR", "tripId inválido.")
    trip = get(user_id, f"TRIP#{trip_id}")
    if not trip:
        raise ApiError(404, "TRIP_NOT_FOUND", "El viaje no existe o no te pertenece.")
    return trip
