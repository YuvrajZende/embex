"""
Smart Chunker — AST-based code chunking using tree-sitter.

Instead of splitting by arbitrary line counts, this chunker parses
the code with tree-sitter and splits on function/class boundaries.
Each chunk represents a complete, meaningful code unit.

Falls back to the fixed-size chunker if parsing fails or the
language isn't supported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from embex.config import EmbexConfig

# Map file extensions → tree-sitter language modules
_LANG_MODULES: dict[str, tuple[str, list[str]]] = {
    # (pip package module path, node types to extract)
    ".py":   ("tree_sitter_python",      ["function_definition", "class_definition"]),
    ".js":   ("tree_sitter_javascript",   ["function_declaration", "function", "arrow_function", "class_declaration"]),
    ".jsx":  ("tree_sitter_javascript",   ["function_declaration", "function", "arrow_function", "class_declaration"]),
    ".ts":   ("tree_sitter_typescript",   ["function_declaration", "function", "arrow_function", "class_declaration"]),
    ".tsx":  ("tree_sitter_typescript",   ["function_declaration", "function", "arrow_function", "class_declaration"]),
}


@dataclass
class SmartChunk:
    """A single code chunk from AST parsing."""

    text: str
    start_line: int
    end_line: int
    kind: str        # "function", "class", or "module"
    name: str        # function/class name, or "module" for top-level code


def _get_parser_and_types(extension: str):
    """Load the tree-sitter parser for a given file extension.

    Returns (parser, node_types) or (None, None) if unsupported.
    """
    if extension not in _LANG_MODULES:
        return None, None

    module_name, node_types = _LANG_MODULES[extension]

    try:
        import importlib
        import tree_sitter as ts

        lang_module = importlib.import_module(module_name)
        language = ts.Language(lang_module.language())
        parser = ts.Parser(language)
        return parser, node_types
    except (ImportError, AttributeError, Exception):
        return None, None


def _extract_node_name(node) -> str:
    """Extract the name from a function/class node."""
    for child in node.children:
        if child.type == "identifier":
            return child.text.decode("utf-8") if isinstance(child.text, bytes) else child.text
        # For TypeScript typed function names
        if child.type == "name":
            return child.text.decode("utf-8") if isinstance(child.text, bytes) else child.text
    return "<anonymous>"


def _node_kind(node_type: str) -> str:
    """Simplify node type to 'function' or 'class'."""
    if "class" in node_type:
        return "class"
    return "function"


def _walk_and_collect(root_node, target_types: list[str]) -> list:
    """Walk the AST and collect all target node types."""
    results = []
    stack = [root_node]
    while stack:
        node = stack.pop()
        if node.type in target_types:
            results.append(node)
        # For classes, still look inside for methods
        for child in node.children:
            stack.append(child)
    return results


def smart_chunk(
    content: str,
    extension: str,
    config: "EmbexConfig",
) -> list[SmartChunk]:
    """Split code into chunks based on AST function/class boundaries.

    Parameters
    ----------
    content : str
        The full file content.
    extension : str
        File extension (e.g. ".py", ".js").
    config : EmbexConfig
        Project configuration.

    Returns
    -------
    list[SmartChunk]
        List of code chunks. Falls back to fixed-size chunking if
        tree-sitter parsing fails or the language is unsupported.
    """
    parser, target_types = _get_parser_and_types(extension)

    if parser is None:
        # Fallback to fixed-size chunking
        return _fallback_chunk(content, config)

    try:
        source_bytes = content.encode("utf-8")
        tree = parser.parse(source_bytes)
        root = tree.root_node
    except Exception:
        return _fallback_chunk(content, config)

    # Collect all function/class definitions
    nodes = _walk_and_collect(root, target_types)

    if not nodes:
        # No functions/classes found — treat entire file as one chunk
        return [SmartChunk(
            text=content,
            start_line=1,
            end_line=content.count("\n") + 1,
            kind="module",
            name="module",
        )]

    # Sort by start position
    nodes.sort(key=lambda n: n.start_point[0])

    lines = content.split("\n")
    chunks: list[SmartChunk] = []
    covered_up_to = 0  # track which lines we've already included

    for node in nodes:
        start_line = node.start_point[0]  # 0-indexed
        end_line = node.end_point[0]      # 0-indexed

        # If there's top-level code before this node, capture it
        if start_line > covered_up_to:
            preamble_text = "\n".join(lines[covered_up_to:start_line]).strip()
            if preamble_text:
                chunks.append(SmartChunk(
                    text=preamble_text,
                    start_line=covered_up_to + 1,
                    end_line=start_line,
                    kind="module",
                    name="imports/globals",
                ))

        # Extract the function/class chunk
        chunk_text = "\n".join(lines[start_line:end_line + 1])
        name = _extract_node_name(node)
        kind = _node_kind(node.type)

        chunks.append(SmartChunk(
            text=chunk_text,
            start_line=start_line + 1,  # 1-indexed for display
            end_line=end_line + 1,
            kind=kind,
            name=name,
        ))

        covered_up_to = end_line + 1

    # Capture any trailing code after the last node
    if covered_up_to < len(lines):
        trailing = "\n".join(lines[covered_up_to:]).strip()
        if trailing:
            chunks.append(SmartChunk(
                text=trailing,
                start_line=covered_up_to + 1,
                end_line=len(lines),
                kind="module",
                name="trailing",
            ))

    return chunks


def _fallback_chunk(content: str, config: "EmbexConfig") -> list[SmartChunk]:
    """Fixed-size line chunking as a fallback."""
    from embex.core.chunker import chunk_content

    raw_chunks = chunk_content(content, chunk_size=config.chunking.chunk_size, overlap=config.chunking.overlap)
    return [
        SmartChunk(
            text=text,
            start_line=start_line,
            end_line=end_line,
            kind="chunk",
            name=f"chunk_{i}",
        )
        for i, (text, _, start_line, end_line) in enumerate(raw_chunks)
    ]

