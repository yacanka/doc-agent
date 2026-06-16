"""Document operation executor with an approved Python tool allow-list."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agent.schemas import DocumentOperation, ExecutionResult, OperationPlan, ToolName
from app.tools.validation_tool import validate_replacements, write_report
from app.tools.word_tool import replace_text, timestamped_output


class Executor:
    """Execute validated plans without granting LLM file write access."""

    def __init__(self, outputs_dir: Path) -> None:
        """Initialize with the trusted root output directory."""
        self.outputs_dir = outputs_dir

    def apply(self, session: dict, replacements: dict[str, str]) -> dict:
        """Apply literal replacements and return output metadata."""
        operation = DocumentOperation(
            action="replace_text",
            tool=ToolName.WORD_REPLACE_TEXT,
            parameters={"replacements": replacements},
        )
        return self.apply_plan(session, OperationPlan(operations=[operation])).model_dump()

    def apply_plan(self, session: dict, plan: OperationPlan) -> ExecutionResult:
        """Execute only approved operations against controlled file paths."""
        context = _ExecutionContext.from_session(session, self.outputs_dir)
        executed = 0
        for operation in plan.operations:
            _dispatch_operation(operation, context)
            executed += 1
        report_path = write_report(context.report, context.output_path) if context.report else None
        return context.to_result(executed, report_path)


class _ExecutionContext:
    """Trusted executor state hidden from the LLM contract."""

    def __init__(self, source: Path, output: Path) -> None:
        self.source = source
        self.output_path = output
        self.replacements: dict[str, str] = {}
        self.changed_count = 0
        self.report: dict[str, Any] = {}

    @classmethod
    def from_session(cls, session: dict, outputs_dir: Path) -> "_ExecutionContext":
        """Build controlled source and destination paths from server session data."""
        source = Path(session["original_path"])
        output = timestamped_output(outputs_dir, session["id"], session["filename"])
        output.parent.mkdir(parents=True, exist_ok=True)
        return cls(source, output)

    def to_result(self, executed: int, report_path: Path | None) -> ExecutionResult:
        """Convert executor state to the public result schema."""
        return ExecutionResult(
            output_path=str(self.output_path),
            report_path=str(report_path) if report_path else None,
            report=self.report,
            changed_count=self.changed_count,
            operations_executed=executed,
        )


def _dispatch_operation(operation: DocumentOperation, context: _ExecutionContext) -> None:
    if operation.tool == ToolName.WORD_REPLACE_TEXT:
        _run_replace_text(operation, context)
        return
    if operation.tool == ToolName.VALIDATE_REPLACEMENTS:
        _run_validation(context)
        return
    raise ValueError(f"Tool is not approved: {operation.tool}")


def _run_replace_text(operation: DocumentOperation, context: _ExecutionContext) -> None:
    replacements = operation.parameters["replacements"]
    context.replacements = {str(key): str(value) for key, value in replacements.items()}
    context.changed_count = replace_text(context.source, context.output_path, context.replacements)
    _run_validation(context)


def _run_validation(context: _ExecutionContext) -> None:
    if not context.replacements:
        raise ValueError("Validation requires executed replacements")
    context.report = validate_replacements(context.output_path, context.replacements, context.changed_count)
