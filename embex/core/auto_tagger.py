"""
Auto-tagging — automatically label chunks with topic tags based on content analysis.

Tags are added as metadata to chunks in ChromaDB, enabling filtered searches.
"""

from __future__ import annotations

import re
from typing import Any


# Tag detection rules: (tag_name, patterns_to_look_for)
_TAG_RULES: list[tuple[str, list[str]]] = [
    ("auth", [
        r"\bauth\b", r"\blogin\b", r"\blogout\b", r"\bsignup\b", r"\bsign.?in\b",
        r"\bpassword\b", r"\btoken\b", r"\bjwt\b", r"\boauth\b", r"\bsession\b",
    ]),
    ("database", [
        r"\bsql\b", r"\bquery\b", r"\binsert\b", r"\bselect\b", r"\btable\b",
        r"\bdatabase\b", r"\bdb\b", r"\bsqlite\b", r"\bpostgres\b", r"\bmongo\b",
        r"\borm\b", r"\bmodel\b", r"\bmigration\b",
    ]),
    ("api", [
        r"\bapi\b", r"\bendpoint\b", r"\broute\b", r"\brequest\b", r"\bresponse\b",
        r"\bhttp\b", r"\brest\b", r"\bgraphql\b", r"\bmiddleware\b",
        r"\bget\b.*\bdef\b|\bpost\b.*\bdef\b|\bput\b.*\bdef\b|\bdelete\b.*\bdef\b",
    ]),
    ("test", [
        r"\btest_\b", r"\bassert\b", r"\bpytest\b", r"\bjest\b", r"\bdescribe\b",
        r"\bit\(.+?\)\b", r"\bexpect\b", r"\bmock\b", r"\bfixture\b",
    ]),
    ("config", [
        r"\bconfig\b", r"\bsettings?\b", r"\benv\b", r"\b\.env\b",
        r"\byaml\b", r"\bjson\b", r"\btoml\b", r"\benvironment\b",
    ]),
    ("error-handling", [
        r"\btry\b", r"\bexcept\b", r"\bcatch\b", r"\braise\b", r"\bthrow\b",
        r"\berror\b", r"\bexception\b", r"\bfail\b",
    ]),
    ("io", [
        r"\bfile\b", r"\bread\b", r"\bwrite\b", r"\bopen\b", r"\bpath\b",
        r"\bstdin\b", r"\bstdout\b", r"\bstream\b", r"\bsocket\b",
    ]),
    ("ui", [
        r"\brender\b", r"\bcomponent\b", r"\btemplate\b", r"\bview\b",
        r"\bhtml\b", r"\bcss\b", r"\bstyle\b", r"\bbutton\b", r"\bform\b",
    ]),
    ("async", [
        r"\basync\b", r"\bawait\b", r"\bcoroutine\b", r"\btask\b",
        r"\bfuture\b", r"\bpromise\b", r"\bcallback\b",
    ]),
    ("cli", [
        r"\bargparse\b", r"\bclick\b", r"\btyper\b", r"\bcommand\b",
        r"\bargument\b", r"\bflag\b", r"\bparser\b",
    ]),
]


def auto_tag(text: str) -> list[str]:
    """Analyze a code chunk and return a list of topic tags.

    Parameters
    ----------
    text : str
        The raw code chunk text.

    Returns
    -------
    list[str]
        Tags like ["auth", "database", "api"].
    """
    text_lower = text.lower()
    tags: list[str] = []

    for tag_name, patterns in _TAG_RULES:
        for pattern in patterns:
            if re.search(pattern, text_lower):
                tags.append(tag_name)
                break  # One match is enough for this tag

    return tags


def apply_tags_to_metadata(
    metadata: dict[str, Any],
    chunk_text: str,
) -> dict[str, Any]:
    """Add auto-generated tags to chunk metadata.

    Parameters
    ----------
    metadata : dict
        Existing chunk metadata.
    chunk_text : str
        The code chunk text to analyze.

    Returns
    -------
    dict
        Updated metadata with a ``tags`` field.
    """
    tags = auto_tag(chunk_text)
    metadata["tags"] = ",".join(tags) if tags else ""
    return metadata
