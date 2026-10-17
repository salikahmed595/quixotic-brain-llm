"""Documents — PRD §13 and §37 (POST/GET /v1/documents, DELETE /v1/documents/{id}).

Upload is accepted immediately; processing happens in the background (§47, §56 "Immediate acceptance")."""
from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ...analytics import audit
from ...ingestion.storage import raw_document_key
from ...ingestion.validation import InvalidUpload, safe_filename, validate_upload
from ...permissions.access import Principal, resolve_department_scope
from ...permissions.roles import P, Role
from ..deps import current_principal, get_services, require
from ..flow import KnowledgeFlow
from ..services import Services

router = APIRouter(prefix="/v1/documents", tags=["documents"])


def _view(v: dict) -> dict:
    return {"id": str(v["id"]), "title": v["title"], "filename": v["filename"], "departments": v["departments"],
            "category": v["category"], "document_type": v["document_type"], "access_level": v["access_level"],
            "version": v["version"], "status": v["status"], "processing_status": v["processing_status"],
            "processing_error": v["processing_error"], "size_bytes": v["size_bytes"], "updated_at": v["updated_at"]}


@router.post("", status_code=202)
def upload(file: UploadFile = File(...), department_ids: str = Form(...), title: Optional[str] = Form(None),
           category: Optional[str] = Form(None), document_type: Optional[str] = Form(None),
           access_level: Optional[str] = Form(None), language: Optional[str] = Form(None),
           status: str = Form("draft"),
           actor: Principal = Depends(require(P.MANAGE_DOCUMENTS)), svc: Services = Depends(get_services)):
    """`status` mirrors the §13.2 form's Status field. Only an administrator may publish directly
    (status=active); every other upload is submitted for review (§9.2 "All submissions require review")."""
    if status not in ("draft", "active"):
        raise HTTPException(422, "status must be 'draft' or 'active'")
    if status == "active" and not actor.can_publish:
        raise HTTPException(403, "only an administrator can publish directly; your upload will be submitted for review")
    try:
        dept_ids = [UUID(x) for x in department_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, "department_ids must be comma-separated UUIDs")
    if not dept_ids:
        raise HTTPException(422, "at least one department is required")
    allowed = resolve_department_scope(actor, svc.users.all_department_ids())
    if not set(dept_ids) <= allowed:
        raise HTTPException(403, "you can only upload for departments you are authorized for")
    data = file.file.read(svc.settings.max_upload_bytes + 1)
    name = safe_filename(file.filename or "file")
    try:
        ext = validate_upload(name, data, svc.settings.max_upload_bytes)
    except InvalidUpload as e:
        raise HTTPException(422, str(e))

    file_id = uuid4()
    key = raw_document_key(file_id, name)
    svc.storage.put(key, data)                                                   # §13.3 store original file
    svc.knowledge.create_source_file(file_id, name, ext, len(data), key, actor.user_id)
    _, version_id = svc.knowledge.create_item_with_first_version(
        title or name, category, document_type, dept_ids, None, language, access_level, file_id, actor.user_id)
    audit.record(svc.ops, audit.DOCUMENT_UPLOAD, actor.user_id, actor.employee_id, filename=name, version_id=version_id)
    flow = KnowledgeFlow(svc)
    job_id = flow.enqueue("document.process", {"version_id": str(version_id)}, actor.user_id)
    if status == "active":
        flow.admin_publish(version_id, actor)
    else:
        flow.transition(version_id, "submitted", actor)
    return {"document_id": str(version_id), "job_id": str(job_id), "processing_status": "pending"}


@router.get("")
def list_documents(limit: int = 50, offset: int = 0, actor: Principal = Depends(current_principal),
                   svc: Services = Depends(get_services)):
    scope = None if actor.all_departments else actor.department_ids
    return {"documents": [_view(v) for v in svc.knowledge.list_versions(department_ids=scope, only_files=True,
                                                                         limit=limit, offset=offset)]}


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: UUID, actor: Principal = Depends(require(P.MANAGE_DOCUMENTS)),
                    svc: Services = Depends(get_services)):
    f = svc.knowledge.delete_version(document_id)
    if f is None and svc.knowledge.get_version(document_id) is None:
        raise HTTPException(404, "document not found")
    if f:
        svc.storage.delete(f["s3_key"])
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="delete_document",
                 document_id=document_id)
