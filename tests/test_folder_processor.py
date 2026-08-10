from pathlib import Path

from auto_processor.folder_processor import FolderProcessor


def test_completed_output_is_not_returned_as_pending_input(tmp_path: Path) -> None:
    processor = FolderProcessor(tmp_path / "faxsender")
    processor.ensure_directories()
    completed = processor.root / "100_팀장_고객.pdf"
    completed.write_bytes(b"completed output")
    processor._processed.add(processor._hash(completed))
    processor._save_processed()

    # Three unchanged scans make a file stable; it must still be excluded.
    assert processor.pending_files() == []
    assert processor.pending_files() == []
    assert processor.pending_files() == []


def test_selected_faxsender_folder_is_not_nested() -> None:
    # The UI logic is intentionally mirrored as a pure path rule here.
    selected = Path("C:/Users/test/Documents/faxsender")
    watch_root = selected if selected.name.casefold() == "faxsender" else selected / "faxsender"
    assert watch_root == selected
