"""Translate missing travel content locally, then optionally update Supabase.

Argos Translate runs on the local machine after its model packages are installed.
The script is a dry run unless --apply is supplied. Existing translations are
never overwritten unless --overwrite is also supplied.
"""

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv

from app.services.offline_translation import ArgosTranslator
from app.services.supabase import SupabaseRestClient

TABLE_FIELDS = {
    "locations": {
        "name_ja": ("name_en", "name_zh"),
        "description_ja": ("description_en", "description_zh"),
        "address_ja": ("address_en", "address_zh"),
        "opening_hours": ("opening_hours_en", "opening_hours_zh"),
    },
    "exhibitions": {
        "title_ja": ("title_en", "title_zh"),
        "description_ja": ("description_en", "description_zh"),
        "price_note": ("price_note_en", "price_note_zh"),
        "period_note": ("period_note_en", "period_note_zh"),
    },
}


class Translator(Protocol):
    def translate(self, text: str, target: str) -> str: ...


def install_models() -> None:
    """Download the smallest available model set needed by this script."""
    try:
        import argostranslate.package
        import certifi
    except ImportError as error:
        raise SystemExit(
            "Argos Translate is missing. Run: .venv/bin/pip install -e '.[translation]'"
        ) from error

    # python.org macOS installations can lack the framework-level cert.pem.
    # Use certifi's maintained CA bundle without disabling TLS verification.
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    argostranslate.package.update_package_index()
    packages = argostranslate.package.get_available_packages()
    installed = {
        (package.from_code, package.to_code)
        for package in argostranslate.package.get_installed_packages()
    }

    def install_pair(source: str, target: str) -> bool:
        if (source, target) in installed:
            return True
        package = next(
            (item for item in packages if item.from_code == source and item.to_code == target),
            None,
        )
        if package is None:
            return False
        print(f"Installing Argos model {source}->{target}")
        argostranslate.package.install_from_path(package.download())
        installed.add((source, target))
        return True

    if not install_pair("ja", "en"):
        raise SystemExit("The Argos package index has no ja->en model")
    # Prefer a direct model; Argos can pivot ja->en->zh when it is unavailable.
    if not install_pair("ja", "zh") and not install_pair("en", "zh"):
        raise SystemExit("The Argos package index has neither ja->zh nor en->zh")


async def read_all(client: SupabaseRestClient, table: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    while True:
        page = await client.request(
            "GET",
            table,
            params={"select": "*", "limit": "500", "offset": str(len(rows)), "order": "id"},
            profile="travel",
        )
        if not page:
            return rows
        rows.extend(page)


def translations_for_row(
    table: str, row: dict[str, Any], translator: Translator, overwrite: bool
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    translated_at = datetime.now(UTC).isoformat()
    metadata = dict(row.get("translation_meta") or {})
    for source_field, (english_field, chinese_field) in TABLE_FIELDS[table].items():
        source = row.get(source_field)
        if not isinstance(source, str) or not source.strip():
            continue
        for target, target_field in (("en", english_field), ("zh", chinese_field)):
            if not overwrite and row.get(target_field):
                continue
            translated = translator.translate(source.strip(), target)
            if not translated:
                continue
            updates[target_field] = translated
            metadata[target_field] = {
                "provider": "argos-translate",
                "source_field": source_field,
                "source_language": "ja",
                "target_language": "zh-TW" if target == "zh" else "en",
                "translated_at": translated_at,
                "reviewed": False,
            }
    if updates:
        updates["translation_meta"] = metadata
    return updates


async def run(args: argparse.Namespace) -> None:
    load_dotenv()
    try:
        translator = ArgosTranslator()
    except RuntimeError as error:
        raise SystemExit(
            f"{error}. Run: python scripts/translate_supabase_content.py --install-models"
        ) from error
    client = SupabaseRestClient(
        os.environ["SUPABASE_PUBLIC_URL"], os.environ["SUPABASE_SECRET_KEY"]
    )
    report: dict[str, list[dict[str, Any]]] = {table: [] for table in args.tables}
    changed = 0
    for table in args.tables:
        rows = await read_all(client, table)
        if args.limit is not None:
            rows = rows[: args.limit]
        for row in rows:
            updates = translations_for_row(table, row, translator, args.overwrite)
            if not updates:
                continue
            changed += 1
            report[table].append({"id": str(row["id"]), "updates": updates})
            if args.apply:
                await client.request(
                    "PATCH",
                    table,
                    params={"id": f"eq.{row['id']}"},
                    body=updates,
                    prefer="return=minimal",
                    profile="travel",
                )
            print(f"{table} {row['id']}: {', '.join(updates.keys() - {'translation_meta'})}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    mode = "updated" if args.apply else "would update"
    print(f"{mode} {changed} rows; report: {args.output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write translations to Supabase")
    parser.add_argument(
        "--overwrite", action="store_true", help="replace existing translations (use carefully)"
    )
    parser.add_argument("--limit", type=int, help="maximum rows per selected table")
    parser.add_argument(
        "--table",
        choices=tuple(TABLE_FIELDS),
        action="append",
        dest="tables",
        help="table to process; repeat to select both (default: both)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/translation-preview.json"),
        help="dry-run/audit JSON path",
    )
    parser.add_argument(
        "--install-models",
        action="store_true",
        help="download and install required Argos language models, then exit",
    )
    args = parser.parse_args()
    args.tables = args.tables or list(TABLE_FIELDS)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than zero")
    return args


if __name__ == "__main__":
    cli_args = parse_args()
    if cli_args.install_models:
        install_models()
    else:
        asyncio.run(run(cli_args))
