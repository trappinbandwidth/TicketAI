"""Execute a queued WP-03 document job with explicit failure persistence."""
from __future__ import annotations

from app.platform.document_service import DocumentService
from app.platform.documents import (
    DocumentAsset,
    DocumentJob,
    DocumentStatus,
    ExtractionField,
    ScanResult,
)
from app.platform.models import utc_now
from app.services.document_provider import process_document
from app.services.malware_scanner import configured_scanner
from app.services.preprocessor import image_file_to_base64, pdf_to_images_and_text


def _download(storage_path: str) -> bytes:
    if not storage_path.startswith("gs://"):
        raise ValueError("Document storage path is not a private GCS object.")
    from firebase_admin import storage

    bucket_name, blob_path = storage_path[5:].split("/", 1)
    return storage.bucket(bucket_name).blob(blob_path).download_as_bytes()


def _fields(extraction: dict) -> list[ExtractionField]:
    fields = []
    for name, item in extraction.items():
        if not isinstance(item, dict) or "confidence_score" not in item:
            continue
        bbox = item.get("bbox")
        fields.append(ExtractionField(
            field_name=name,
            value=str(item.get("value") or ""),
            confidence=max(0.0, min(float(item.get("confidence_score") or 0), 1.0)),
            page=(bbox or {}).get("page"),
            bounding_box=(
                {key: float((bbox or {}).get(key, 0)) for key in ("x", "y", "w", "h")}
                if bbox else None
            ),
            raw_evidence=item.get("raw_evidence") or item.get("ai_reason"),
        ))
    return fields


def run_document_job(db, job_id: str) -> dict:
    job_ref = db.collection("document_jobs").document(job_id)
    snapshot = job_ref.get()
    if not getattr(snapshot, "exists", False):
        raise LookupError("Document job not found.")
    job = DocumentJob.model_validate(snapshot.to_dict())
    if job.status in {"review_required", "completed"}:
        return {"job": job, "idempotent": True}
    if job.status not in {"queued", "failed"} or job.attempts >= job.max_attempts:
        raise RuntimeError("Document job is not runnable.")

    asset_ref = db.collection("document_assets").document(job.document_id)
    asset = DocumentAsset.model_validate(asset_ref.get().to_dict())
    if asset.malware_scan_result != ScanResult.CLEAN:
        raise RuntimeError("Document has not passed malware scanning.")

    job.status = "running"
    job.attempts += 1
    job.updated_at = utc_now()
    job_ref.set(job.model_dump(mode="json"))
    asset.status = DocumentStatus.EXTRACTING
    asset.updated_at = utc_now()
    asset_ref.set(asset.model_dump(mode="json"))

    try:
        content = _download(asset.storage_path or "")
        if asset.content_type == "application/pdf":
            images, ocr_text = pdf_to_images_and_text(content)
        else:
            images, ocr_text = image_file_to_base64(content, asset.content_type)
        extraction, _, usage = process_document(
            images_b64=images,
            ocr_text=ocr_text,
            prompt_version="v2",
            temperature=0.4,
        )
        provider = (usage or {}).get("provider", "mock")
        model = (usage or {}).get("model", "mock")
        service = DocumentService(db, configured_scanner())
        run = service.start_extraction(
            job.owner_principal_id,
            asset.id,
            _fields(extraction),
            classifier_version="document-gate-v1",
            extractor_version="carver-v2",
            model_provider=provider,
            model_name=model,
            prompt_version="v2",
        )
        job.status = "review_required"
        job.error_code = None
        job.updated_at = utc_now()
        job_ref.set(job.model_dump(mode="json"))
        return {"job": job, "extraction_run": run}
    except Exception:
        job.status = "failed"
        job.error_code = "document_processing_failed"
        job.updated_at = utc_now()
        job_ref.set(job.model_dump(mode="json"))
        asset.status = DocumentStatus.FAILED
        asset.updated_at = utc_now()
        asset_ref.set(asset.model_dump(mode="json"))
        raise
