# Batch-extract invoice data from scanned images across 6 languages.
#
# For every image under DATA_DIR/<language>/images/*.png it uploads the file to
# LlamaCloud, runs the extraction workflow, and writes the result as JSON to
# OUTPUT_DIR/<language>/<image-name>.json (mirroring the source folder layout).
#
# pip install llama-index-workflows[client] llama-cloud>=1.0.0 python-dotenv

import asyncio
import json
import os
from pathlib import Path

# Use the OS (Windows) certificate store so corporate proxy / MITM CAs are
# trusted. Without this, requests fail with SSL CERTIFICATE_VERIFY_FAILED.
import truststore

truststore.inject_into_ssl()

import httpx
from dotenv import load_dotenv
from llama_cloud import LlamaCloud
from workflows.client import WorkflowClient

from json_to_markdown import to_markdown

load_dotenv()

API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
BASE_URL = os.getenv("LLAMA_CLOUD_BASE_URL", "https://api.cloud.llamaindex.ai")
DEPLOYMENT_NAME = os.getenv("LLAMA_DEPLOY_DEPLOYMENT_NAME", "invoice-data-extraction-tool")
# The extraction workflow registered inside the deployment (see list_workflows()).
WORKFLOW_NAME = os.getenv("WORKFLOW_NAME", "process-file")

# Source images (6 language folders, each with an images/ subfolder).
DATA_DIR = Path(
    r"C:\Users\rajesh.hugar\OneDrive - bizmetric.com\2026\WIPRO_"
    r"\model-evaluation-temp\Scanned_Images_\Data"
)
# Where extracted JSON results are written.
OUTPUT_DIR = Path(__file__).parent / "Extracted_images"

LANGUAGES = ["bengali", "hindi", "kannada", "marathi", "tamil", "telugu"]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf"}


def _serialize(result):
    """Turn a workflow result (pydantic / dict / str) into something json.dump can write."""
    for attr in ("model_dump", "dict"):
        method = getattr(result, attr, None)
        if callable(method):
            try:
                return method()
            except Exception:
                pass
    if isinstance(result, (dict, list, str, int, float, bool)) or result is None:
        return result
    return str(result)


def iter_images():
    """Yield (language, image_path) for every image to process."""
    for language in LANGUAGES:
        images_dir = DATA_DIR / language / "images"
        if not images_dir.is_dir():
            print(f"  ! skipping {language}: {images_dir} not found")
            continue
        for image_path in sorted(images_dir.iterdir()):
            if image_path.suffix.lower() in IMAGE_EXTENSIONS:
                yield language, image_path


async def extract_one(llama_cloud, client, language, image_path):
    out_path = OUTPUT_DIR / language / f"{image_path.stem}.json"

    # Resume support: skip anything we've already extracted.
    if out_path.exists():
        print(f"  = {language}/{image_path.name} (already done)")
        return "skipped"

    # 1) Upload the image to LlamaCloud.
    with open(image_path, "rb") as f:
        uploaded = llama_cloud.files.create(file=f, purpose="extract")

    # 2) Run the workflow against the uploaded file.
    handler = await client.run_workflow_nowait(
        WORKFLOW_NAME,
        start_event={"file_id": uploaded.id},
    )

    # 3) Stream events. The actual extracted invoice data arrives as an
    #    "ExtractedEvent"; the final StopEvent only carries a saved-record id.
    extracted = None
    statuses = []
    async for event in client.get_workflow_events(handler.handler_id):
        if event.type in ("ExtractedEvent", "ExtractedInvalidEvent"):
            value = event.value or {}
            extracted = value.get("data", value)
        elif event.type == "Status":
            statuses.append(event.value)

    handler_result = await client.get_handler(handler.handler_id)

    # 4) Persist the result, mirroring the source folder layout.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_image": str(image_path),
        "language": language,
        "file_id": uploaded.id,
        "record_id": _serialize(handler_result.result),
        "extracted_data": extracted,
        "statuses": statuses,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also write a human-readable Markdown version alongside the JSON.
    md_path = out_path.with_suffix(".md")
    md_path.write_text(to_markdown(payload), encoding="utf-8")

    print(f"  + {language}/{image_path.name} -> {out_path.name} + {md_path.name}")
    return "done"


async def main():
    if not API_KEY:
        raise SystemExit("LLAMA_CLOUD_API_KEY is not set (check your .env).")

    llama_cloud = LlamaCloud(api_key=API_KEY, base_url=BASE_URL)

    httpx_client = httpx.AsyncClient(
        base_url=f"{BASE_URL}/deployments/{DEPLOYMENT_NAME}",
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=httpx.Timeout(300.0),
    )
    client = WorkflowClient(httpx_client=httpx_client)

    counts = {"done": 0, "skipped": 0, "failed": 0}
    try:
        for language, image_path in iter_images():
            try:
                status = await extract_one(llama_cloud, client, language, image_path)
                counts[status] += 1
            except Exception as exc:  # keep going if a single image fails
                counts["failed"] += 1
                print(f"  x {language}/{image_path.name} FAILED: {exc}")
    finally:
        await httpx_client.aclose()

    print(
        f"\nFinished. extracted={counts['done']} "
        f"skipped={counts['skipped']} failed={counts['failed']}"
    )
    print(f"Results in: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
