from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import UploadFile

from backend.database.db import get_conn, init_db, now_iso
from backend.models.schemas import TemplateMergeRequest
from backend.services.document_service import cleanup_process_document, save_process_upload
from backend.services.template_merge_service import merge_template_pdf


DEFAULT_TEMPLATE_ID = 4
POLL_SECONDS = 2.0
STABLE_SCANS_REQUIRED = 3


@dataclass(frozen=True)
class ProcessingResult:
    source: Path
    output: Path | None
    archived_source: Path | None
    error: str | None = None


class FolderProcessor:
    """Processes PDFs dropped directly in a user's ``faxsender`` folder.

    The watch directory is intentionally also the output directory.  A durable
    fingerprint ledger prevents generated PDFs from being picked up again.
    """

    def __init__(self, root: Path, template_id: int = DEFAULT_TEMPLATE_ID) -> None:
        self.root = root.expanduser().resolve()
        self.template_id = template_id
        self.completed_dir = self.root / "사용완료"
        self.failed_dir = self.root / "오류"
        self.state_path = self.root / ".faxsender-processed.json"
        self._stable: dict[Path, tuple[int, int, int]] = {}
        self._processed = self._load_processed()

    def ensure_directories(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.completed_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _template_payload() -> dict:
        root = Path(os.environ["FAX_SENDER_ROOT"])
        template_path = root / "auto_processor" / "resources" / "heungkuk_template.json"
        return json.loads(template_path.read_text(encoding="utf-8"))

    def _ensure_heungkuk_template(self) -> None:
        """Seed only the non-sensitive built-in template needed by the watcher."""
        with get_conn() as conn:
            if conn.execute("SELECT 1 FROM pdf_templates WHERE id = ?", (self.template_id,)).fetchone():
                return
            payload = self._template_payload()
            now = now_iso()
            conn.execute(
                """
                INSERT INTO pdf_templates(
                    id, name, description, document_id, overlay_config_json,
                    form_data_json, render_style_json, created_at, updated_at
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    self.template_id,
                    payload["name"],
                    payload["description"],
                    json.dumps(payload["overlay_config"], ensure_ascii=False),
                    json.dumps(payload["form_data"], ensure_ascii=False),
                    json.dumps(payload["render_style"], ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def _load_processed(self) -> set[str]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            values = payload.get("processed_sha256", [])
            return {value for value in values if isinstance(value, str)}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return set()

    def _save_processed(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"processed_sha256": sorted(self._processed)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _unique_destination(directory: Path, filename: str) -> Path:
        candidate = directory / filename
        if not candidate.exists():
            return candidate
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return directory / f"{stem}_{timestamp}{suffix}"

    def _is_stable(self, path: Path) -> bool:
        try:
            stat = path.stat()
        except OSError:
            self._stable.pop(path, None)
            return False
        previous = self._stable.get(path)
        fingerprint = (stat.st_size, stat.st_mtime_ns)
        stable_count = previous[2] + 1 if previous and previous[:2] == fingerprint else 1
        self._stable[path] = (*fingerprint, stable_count)
        return stable_count >= STABLE_SCANS_REQUIRED

    def pending_files(self) -> list[Path]:
        self.ensure_directories()
        candidates: list[Path] = []
        for path in self.root.glob("*.pdf"):
            if not path.is_file() or path.name.startswith("~") or not self._is_stable(path):
                continue
            # Completed PDFs are written to the same directory as inputs. Do
            # not merely reject them during processing; keep them out of the
            # watch queue completely so they can never start a second run.
            if self._hash(path) in self._processed:
                continue
            candidates.append(path)
        return sorted(candidates, key=lambda path: path.stat().st_mtime)

    def process(self, source: Path) -> ProcessingResult:
        source = source.resolve()
        source_hash = self._hash(source)
        if source_hash in self._processed:
            return ProcessingResult(source=source, output=None, archived_source=None)

        document_id: int | None = None
        try:
            init_db()
            self._ensure_heungkuk_template()
            with source.open("rb") as handle:
                upload = UploadFile(filename=source.name, file=handle)
                document = asyncio.run(save_process_upload(upload))
            document_id = document.id
            result = merge_template_pdf(
                self.template_id,
                TemplateMergeRequest(),
                document_id_override=document_id,
            )
            generated = Path(result.output_path)
            if not result.success or not generated.exists():
                raise RuntimeError("PDF 합성 결과 파일을 만들지 못했습니다.")

            destination = self._unique_destination(self.root, result.output_filename)
            shutil.move(str(generated), str(destination))
            archived = self._unique_destination(self.completed_dir, source.name)
            shutil.move(str(source), str(archived))
            self._processed.add(source_hash)
            # Outputs are stored alongside incoming PDFs. Record them too so
            # the next polling cycle never treats a generated file as input.
            self._processed.add(self._hash(destination))
            self._save_processed()
            return ProcessingResult(source=source, output=destination, archived_source=archived)
        except Exception as exc:  # A failed original must remain recoverable.
            self.failed_dir.mkdir(parents=True, exist_ok=True)
            failed = self._unique_destination(self.failed_dir, source.name)
            try:
                if source.exists():
                    shutil.move(str(source), str(failed))
                (failed.with_suffix(failed.suffix + ".error.txt")).write_text(str(exc), encoding="utf-8")
            except OSError:
                pass
            return ProcessingResult(source=source, output=None, archived_source=None, error=str(exc))
        finally:
            if document_id is not None:
                cleanup_process_document(document_id)


class FolderMonitor:
    def __init__(self, processor: FolderProcessor, on_result: Callable[[ProcessingResult], None]) -> None:
        self.processor = processor
        self.on_result = on_result
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="faxsender-folder-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=POLL_SECONDS + 1)

    def _run(self) -> None:
        self.processor.ensure_directories()
        while not self._stop.is_set():
            for source in self.processor.pending_files():
                if self._stop.is_set():
                    break
                result = self.processor.process(source)
                self.on_result(result)
            self._stop.wait(POLL_SECONDS)
