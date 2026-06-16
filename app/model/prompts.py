"""Prompt templates for local document intelligence."""
from __future__ import annotations


def qa_prompt(question: str, document_text: str) -> str:
    """Build a grounded question-answering prompt."""
    return (
        "Answer using only the document text. If unknown, say you do not know.\n\n"
        f"Document:\n{document_text[:6000]}\n\nQuestion: {question}\nAnswer:"
    )


def planning_prompt(instruction: str, document_text: str) -> str:
    """Build a JSON-only operation planning prompt."""
    return (
        "Return JSON only with shape {\"replacements\": {\"old\": \"new\"}}. "
        "Plan safe literal DOCX text replacements.\n\n"
        f"Document:\n{document_text[:6000]}\n\nInstruction: {instruction}\nJSON:"
    )
