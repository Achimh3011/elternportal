"""Minimal HTML to Markdown conversion for portal message bodies."""

import re

from lxml import html as lhtml
from lxml.etree import _Element

_UMNODES = {"strong": "**", "b": "**", "em": "*", "i": "*"}
_HEADING_TAGS = {f"h{n}": "#" * n for n in range(1, 7)}
_BLOCK_TRENNER = {"p": "\n\n", "div": "\n", "blockquote": "\n\n"}
_WHITESPACE_RE = re.compile(r"\n{3,}")


def html_to_markdown(fragment_html: str) -> str:
    """Convert an HTML fragment into plain Markdown.

    Args:
        fragment_html: HTML fragment as emitted by the portal message editor.

    Returns:
        Markdown text with collapsed blank lines.
    """
    if not fragment_html or not fragment_html.strip():
        return ""
    wrapper = lhtml.fragment_fromstring(f"<div>{fragment_html}</div>", create_parent=False)
    text = _nodes_to_markdown(wrapper)
    return _WHITESPACE_RE.sub("\n\n", text).strip()


def _nodes_to_markdown(element: _Element) -> str:
    parts = [_text_nodes(element)]
    for child in element:
        if not isinstance(child.tag, str):
            continue
        parts.append(_child_to_markdown(child))
        parts.append(child.tail or "")
    return "".join(parts)


_INTERPUNKTION = "!.,;:?!)]}\"'"


def _trenner(child: _Element) -> str:
    """Space after inline elements, unless whitespace or punctuation already follows."""
    tail = child.tail or ""
    erstes = tail[:1]
    if erstes.isspace() or erstes in _INTERPUNKTION:
        return ""
    return " "


def _text_nodes(element: _Element) -> str:
    return element.text or ""


def _child_to_markdown(child: _Element) -> str:
    inner = _nodes_to_markdown(child)
    tag = child.tag
    if tag in _UMNODES:
        return f"{_UMNODES[tag]}{inner.strip()}{_UMNODES[tag]}{_trenner(child)}"
    if tag == "br":
        return "\n"
    if tag == "a":
        return f"[{inner.strip()}]({child.get('href', '')}){_trenner(child)}"
    if tag == "li":
        return f"- {inner.strip()}\n"
    if tag in _HEADING_TAGS:
        return f"\n{_HEADING_TAGS[tag]} {inner.strip()}\n\n"
    if tag == "hr":
        return "\n---\n\n"
    if tag == "img":
        return f"![{child.get('alt', '')}]({child.get('src', '')}) "
    if tag in _BLOCK_TRENNER:
        return f"{_BLOCK_TRENNER[tag]}{inner.strip()}{_BLOCK_TRENNER[tag]}"
    return inner
