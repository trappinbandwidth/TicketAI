"""
Textract Service — extracts word-level bounding boxes from document images.

Returns a list of WordPosition objects, each with the word text and its
normalized bounding box (0–1 fractions of page dimensions).

Falls back to an empty list when AWS credentials are not configured,
which is safe — bbox_matcher will simply leave bbox=None on all fields.

AWS credentials are read from the standard chain:
  TEXTRACT_AWS_ACCESS_KEY_ID / TEXTRACT_AWS_SECRET_ACCESS_KEY env vars, or
  ~/.aws/credentials, or IAM instance role (on EC2/Lightsail).

Region defaults to us-east-1 (where Textract is cheapest).
Cost: ~$1.50 per 1,000 pages ($0.0015/page, $0.003/ticket avg).
"""
import base64
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WordPosition:
    word: str
    x: float       # left, 0–1
    y: float       # top, 0–1
    w: float       # width, 0–1
    h: float       # height, 0–1
    page: int = 1  # 1-indexed


def extract_word_positions(images_b64: list[str]) -> list[WordPosition]:
    """
    Run AWS Textract on each page image and return all word positions.
    Returns [] if Textract is unavailable or credentials are missing.
    """
    access_key = os.getenv("TEXTRACT_AWS_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID", "")
    secret_key = os.getenv("TEXTRACT_AWS_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY", "")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    if not access_key or not secret_key:
        logger.debug("[textract] credentials not set — skipping bounding box extraction")
        return []

    try:
        import boto3
    except ImportError:
        logger.warning("[textract] boto3 not installed — pip install boto3 to enable bboxes")
        return []

    client = boto3.client(
        "textract",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )

    all_words: list[WordPosition] = []

    for page_num, img_b64 in enumerate(images_b64, start=1):
        try:
            img_bytes = base64.b64decode(img_b64)
            response = client.detect_document_text(
                Document={"Bytes": img_bytes}
            )
        except Exception as exc:
            logger.warning("[textract] page=%d error=%s", page_num, exc)
            continue

        for block in response.get("Blocks", []):
            if block.get("BlockType") != "WORD":
                continue
            text = block.get("Text", "").strip()
            if not text:
                continue
            geo = block.get("Geometry", {}).get("BoundingBox", {})
            if not geo:
                continue
            all_words.append(WordPosition(
                word=text,
                x=geo.get("Left", 0.0),
                y=geo.get("Top", 0.0),
                w=geo.get("Width", 0.0),
                h=geo.get("Height", 0.0),
                page=page_num,
            ))

    logger.warning("[textract] pages=%d words_found=%d", len(images_b64), len(all_words))
    return all_words
