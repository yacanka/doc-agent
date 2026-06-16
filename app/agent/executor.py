"""Document operation executor."""
from __future__ import annotations

from pathlib import Path

from app.tools.validation_tool import validate_replacements, write_report
from app.tools.word_tool import replace_text, timestamped_output


class Executor:
    """Execute planned DOCX replacements and validation."""

    def __init__(self, outputs_dir: Path) -> None:
        """Initialize with the root output directory."""
        self.outputs_dir = outputs_dir

    def apply(self, session: dict, replacements: dict[str, str]) -> dict:
        """Apply replacements and return output metadata."""
        source = Path(session["original_path"])
        output = timestamped_output(self.outputs_dir, session["id"], session["filename"])
        output.parent.mkdir(parents=True, exist_ok=True)
        changed_count = replace_text(source, output, replacements)
        report = validate_replacements(output, replacements, changed_count)
        report_path = write_report(report, output)
        return {"output_path": str(output), "report_path": str(report_path), "report": report}
