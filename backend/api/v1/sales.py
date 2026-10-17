"""POST /v1/sales-memory (PRD §37) and the Discord import (PRD §17)."""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ...analytics import audit
from ...ingestion.storage import raw_discord_key
from ...ingestion.validation import InvalidUpload, safe_filename, validate_upload
from ...permissions.access import Principal
from ...permissions.roles import P
from ...sales_memory.schema import SalesMemoryRecord
from ..deps import get_services, require
from ..flow import KnowledgeFlow
from ..services import Services

router = APIRouter(prefix="/v1/sales-memory", tags=["sales-memory"])


class SalesMemoryCreate(BaseModel):
    department_id: UUID                  # the PRD names no access rule for sales memories (docs/PRD_GAPS.md)
    record: SalesMemoryRecord            # PRD §16.2 fields


@router.post("", status_code=201)
def create(body: SalesMemoryCreate, actor: Principal = Depends(require(P.MANAGE_SALES_MEMORY)),
           svc: Services = Depends(get_services)):
    text = body.record.embedding_text()
    if not text:
        raise HTTPException(422, "record needs a customer_message or scenario to be searchable")
    rec = body.record.model_copy()
    rec.language = rec.language or svc.language.detect(text)
    mid = svc.ops.insert_sales_memory(rec.model_dump(), svc.embedder.embed(text), svc.embedder.name, body.department_id)
    return {"id": str(mid)}


@router.post("/imports", status_code=202)
def import_conversations(file: UploadFile = File(...), department_id: UUID = Form(...),
                         actor: Principal = Depends(require(P.MANAGE_SALES_MEMORY)),
                         svc: Services = Depends(get_services)):
    """§17.1: drop a JSON file, then process. Stored raw first (§17.2), processed in the background (§47)."""
    data = file.file.read(svc.settings.max_upload_bytes + 1)
    name = safe_filename(file.filename or "discord.json")
    try:
        ext = validate_upload(name, data, svc.settings.max_upload_bytes)
    except InvalidUpload as e:
        raise HTTPException(422, str(e))
    if ext != "json":
        raise HTTPException(422, "Sales chat history must be a JSON file")
    if department_id not in svc.users.all_department_ids():
        raise HTTPException(422, "unknown department")
    job_id = uuid4()
    key = raw_discord_key(job_id, name)
    svc.storage.put(key, data)
    jid = svc.ops.create_job("discord.import", {"s3_key": key, "department_id": str(department_id), "filename": name},
                             actor.user_id)
    svc.queue.send(jid, "discord.import")
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="import_discord_history", filename=name)
    return {"job_id": str(jid)}


@router.get("/imports")
def list_imports(_: Principal = Depends(require(P.MANAGE_SALES_MEMORY)), svc: Services = Depends(get_services)):
    """§17.1: imports with progress (§47) and how many sales memories each stored."""
    return {"imports": svc.ops.sales_memory_imports()}


@router.delete("/imports/{job_id}")
def delete_import(job_id: UUID, actor: Principal = Depends(require(P.MANAGE_SALES_MEMORY)),
                  svc: Services = Depends(get_services)):
    """Owner request (2026-10-08): undo an import made with the wrong file or department."""
    job = svc.ops.get_job(job_id)
    if job is None or job["type"] != "discord.import":
        raise HTTPException(404, "import not found")
    if job["status"] in ("queued", "running"):
        raise HTTPException(409, "this import is still running")
    n = svc.ops.delete_sales_memory_import(job_id)
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="delete_sales_memory_import",
                 job_id=job_id, removed=n)
    return {"removed": n}
