from fastapi import APIRouter, HTTPException


from machine_monitoring_app.database.db_utils import PONY_DATABASE
from machine_monitoring_app.database.pony_models import get_schema_name

ROUTER = APIRouter(
    prefix="/api/v1",
    tags=["Base Routes"],
    responses={404: {"description": "Not found"}})


@ROUTER.get('/get_schema_name')
async def get_schema_name_route():
    schema_name = get_schema_name()
    return {"schema_name": schema_name}
