# Convert extracted invoice JSON files into human-readable Markdown.
#
# Reads every Extracted_images/<language>/*.json produced by extract_images.py
# and writes a sibling <name>.md with the same invoice data formatted as Markdown.

import glob
import json
import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "Extracted_images"


def _fmt(value):
    """Render a scalar value for Markdown, blank for None."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def to_markdown(record: dict) -> str:
    od = (record.get("extracted_data") or {}).get("original_data") or {}
    currency = od.get("currency") or ""
    lines = []

    title = od.get("invoice_number") or Path(record.get("source_image", "invoice")).stem
    lines.append(f"# Invoice {title}")
    lines.append("")
    lines.append(f"*Language:* {record.get('language', '')}  ")
    lines.append(f"*Source image:* `{Path(record.get('source_image', '')).name}`")
    lines.append("")

    # Header details.
    lines.append("## Details")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    detail_fields = [
        ("Invoice number", "invoice_number"),
        ("Invoice date", "invoice_date"),
        ("Due date", "due_date"),
        ("Currency", "currency"),
        ("Vendor name", "vendor_name"),
        ("Vendor address", "vendor_address"),
        ("Customer name", "customer_name"),
        ("Customer address", "customer_address"),
    ]
    for label, key in detail_fields:
        lines.append(f"| {label} | {_fmt(od.get(key))} |")
    lines.append("")

    # Line items.
    items = od.get("line_items") or []
    if items:
        lines.append("## Line items")
        lines.append("")
        lines.append("| # | Description | Quantity | Unit price | Amount |")
        lines.append("| --- | --- | ---: | ---: | ---: |")
        for i, item in enumerate(items, 1):
            lines.append(
                f"| {i} | {_fmt(item.get('description'))} | "
                f"{_fmt(item.get('quantity'))} | {_fmt(item.get('unit_price'))} | "
                f"{_fmt(item.get('amount'))} |"
            )
        lines.append("")

    # Totals.
    totals = [
        ("Subtotal", "subtotal"),
        ("Tax amount", "tax_amount"),
        ("Total amount", "total_amount"),
    ]
    if any(od.get(k) is not None for _, k in totals):
        lines.append("## Totals")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("| --- | ---: |")
        for label, key in totals:
            val = _fmt(od.get(key))
            if val and currency:
                val = f"{val} {currency}"
            lines.append(f"| {label} | {val} |")
        lines.append("")

    # Payment terms.
    if od.get("payment_terms"):
        lines.append("## Payment terms")
        lines.append("")
        lines.append(_fmt(od.get("payment_terms")))
        lines.append("")

    return "\n".join(lines)


def main():
    json_files = sorted(glob.glob(str(OUTPUT_DIR / "**" / "*.json"), recursive=True))
    count = 0
    for jf in json_files:
        record = json.loads(Path(jf).read_text(encoding="utf-8"))
        md_path = Path(jf).with_suffix(".md")
        md_path.write_text(to_markdown(record), encoding="utf-8")
        count += 1
        rel = os.path.relpath(md_path, OUTPUT_DIR)
        print(f"  + {rel}")
    print(f"\nWrote {count} markdown file(s) under {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
