"""Secure, idempotent metadata lifecycle for document intelligence."""
from __future__ import annotations

import uuid

from app.platform.documents import (
    DocumentAsset,
    DocumentJob,
    DocumentStatus,
    ExtractionField,
    ExtractionRun,
    MalwareScanner,
    ScanResult,
    new_document_id,
    validate_upload,
)
from app.platform.models import utc_now


class DocumentService:
    def __init__(self, db, scanner: MalwareScanner):
        self.db = db
        self.scanner = scanner

    def _audit(self, actor_id: str, event_type: str, asset_id: str, payload=None):
        event_id = f"audit_{uuid.uuid4().hex}"
        self.db.collection("audit_events").document(event_id).set({
            "id": event_id,
            "actor_id": actor_id,
            "event_type": event_type,
            "entity_type": "document",
            "entity_id": asset_id,
            "payload": payload or {},
            "created_at": utc_now().isoformat(),
        })

    def ingest(
        self,
        owner_id: str,
        filename: str,
        content_type: str,
        content: bytes,
        storage_path: str | None = None,
    ) -> DocumentAsset:
        safe_name, digest = validate_upload(filename, content_type, content)
        duplicates = list(
            self.db.collection("document_assets").where("owner_principal_id", "==", owner_id).stream()
        )
        duplicate = next(
            (item.to_dict() for item in duplicates if (item.to_dict() or {}).get("sha256") == digest),
            None,
        )
        scan_result = self.scanner.scan(content)
        status = {
            ScanResult.CLEAN: DocumentStatus.READY,
            ScanResult.UNSAFE: DocumentStatus.UNSAFE,
            ScanResult.UNAVAILABLE: DocumentStatus.SCAN_PENDING,
        }[scan_result]
        asset = DocumentAsset(
            id=new_document_id(),
            owner_principal_id=owner_id,
            filename=safe_name,
            content_type=content_type,
            byte_size=len(content),
            sha256=digest,
            status=status,
            malware_scan_result=scan_result,
            duplicate_of=(duplicate or {}).get("id"),
            storage_path=storage_path,
        )
        self.db.collection("document_assets").document(asset.id).set(asset.model_dump(mode="json"))
        self._audit(owner_id, "document.ingested", asset.id, {
            "status": asset.status.value,
            "duplicate": bool(asset.duplicate_of),
        })
        return asset

    def get_document(self, actor_id: str, document_id: str) -> DocumentAsset:
        snapshot = self.db.collection("document_assets").document(document_id).get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Document not found.")
        asset = DocumentAsset.model_validate(snapshot.to_dict())
        if asset.owner_principal_id != actor_id:
            raise PermissionError("Document access denied.")
        return asset

    def list_documents(self, actor_id: str) -> list[DocumentAsset]:
        snapshots = self.db.collection("document_assets").where(
            "owner_principal_id", "==", actor_id
        ).stream()
        assets = [DocumentAsset.model_validate(item.to_dict()) for item in snapshots]
        return sorted(assets, key=lambda item: item.created_at, reverse=True)

    def get_extraction(self, actor_id: str, run_id: str) -> ExtractionRun:
        snapshot = self.db.collection("document_extraction_runs").document(run_id).get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Extraction run not found.")
        run = ExtractionRun.model_validate(snapshot.to_dict())
        self.get_document(actor_id, run.document_id)
        return run

    def enqueue_extraction(self, actor_id: str, document_id: str) -> tuple[DocumentJob, bool]:
        asset = self.get_document(actor_id, document_id)
        snapshots = self.db.collection("document_jobs").where(
            "document_id", "==", document_id
        ).stream()
        for snapshot in snapshots:
            job = DocumentJob.model_validate(snapshot.to_dict())
            if job.document_version == asset.version and job.status in {"queued", "running"}:
                return job, False
        if asset.status != DocumentStatus.READY:
            raise RuntimeError("Only malware-cleared documents may be queued.")
        job = DocumentJob(
            id=f"djob_{uuid.uuid4().hex}",
            document_id=document_id,
            owner_principal_id=actor_id,
            document_version=asset.version,
            correlation_id=f"doc-{uuid.uuid4().hex}",
        )
        self.db.collection("document_jobs").document(job.id).set(job.model_dump(mode="json"))
        asset.status = DocumentStatus.CLASSIFYING
        asset.updated_at = utc_now()
        self.db.collection("document_assets").document(asset.id).set(asset.model_dump(mode="json"))
        self._audit(actor_id, "document.extraction_queued", asset.id, {
            "job_id": job.id,
            "correlation_id": job.correlation_id,
        })
        return job, True

    def get_job(self, actor_id: str, job_id: str) -> DocumentJob:
        snapshot = self.db.collection("document_jobs").document(job_id).get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Document job not found.")
        job = DocumentJob.model_validate(snapshot.to_dict())
        if job.owner_principal_id != actor_id:
            raise PermissionError("Document job access denied.")
        return job

    def start_extraction(
        self,
        actor_id: str,
        document_id: str,
        fields: list[ExtractionField],
        *,
        classifier_version: str,
        extractor_version: str,
        model_provider: str,
        model_name: str,
        prompt_version: str,
    ) -> ExtractionRun:
        ref = self.db.collection("document_assets").document(document_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Document not found.")
        asset = DocumentAsset.model_validate(snapshot.to_dict())
        if asset.owner_principal_id != actor_id:
            raise PermissionError("Document access denied.")
        if asset.status != DocumentStatus.READY:
            raise RuntimeError("Only malware-cleared documents may be extracted.")
        run = ExtractionRun(
            id=f"ext_{uuid.uuid4().hex}",
            document_id=asset.id,
            document_version=asset.version,
            classifier_version=classifier_version,
            extractor_version=extractor_version,
            model_provider=model_provider,
            model_name=model_name,
            prompt_version=prompt_version,
            input_sha256=asset.sha256,
            fields=fields,
        )
        self.db.collection("document_extraction_runs").document(run.id).set(run.model_dump(mode="json"))
        asset.status = DocumentStatus.REVIEW_REQUIRED
        asset.extraction_run_id = run.id
        asset.updated_at = utc_now()
        ref.set(asset.model_dump(mode="json"))
        self._audit(actor_id, "document.extraction_started", asset.id, {"run_id": run.id})
        return run

    def verify_extraction(
        self, actor_id: str, run_id: str, corrections: dict[str, str]
    ) -> ExtractionRun:
        run_ref = self.db.collection("document_extraction_runs").document(run_id)
        snapshot = run_ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Extraction run not found.")
        run = ExtractionRun.model_validate(snapshot.to_dict())
        asset_ref = self.db.collection("document_assets").document(run.document_id)
        asset = DocumentAsset.model_validate(asset_ref.get().to_dict())
        if asset.owner_principal_id != actor_id:
            raise PermissionError("Document access denied.")
        for field in run.fields:
            if field.field_name in corrections:
                field.corrected_value = corrections[field.field_name]
            field.verified = True
        run.status = "verified"
        run.reviewer_principal_id = actor_id
        run.verified_at = utc_now()
        run_ref.set(run.model_dump(mode="json"))
        asset.status = DocumentStatus.VERIFIED
        asset.updated_at = utc_now()
        asset_ref.set(asset.model_dump(mode="json"))
        self._audit(actor_id, "document.extraction_verified", asset.id, {
            "run_id": run.id,
            "corrected_fields": sorted(corrections),
        })
        return run
