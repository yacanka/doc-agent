"""Strict prompt templates for local document intelligence."""
from __future__ import annotations

_MAX_DOCUMENT_CONTEXT = 6000
_OPERATION_PLAN_SCHEMA = (
    '{"mode":"plan","operations":[{"action":"replace_text",'
    '"tool":"word.replace_text","parameters":{"replacements":{"old":"new"}},'
    '"risk":"low"}],"risk":"low","summary":"short reason"}'
)


def qa_prompt(question: str, document_text: str) -> str:
    """Build a grounded question-answering prompt."""
    return (
        "Answer using only the document text. If unknown, say you do not know.\n\n"
        f"Document:\n{document_text[:_MAX_DOCUMENT_CONTEXT]}\n\nQuestion: {question}\nAnswer:"
    )


def planning_prompt(instruction: str, document_text: str) -> str:
    """Build a strict JSON operation-planning prompt."""
    return (
        "Return one valid JSON object only. Do not include markdown or prose. "
        f"Use exactly this schema: {_OPERATION_PLAN_SCHEMA}. "
        "Allowed actions: replace_text. Allowed tools: word.replace_text. "
        "Do not include file paths, write instructions, or destructive operations. "
        "If no safe literal replacement is possible, return an empty operations array.\n\n"
        f"Document:\n{document_text[:_MAX_DOCUMENT_CONTEXT]}\n\nInstruction: {instruction}\nJSON:"
    )
