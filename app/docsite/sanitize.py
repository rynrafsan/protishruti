"""Keep editor HTML safe, and turn it into Markdown for the export.

The editor sends HTML. Only a small set of tags and attributes survives; scripts, styles, event
handlers, inline styles and javascript: links are dropped. Everything is re-escaped, so the stored
HTML is safe to put on the public page as is.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

ALLOWED = {"p", "br", "strong", "em", "u", "s", "a", "ul", "ol", "li", "h3", "h4", "blockquote", "code",
           "pre", "table", "thead", "tbody", "tr", "th", "td", "hr", "sup", "sub", "mark"}
RENAME = {"b": "strong", "i": "em", "h1": "h3", "h2": "h3", "h5": "h4", "h6": "h4", "div": "p",
          "strike": "s", "del": "s", "ins": "u"}
VOID = {"br", "hr"}
DROP_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "noscript", "template", "svg", "math",
                     "head", "title", "textarea", "select", "button"}
SAFE_URL = re.compile(r"^(https?://|mailto:|#|/(?!/))", re.I)


def safe_url(url: str | None) -> str | None:
    url = (url or "").strip()
    return url if url and SAFE_URL.match(url) and not re.search(r"[\s<>\"']", url) else None


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_WITH_CONTENT:
            self.skip += 1
            return
        if self.skip:
            return
        tag = RENAME.get(tag, tag)
        if tag not in ALLOWED:
            return
        if tag == "p" and "p" in self.stack:  # no nested paragraphs
            self._close("p")
        keep = []
        a = dict(attrs)
        if tag == "a":
            url = safe_url(a.get("href"))
            if url:
                keep.append(f' href="{html.escape(url, quote=True)}"')
            if a.get("title"):
                keep.append(f' title="{html.escape(a["title"][:200], quote=True)}"')
        if tag in ("td", "th"):
            for k in ("colspan", "rowspan"):
                if (a.get(k) or "").isdigit() and 1 < int(a[k]) <= 12:
                    keep.append(f' {k}="{int(a[k])}"')
        self.out.append(f"<{tag}{''.join(keep)}>")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        tag = RENAME.get(tag, tag)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self._close(tag)

    def _close(self, tag):
        while self.stack:
            t = self.stack.pop()
            self.out.append(f"</{t}>")
            if t == tag:
                break

    def handle_endtag(self, tag):
        if tag in DROP_WITH_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        tag = RENAME.get(tag, tag)
        if tag in self.stack:
            self._close(tag)

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        text = "".join(self.out)
        text = re.sub(r"<p>(\s|<br>)*</p>", "", text)  # empty paragraphs from the editor
        return text.strip()


def clean_html(text: str | None, limit: int = 60_000) -> str:
    p = _Cleaner()
    p.feed((text or "")[:limit * 2])
    p.close()
    return p.result()[:limit]


def plain(text: str | None, limit: int = 300) -> str:
    """Plain text for titles and short fields."""
    t = re.sub(r"<[^>]*>", "", text or "")
    return re.sub(r"\s+", " ", html.unescape(t)).strip()[:limit]


class _Markdown(HTMLParser):
    """Converts the cleaned HTML above (only that tag set) to GitHub-flavoured Markdown."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.line: list[str] = []
        self.lists: list[list] = []  # [kind, counter]
        self.quote = 0
        self.pre = False
        self.href: list[str | None] = []
        self.table: list[list[str]] | None = None
        self.cell: list[str] | None = None
        self.header_rows = 0

    def _flush(self):
        text = "".join(self.line).strip()
        self.line = []
        if text:
            prefix = "> " * self.quote
            self.blocks.append(prefix + text.replace("\n", "\n" + prefix))

    def _emit(self, s):
        (self.cell if self.cell is not None else self.line).append(s)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("p", "h3", "h4", "blockquote", "pre", "table", "ul", "ol", "hr"):
            if self.cell is None:
                self._flush()
        if tag == "h3":
            self.line.append("### ")
        elif tag == "h4":
            self.line.append("#### ")
        elif tag == "blockquote":
            self.quote += 1
        elif tag == "pre":
            self.pre = True
            self.line.append("```\n")
        elif tag in ("ul", "ol"):
            self.lists.append([tag, 0])
        elif tag == "li":
            self._flush()
            kind = self.lists[-1] if self.lists else ["ul", 0]
            kind[1] += 1
            indent = "  " * (len(self.lists) - 1)
            self.line.append(indent + ("- " if kind[0] == "ul" else f"{kind[1]}. "))
        elif tag in ("strong",):
            self._emit("**")
        elif tag in ("em",):
            self._emit("*")
        elif tag == "s":
            self._emit("~~")
        elif tag == "code" and not self.pre:
            self._emit("`")
        elif tag == "a":
            self.href.append(a.get("href"))
            self._emit("[")
        elif tag == "br":
            self._emit("  \n" if self.cell is None else " ")
        elif tag == "hr":
            self.blocks.append("---")
        elif tag == "table":
            self.table, self.header_rows = [], 0
        elif tag == "tr" and self.table is not None:
            self.table.append([])
        elif tag in ("td", "th") and self.table is not None:
            self.cell = []
            if tag == "th" and len(self.table) == 1:
                self.header_rows = 1

    def handle_endtag(self, tag):
        if tag in ("p", "h3", "h4", "li"):
            if self.cell is None:
                self._flush()
        elif tag == "blockquote":
            self._flush()
            self.quote = max(0, self.quote - 1)
        elif tag == "pre":
            self.line.append("\n```")
            self.pre = False
            self._flush()
        elif tag in ("ul", "ol"):
            self._flush()
            if self.lists:
                self.lists.pop()
        elif tag == "strong":
            self._emit("**")
        elif tag == "em":
            self._emit("*")
        elif tag == "s":
            self._emit("~~")
        elif tag == "code" and not self.pre:
            self._emit("`")
        elif tag == "a":
            href = self.href.pop() if self.href else None
            self._emit(f"]({href})" if href else "]")
        elif tag in ("td", "th") and self.table is not None and self.cell is not None:
            self.table[-1].append("".join(self.cell).strip().replace("|", "\\|"))
            self.cell = None
        elif tag == "table" and self.table is not None:
            rows = [r for r in self.table if r]
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                head = rows[0] if self.header_rows else [""] * width
                body = rows[1:] if self.header_rows else rows
                out = ["| " + " | ".join(head) + " |", "|" + "---|" * width] + ["| " + " | ".join(r) + " |" for r in body]
                self.blocks.append("\n".join(out))
            self.table = None

    def handle_data(self, data):
        if self.pre:
            self.line.append(data)
            return
        text = re.sub(r"\s+", " ", data)
        if self.cell is None and not "".join(self.line).strip():
            text = text.lstrip()
        self._emit(text)

    def result(self) -> str:
        self._flush()
        return "\n\n".join(self.blocks)


def to_markdown(clean: str) -> str:
    p = _Markdown()
    p.feed(clean or "")
    p.close()
    return p.result()
