"""Knowledge documents, proposals and approvals — PRD §7 (Knowledge, Add information, Documents, Approvals), §8, §11
(`/knowledge/documents`, `/knowledge/proposals`, `/admin/proposals/{id}/approve|reject`, `/admin/documents/upload`,
`/admin/documents/{id}/reindex`)."""
from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ...analytics import audit
from ...ingestion.storage import raw_document_key
from ...ingestion.validation import InvalidUpload, safe_filename, validate_upload
from ...knowledge.service import Draft, KnowledgeError, KnowledgeService, is_publisher, may_review
from ...knowledge.vault import parse_note
from ...permissions.access import Principal
from ...permissions.roles import P, can
from ..deps import get_services, require
from ..jobs import enqueue
from ..services import Services

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])
admin = APIRouter(prefix="/v1/admin", tags=["knowledge-admin"])


def _ks(svc: Services) -> KnowledgeService:
    return KnowledgeService(svc)


def _err(e: KnowledgeError):
    raise HTTPException(e.status, str(e))


def _scope(p: Principal, svc: Services):
    """(departments, sensitivity levels) this person may browse; None = every department (§3)."""
    depts = None if p.all_departments else frozenset(p.department_ids | p.managed_department_ids)
    return depts, svc.settings.levels_for(p.role.value)


def _s(x):
    return str(x) if x is not None else None


def _doc_view(d: dict) -> dict:
    return {**d, "item_id": str(d["item_id"]), "version_id": str(d["version_id"]), "owner_id": _s(d.get("owner_id")),
            "department_ids": [str(x) for x in d["department_ids"]]}


# ---- browse (§7 Knowledge) ----
@router.get("/documents")
def list_documents(q: Optional[str] = None, status: Optional[str] = None, category: Optional[str] = None,
                   department_id: Optional[UUID] = None, limit: int = 200, offset: int = 0,
                   p: Principal = Depends(require(P.VIEW_KNOWLEDGE)), svc: Services = Depends(get_services)):
    depts, levels = _scope(p, svc)
    if can(p.role, P.MANAGE_DOCUMENTS):
        levels = levels | {"unclassified"}            # documents nobody classified yet must be visible to those who classify them
    rows = svc.knowledge.list_documents(depts, levels, status=status, q=q, category=category, department_id=department_id,
                                        limit=min(limit, 500), offset=offset)
    return {"documents": [_doc_view(r) for r in rows], "categories": svc.knowledge.categories(),
            "sensitivity_levels": sorted(svc.settings.sensitivity_levels)}


def _item_or_404(p: Principal, svc: Services, item_id: UUID) -> dict:
    item = svc.knowledge.get_item(item_id)
    depts, levels = _scope(p, svc)
    if item is None or item["sensitivity"] not in levels and item["sensitivity"] != "unclassified" \
            or (depts is not None and not set(item["department_ids"]) & depts):
        raise HTTPException(404, "document not found")          # never reveal documents outside the scope (§13 AT-05)
    return item


@router.get("/documents/{item_id}")
def get_document(item_id: UUID, p: Principal = Depends(require(P.VIEW_KNOWLEDGE)), svc: Services = Depends(get_services)):
    item = _item_or_404(p, svc, item_id)
    pub = svc.knowledge.published_version(item_id)
    return {"item": {**item, "id": str(item["id"]), "owner_id": _s(item["owner_id"]), "department_ids": [str(x) for x in item["department_ids"]]},
            "published": {"id": str(pub["id"]), "version": pub["version"], "text": pub["body"], "effective_date": pub["effective_date"],
                          "expires_at": pub["expires_at"], "published_at": pub["published_at"], "vault_commit": pub["vault_commit"],
                          "filename": pub["filename"]} if pub else None,
            "versions": [{**v, "id": str(v["id"])} for v in svc.knowledge.versions_of(item_id)],
            "proposals": [_proposal_row(x) for x in svc.knowledge.list_proposals(item_id=item_id, limit=50)]}


@router.get("/documents/{item_id}/versions/{version_id}")
def get_version(item_id: UUID, version_id: UUID, p: Principal = Depends(require(P.VIEW_KNOWLEDGE)), svc: Services = Depends(get_services)):
    _item_or_404(p, svc, item_id)
    v = svc.knowledge.get_version(version_id)
    if v is None or v["item_id"] != item_id:
        raise HTTPException(404, "version not found")
    return {"id": str(v["id"]), "version": v["version"], "status": v["status"], "text": v["body"], "change_note": v["change_note"],
            "effective_date": v["effective_date"], "expires_at": v["expires_at"], "history": svc.knowledge.history(version_id)}


# ---- propose (§7 Add information, §11 POST /knowledge/proposals) ----
class ProposalIn(BaseModel):
    item_id: Optional[UUID] = None                    # set = new version of an existing document
    title: str = Field(min_length=2, max_length=200)
    body: Optional[str] = Field(default=None, max_length=400_000)
    department_ids: list[UUID] = Field(min_length=1)
    sensitivity: str
    category: Optional[str] = Field(default=None, max_length=80)
    owner_id: Optional[UUID] = None
    provenance: Optional[str] = Field(default=None, max_length=300)
    effective_date: Optional[date] = None
    expires_at: Optional[datetime] = None
    change_note: Optional[str] = Field(default=None, max_length=1000)
    high_impact: bool = False
    gap_id: Optional[UUID] = None                     # answering a knowledge gap (§9 gap loop)


def _draft(b, body, file_id=None) -> Draft:
    return Draft(title=" ".join(b.title.split()), body=body, department_ids=list(b.department_ids), sensitivity=b.sensitivity,
                 category=(b.category or "").strip() or None, owner_id=b.owner_id, provenance=(b.provenance or "").strip() or None,
                 effective_date=b.effective_date, expires_at=b.expires_at, change_note=(b.change_note or "").strip() or None,
                 high_impact=b.high_impact, source_file_id=file_id, gap_id=getattr(b, "gap_id", None))


@router.post("/proposals", status_code=201)
def propose(body: ProposalIn, p: Principal = Depends(require(P.PROPOSE_KNOWLEDGE)), svc: Services = Depends(get_services)):
    if body.item_id is None and not (body.body or "").strip():
        raise HTTPException(422, "write the information, or upload a document")
    try:
        d = _draft(body, body.body)
        return _ks(svc).propose_update(p, body.item_id, d) if body.item_id else _ks(svc).propose_new(p, d)
    except KnowledgeError as e:
        _err(e)


def _store_upload(svc: Services, p: Principal, file: UploadFile) -> tuple[UUID, str]:
    data = file.file.read(svc.settings.max_upload_bytes + 1)
    name = safe_filename(file.filename or "file")
    try:
        ext = validate_upload(name, data, svc.settings.max_upload_bytes)    # §7 type/size detection; unreadable files rejected
    except InvalidUpload as e:
        raise HTTPException(422, str(e))
    file_id = uuid4()
    key = raw_document_key(file_id, name)
    svc.storage.put(key, data)                                              # §11 private object storage for originals
    svc.knowledge.create_source_file(file_id, name, ext, len(data), key, p.user_id)
    audit.record(svc.ops, audit.DOCUMENT_UPLOAD, p.user_id, p.employee_id, filename=name, size=len(data))
    return file_id, name


def _ids(raw: str) -> list[UUID]:
    try:
        return [UUID(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, "department_ids must be comma-separated ids")


@router.post("/proposals/upload", status_code=202)
@admin.post("/documents/upload", status_code=202)
def propose_upload(file: UploadFile = File(...), department_ids: str = Form(...), sensitivity: str = Form(...),
                   title: Optional[str] = Form(None), category: Optional[str] = Form(None), item_id: Optional[UUID] = Form(None),
                   owner_id: Optional[UUID] = Form(None), provenance: Optional[str] = Form(None),
                   effective_date: Optional[date] = Form(None), expires_at: Optional[datetime] = Form(None),
                   change_note: Optional[str] = Form(None), high_impact: bool = Form(False), gap_id: Optional[UUID] = Form(None),
                   p: Principal = Depends(require(P.PROPOSE_KNOWLEDGE)), svc: Services = Depends(get_services)):
    """PDF / DOCX / TXT / MD (§7 Documents). Stored, parsed and indexed in the background; reviewers then see the parsed text."""
    file_id, name = _store_upload(svc, p, file)
    b = ProposalIn(item_id=item_id, title=(title or name.rsplit(".", 1)[0]).strip() or name, body=None, department_ids=_ids(department_ids),
                   sensitivity=sensitivity, category=category, owner_id=owner_id, provenance=provenance or f"Uploaded file {name}",
                   effective_date=effective_date, expires_at=expires_at, change_note=change_note, high_impact=high_impact, gap_id=gap_id)
    try:
        d = _draft(b, None, file_id)
        out = _ks(svc).propose_update(p, item_id, d, source="upload", source_ref=None) if item_id else \
            _ks(svc).propose_new(p, d, source="upload")
    except KnowledgeError as e:
        _err(e)
    return {**out, "processing_status": "pending"}


@admin.post("/documents/import-obsidian", status_code=202)
def import_obsidian(files: list[UploadFile] = File(...), department_ids: str = Form(""), sensitivity: Optional[str] = Form(None),
                    approve: bool = Form(False), p: Principal = Depends(require(P.MANAGE_DOCUMENTS)),
                    svc: Services = Depends(get_services)):
    """P0 "Obsidian-compatible approved document import" (§14): .md notes or a .zip of a vault. Each note becomes a proposal;
    its front matter (title, category, departments, sensitivity, owner, source, effective_date, expires) fills the fields, the form
    values are the defaults. `approve` records the importer's own approval (still a person's decision, §1); high-impact notes
    still need a second approver."""
    notes: list[tuple[str, str]] = []
    for f in files:
        data = f.file.read(svc.settings.max_upload_bytes + 1)
        if len(data) > svc.settings.max_upload_bytes:
            raise HTTPException(422, f"{f.filename} is too large")
        if (f.filename or "").lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for n in z.namelist():
                        parts = n.split("/")
                        if n.lower().endswith(".md") and not any(x.startswith(".") for x in parts) and "Archive" not in parts:
                            notes.append((n, z.read(n).decode("utf-8", errors="replace")))
            except zipfile.BadZipFile:
                raise HTTPException(422, f"{f.filename} is not a valid zip file")
        elif (f.filename or "").lower().endswith(".md"):
            notes.append((f.filename, data.decode("utf-8", errors="replace")))
        else:
            raise HTTPException(422, f"{f.filename}: only .md notes or a .zip of a vault")
    if not notes:
        raise HTTPException(422, "no Markdown notes found")
    if len(notes) > 500:
        raise HTTPException(422, "import at most 500 notes at a time")
    default_depts = _ids(department_ids) if department_ids else []
    by_name = {d["name"].lower(): d["id"] for d in svc.users.list_departments(include_archived=False)}
    ks, results = _ks(svc), []
    for path, text in notes:
        fm, body = parse_note(text)
        names = fm.get("departments") or fm.get("department") or []
        names = [names] if isinstance(names, str) else names
        depts = [by_name[n.lower()] for n in names if isinstance(n, str) and n.lower() in by_name] or default_depts
        title = str(fm.get("title") or path.rsplit("/", 1)[-1].removesuffix(".md")).strip()
        try:
            exp = fm.get("expires")
            d = Draft(title=title, body=body.strip(), department_ids=depts, sensitivity=str(fm.get("sensitivity") or sensitivity or ""),
                      category=fm.get("category"), provenance=str(fm.get("source") or f"Obsidian import: {path}"),
                      effective_date=fm.get("effective_date") if isinstance(fm.get("effective_date"), date) else None,
                      expires_at=datetime.combine(exp, datetime.min.time()) if isinstance(exp, date) else None,
                      change_note="Imported from Obsidian")
            if not d.body:
                raise KnowledgeError(422, "the note is empty")
            out = ks.propose_new(p, d, source="import", source_ref=f"{path}:{hash(text) & 0xffffffff:x}")
            results.append({"note": path, "ok": True, **out})
        except KnowledgeError as e:
            results.append({"note": path, "ok": False, "error": str(e)})
    if approve and is_publisher(p):
        for r in results:
            if r["ok"] and not r.get("duplicate"):
                r["approval"] = "queued"              # recorded by the worker once the note is indexed (it must be readable first)
                enqueue(svc, "knowledge.approve_after_index", {"proposal_id": r["proposal_id"], "user_id": str(p.user_id)}, p.user_id)
    audit.record(svc.ops, audit.DOCUMENT_UPLOAD, p.user_id, p.employee_id, action="obsidian_import", notes=len(notes),
                 created=sum(1 for r in results if r["ok"]))
    return {"results": results}


# ---- review (§7 Approvals) ----
def _proposal_row(x: dict) -> dict:
    return {"id": str(x["id"]), "kind": x["kind"], "title": x["title"], "summary": x["summary"], "status": x["status"],
            "source": x["source"], "submitted_by": _s(x["submitted_by"]), "submitted_by_name": x["submitted_by_name"],
            "submitted_at": x["submitted_at"], "high_impact": x["high_impact"], "required_approvals": x["required_approvals"],
            "item_id": str(x["item_id"]), "version": x["version"], "version_status": x["version_status"],
            "filename": x["filename"], "processing_status": x["processing_status"], "processing_error": x["processing_error"],
            "indexed": x["indexed_checksum"] is not None and x["indexed_checksum"] == x["checksum"],
            "departments": x["current_departments"], "error": x["error"], "published_at": x["published_at"]}


@router.get("/proposals")
def list_proposals(status: Optional[str] = None, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    """Reviewers see what they may decide; proposers see their own (§7 Approvals queue)."""
    if not (can(p.role, P.REVIEW_PROPOSALS) or can(p.role, P.PROPOSE_KNOWLEDGE)):
        raise HTTPException(403, "your role cannot see proposals")
    statuses = [status] if status else None
    ks, out = _ks(svc), []
    for x in svc.knowledge.list_proposals(statuses):
        mine = x["submitted_by"] == p.user_id
        reviewable = may_review(p, ks.proposal_departments(x))
        if mine or reviewable:
            out.append({**_proposal_row(x), "mine": mine, "can_review": reviewable})
    return {"proposals": out}


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: UUID, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    ks = _ks(svc)
    x = svc.knowledge.get_proposal(proposal_id)
    if x is None:
        raise HTTPException(404, "proposal not found")
    reviewable = may_review(p, ks.proposal_departments(x))
    if x["submitted_by"] != p.user_id and not reviewable:
        raise HTTPException(404, "proposal not found")
    decisions = svc.knowledge.decisions(proposal_id)
    already = any(d["decided_by"] == p.user_id for d in decisions)
    return {**_proposal_row(x), "meta": x["meta"], "diff": ks.diff(x),
            "related": [{**r, "item_id": str(r["item_id"]), "similarity": round(float(r["similarity"]), 3)}
                        for r in svc.knowledge.related_documents(x["version_id"], *_scope(p, svc))] if x["kind"] != "archive" else [],
            "decisions": [{**d, "decided_by": str(d["decided_by"])} for d in decisions],
            "can_review": reviewable and x["status"] == "open" and not already, "mine": x["submitted_by"] == p.user_id}


class DecisionIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)


def _decide(proposal_id: UUID, decision: str, body: DecisionIn, p: Principal, svc: Services):
    try:
        return _ks(svc).decide(p, proposal_id, decision, body.note)
    except KnowledgeError as e:
        _err(e)


@admin.post("/proposals/{proposal_id}/approve")
def approve(proposal_id: UUID, body: DecisionIn = DecisionIn(), p: Principal = Depends(require(P.REVIEW_PROPOSALS)),
            svc: Services = Depends(get_services)):
    return _decide(proposal_id, "approve", body, p, svc)


@admin.post("/proposals/{proposal_id}/reject")
def reject(proposal_id: UUID, body: DecisionIn, p: Principal = Depends(require(P.REVIEW_PROPOSALS)), svc: Services = Depends(get_services)):
    return _decide(proposal_id, "reject", body, p, svc)


@admin.post("/proposals/{proposal_id}/request-changes")
def request_changes(proposal_id: UUID, body: DecisionIn, p: Principal = Depends(require(P.REVIEW_PROPOSALS)),
                    svc: Services = Depends(get_services)):
    return _decide(proposal_id, "request_changes", body, p, svc)


@router.post("/proposals/{proposal_id}/withdraw")
def withdraw(proposal_id: UUID, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    try:
        _ks(svc).withdraw(p, proposal_id)
    except KnowledgeError as e:
        _err(e)
    return {"status": "withdrawn"}


@admin.post("/proposals/{proposal_id}/retry", status_code=202)
def retry_publication(proposal_id: UUID, p: Principal = Depends(require(P.MANAGE_DOCUMENTS)), svc: Services = Depends(get_services)):
    x = svc.knowledge.get_proposal(proposal_id)
    if x is None or x["status"] != "failed":
        raise HTTPException(409, "only a failed publication can be retried")
    svc.knowledge.set_proposal_status(proposal_id, "approved", expect=("failed",))
    return {"job_id": str(enqueue(svc, "knowledge.publish", {"proposal_id": str(proposal_id), "approved_by": str(p.user_id)}, p.user_id))}


# ---- documents (§7 Documents: archive, reindex, versions; §8 rollback) ----
class NoteIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)


class RestoreIn(NoteIn):
    version_id: UUID


@admin.post("/documents/{item_id}/archive")
def archive_document(item_id: UUID, body: NoteIn = NoteIn(), p: Principal = Depends(require(P.MANAGE_DOCUMENTS)),
                     svc: Services = Depends(get_services)):
    try:
        return _ks(svc).propose_archive(p, item_id, body.note)
    except KnowledgeError as e:
        _err(e)


@admin.post("/documents/{item_id}/restore")
def restore_version(item_id: UUID, body: RestoreIn, p: Principal = Depends(require(P.MANAGE_DOCUMENTS)),
                    svc: Services = Depends(get_services)):
    try:
        return _ks(svc).propose_restore(p, item_id, body.version_id, body.note)
    except KnowledgeError as e:
        _err(e)


class ClassifyIn(BaseModel):
    item_ids: list[UUID] = Field(min_length=1, max_length=2000)
    sensitivity: str


@admin.post("/documents/classify")
def classify_documents(body: ClassifyIn, p: Principal = Depends(require(P.MANAGE_DOCUMENTS)), svc: Services = Depends(get_services)):
    """First classification of documents that existed before access levels did (PRD §8, §10). Unclassified documents are never
    used in answers; a publisher decides their level here (a person's decision, recorded as a permission change). Already
    classified documents are changed only through a reviewed proposal."""
    if not is_publisher(p):
        raise HTTPException(403, "only a publisher can classify documents")
    if body.sensitivity not in svc.settings.sensitivity_levels:
        raise HTTPException(422, f"sensitivity must be one of {sorted(svc.settings.sensitivity_levels)}")
    n = svc.knowledge.classify_unclassified(body.item_ids, body.sensitivity)
    audit.record(svc.ops, audit.PERMISSION_CHANGE, p.user_id, p.employee_id, action="classify_documents", sensitivity=body.sensitivity,
                 documents=n)
    return {"classified": n}


@admin.post("/documents/{item_id}/reindex", status_code=202)
def reindex_document(item_id: UUID, p: Principal = Depends(require(P.MANAGE_DOCUMENTS)), svc: Services = Depends(get_services)):
    pub = svc.knowledge.published_version(item_id)
    if pub is None:
        raise HTTPException(404, "no published version to reindex")
    audit.record(svc.ops, audit.ADMIN_ACTION, p.user_id, p.employee_id, action="reindex_document", item=item_id)
    return {"job_id": str(enqueue(svc, "knowledge.process", {"version_id": str(pub["id"])}, p.user_id))}


@admin.delete("/documents/{item_id}", status_code=204)
def delete_unpublished(item_id: UUID, p: Principal = Depends(require(P.MANAGE_DOCUMENTS)), svc: Services = Depends(get_services)):
    """Only for documents that were never published (a published one is archived instead, so history stays, §8)."""
    out = svc.knowledge.delete_draft_document(item_id)
    if out is None:
        raise HTTPException(409, "published or archived documents are archived, not deleted")
    for f in out["files"]:
        svc.storage.delete(f["s3_key"])
    audit.record(svc.ops, audit.ADMIN_ACTION, p.user_id, p.employee_id, action="delete_unpublished_document", item=item_id)
