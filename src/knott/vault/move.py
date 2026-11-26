"""`knott mv`: move one Markdown file and rewrite the links the move would break (spec 0018).

Every edit is a replaced span of characters: a frontmatter scalar, or the path of a
body link's destination. All edits are prepared in memory and each edited file is
parsed again and checked before anything is written (decision 0013).
"""

from __future__ import annotations

import copy
import dataclasses
import math
import os
import posixpath
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from knott._yaml import KeyPath
from knott.errors import KnottError, MoveError
from knott.models import Issue, MoveResult, SkippedFile, UnchangedLink, UpdatedLink
from knott.schema.models import (
    AttributeDef,
    FileShape,
    ListShape,
    MapShape,
    ObjectShape,
    ReferenceShape,
    Schema,
)
from knott.schema.validator import _check_location, _check_name, format_field_path
from knott.vault.discovery import CONNECTORS_DIR, LOOPS_DIR, RELATIONS_DIR
from knott.vault.entity import FRONTMATTER_DELIMITER, MarkdownFile, parse_markdown
from knott.vault.fix import _write_atomic
from knott.vault.index import VaultSession
from knott.vault.links import (
    _MARKDOWN_LINK,
    _URL_SCHEME,
    KID_PREFIX,
    LinkError,
    _exists_exact_case,
    parse_reference,
)
from knott.vault.refs import entity_kid

_BOM = "﻿"
_LINE = re.compile(r"\r?\n")
_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")
_BLANK_LINE = re.compile(r"\n[ \t]*\r?\n")
_TITLE = re.compile(r"""[ \t]+(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\((?:[^()\\]|\\.)*\))""")
_CLOSE = re.compile(r"[ \t]*\)")
# Other `.knott/` folders whose files have a guidance body that may link to pages.
_GUIDANCE_DIRS = (RELATIONS_DIR, CONNECTORS_DIR, LOOPS_DIR)


# --- paths ---------------------------------------------------------------------


def relative_path(target: str, holder: str) -> str:
    """The shortest relative path from the folder of ``holder`` to ``target`` (both
    vault-relative), with ``./`` in front when its first segment has a ``:``, which
    would otherwise read as a URI."""
    path = posixpath.relpath(target, posixpath.dirname(holder) or ".")
    return f"./{path}" if ":" in path.split("/", 1)[0] else path


def _normal(holder: str, path: str) -> str | None:
    """The vault-relative file ``path`` names from ``holder``; None when it leaves the vault."""
    target = posixpath.normpath(posixpath.join(posixpath.dirname(holder), path))
    return None if target == ".." or target.startswith("../") else target


def _encode(path: str, wrapped: bool, *, body: bool) -> str:
    """``path`` as a link destination: inside ``<…>`` when ``wrapped``."""
    special = "%<>" if wrapped else " %()<>"
    if body:
        special += "#"  # in a body link a bare `#` starts a fragment
    return "".join(f"%{ord(ch):02X}" if ch in special else ch for ch in path)


# --- frontmatter values --------------------------------------------------------


@dataclass(frozen=True)
class _Value:
    """How a frontmatter reference or file value names a path."""

    path: str
    """The path it names, decoded."""
    link: re.Match[str] | None
    """The Markdown link match on the stripped value; None for a plain path."""
    wrapped: bool = False

    def with_path(self, value: str, path: str) -> str:
        """``value`` with its path replaced: the form, the label and the outer spaces stay."""
        stripped = value.strip()
        lead = value[: len(value) - len(value.lstrip())]
        tail = value[len(value.rstrip()) :]
        if self.link is None:
            new = f"./{path}" if path.startswith("[") else path
        else:
            destination = _encode(path, self.wrapped, body=False)
            if self.wrapped:
                destination = f"<{destination}>"
            new = f"[{self.link.group('label')}]({destination})"
        assert stripped
        return lead + new + tail


def _value_path(value: str, *, reference: bool) -> _Value | None:
    """The path a reference or file value names; None when it names none (a `kid:`,
    a URI) or is malformed."""
    text = value.strip()
    if text.startswith(KID_PREFIX) and reference:
        return None
    match = _MARKDOWN_LINK.match(text)
    wrapped = False
    if match is not None:
        destination = match.group("dest").strip()
        wrapped = destination.startswith("<") and destination.endswith(">")
        if wrapped:
            destination = destination[1:-1]
        elif any(ch.isspace() for ch in destination):
            return None
        if _URL_SCHEME.match(destination):
            return None
        path = unquote(destination)
        if reference and _URL_SCHEME.match(path):
            return None
    elif text.startswith("[") or _URL_SCHEME.match(text):
        return None
    else:
        path = text
    if not path or "#" in path or "\0" in path or path.startswith(("/", "\\")):
        return None
    if reference:
        try:
            parse_reference(value)
        except LinkError:
            return None
    return _Value(path=path, link=match, wrapped=wrapped)


def _link_values(
    definition: AttributeDef, at: KeyPath, value: Any
) -> Iterator[tuple[KeyPath, bool, str]]:
    """The reference and file strings in ``value``, walked along ``definition`` as
    validation walks it: ``(key path, is a reference, value)``."""
    shape = definition.shape
    if isinstance(shape, ReferenceShape | FileShape):
        if isinstance(value, str) and value.strip():
            yield at, isinstance(shape, ReferenceShape), value
    elif isinstance(shape, ListShape) and type(value) is list:
        for index, item in enumerate(value):
            yield from _link_values(shape.items, (*at, index), item)
    elif isinstance(shape, MapShape) and type(value) is dict:
        for key, item in value.items():
            if isinstance(key, str):
                yield from _link_values(shape.values, (*at, key), item)
    elif isinstance(shape, ObjectShape) and type(value) is dict:
        for name, field_def in shape.fields.items():
            yield from _link_values(field_def, (*at, name), value.get(name))


# --- body links ----------------------------------------------------------------


@dataclass(frozen=True)
class BodyLink:
    """The destination of one inline link or image in a body."""

    start: int
    """Offset of the path in the file's text (inside ``<…>`` when wrapped)."""
    end: int
    raw: str
    """The path as written, without a fragment."""
    fragment: str
    """``#…`` after the path, as written; empty when there is none."""
    wrapped: bool

    @property
    def path(self) -> str:
        return unquote(self.raw)

    @property
    def relative(self) -> bool:
        """Whether the destination is a relative path (not a URL, not absolute, not empty)."""
        raw = self.raw
        return bool(raw) and not _URL_SCHEME.match(raw) and not raw.startswith(("/", "\\"))


def body_links(text: str, start: int) -> list[BodyLink]:
    """Every inline link and image destination in ``text`` from offset ``start`` (the
    body), outside fenced code blocks and inline code spans."""
    links: list[BodyLink] = []
    for region_start, region_end in _unfenced(text, start):
        links.extend(_region_links(text, region_start, region_end))
    return links


def _unfenced(text: str, start: int) -> Iterator[tuple[int, int]]:
    """The stretches of the body outside fenced code blocks."""
    position = region = start
    fence: str | None = None
    while position < len(text):
        newline = text.find("\n", position)
        line_end = len(text) if newline < 0 else newline + 1
        match = _FENCE.match(text[position:line_end].rstrip("\r\n"))
        if match is not None:
            marker, rest = match.group(1), match.group(2)
            if fence is None:
                if marker[0] == "~" or "`" not in rest:
                    if region < position:
                        yield region, position
                    fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not rest.strip():
                fence = None
                region = line_end
        position = line_end
    if fence is None and region < len(text):
        yield region, len(text)


def _region_links(text: str, start: int, end: int) -> Iterator[BodyLink]:
    i = start
    while i < end:
        ch = text[i]
        if ch == "\\":
            i += 2
        elif ch == "`":
            run = 1
            while i + run < end and text[i + run] == "`":
                run += 1
            i = _after_code_span(text, i + run, end, run)
        elif ch == "]" and text.startswith("(", i + 1):
            link = _destination(text, i + 2, end)
            if link is not None:
                yield link
            i += 2
        else:
            i += 1


def _after_code_span(text: str, i: int, end: int, run: int) -> int:
    """Where scanning resumes after an opening run of ``run`` backticks that ends at ``i``:
    past the closing run of the same length in the same paragraph, else at ``i``."""
    paragraph = _BLANK_LINE.search(text, i, end)
    limit = paragraph.start() if paragraph is not None else end
    j = i
    while j < limit:
        if text[j] != "`":
            j += 1
            continue
        closing = 1
        while j + closing < limit and text[j + closing] == "`":
            closing += 1
        if closing == run:
            return j + closing
        j += closing
    return i


def _destination(text: str, i: int, end: int) -> BodyLink | None:
    """The link destination that starts at ``i``, just after ``](``; None when what
    follows is not ``dest``, an optional title and ``)``."""
    while i < end and text[i] in " \t":
        i += 1
    wrapped = i < end and text[i] == "<"
    if wrapped:
        close = i + 1
        while close < end and text[close] not in "<>\n":
            close += 1
        if close >= end or text[close] != ">":
            return None
        first, last, after = i + 1, close, close + 1
    else:
        depth = 0
        j = i
        while j < end and not text[j].isspace():
            if text[j] == "\\" and j + 1 < end:
                j += 1
            elif text[j] == "(":
                depth += 1
            elif text[j] == ")":
                if depth == 0:
                    break
                depth -= 1
            j += 1
        first, last, after = i, j, j
    title = _TITLE.match(text, after, end)
    if title is not None:
        after = title.end()
    if _CLOSE.match(text, after, end) is None:
        return None
    destination = text[first:last]
    raw, hash_mark, fragment = destination.partition("#")
    return BodyLink(first, first + len(raw), raw, hash_mark + fragment, wrapped)


def _body_start(text: str, parsed: MarkdownFile) -> int:
    """Offset of the body: after the closing ``---`` line, or the start of a file
    without frontmatter."""
    offset = len(_BOM) if text.startswith(_BOM) else 0
    if parsed.frontmatter is None:
        return offset
    starts = _line_starts(text)
    lines = _LINE.split(text[offset:])
    closing = lines.index(FRONTMATTER_DELIMITER, 1)
    return starts[closing + 1] if closing + 1 < len(starts) else len(text)


def _line_starts(text: str) -> list[int]:
    """Offset of each line of ``text``, split as ``parse_markdown`` splits it."""
    offset = len(_BOM) if text.startswith(_BOM) else 0
    starts = [offset]
    starts.extend(match.end() for match in _LINE.finditer(text, offset))
    return starts


def _line_of(text: str, offset: int) -> int:
    """1-based line of ``offset``."""
    return text.count("\n", 0, offset) + 1


# --- planning ------------------------------------------------------------------


@dataclass
class _Edit:
    """One rewritten link in a file."""

    start: int
    end: int
    text: str
    """What replaces ``[start, end)`` of the file's text."""
    target: str
    """The vault-relative file the link must name after the move."""
    line: int
    at: KeyPath | None
    """The frontmatter value's key path; None for a body link."""
    old: str
    new: str
    reference: bool = True
    index: int = -1
    """For a body link: its position among the body's links."""


@dataclass
class _File:
    """One file the move reads, with the edits prepared for it."""

    path: str
    """Vault-relative path now."""
    new_path: str
    """Vault-relative path after the move."""
    text: str
    parsed: MarkdownFile
    edits: list[_Edit] = field(default_factory=list)
    new_text: str = ""


class Mover:
    """Plans and performs one move in a vault."""

    def __init__(self, session: VaultSession, source: str, dest: str) -> None:
        self.session = session
        self.root = session.root
        self.source = source
        self.dest = dest
        self.folder_changes = posixpath.dirname(source) != posixpath.dirname(dest)
        self.unchanged: list[UnchangedLink] = []
        self.skipped: list[SkippedFile] = []

    # .. reading ..

    def _read(self, path: str) -> _File | None:
        """The file at ``path``; None, recorded as skipped, when it cannot be read."""
        if (self.root / path).is_symlink():
            # Replacing it would replace the link, and its target may be outside the vault.
            reason = "is a symbolic link, which knott does not edit"
            self.skipped.append(SkippedFile(path=path, reason=reason))
            return None
        try:
            text = (self.root / path).read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            why = str(exc.strerror) if isinstance(exc, OSError) else "file is not valid UTF-8"
            self.skipped.append(SkippedFile(path=path, reason=f"cannot read the file: {why}"))
            return None
        parsed = parse_markdown(text, path)
        if parsed.error is not None:
            self.skipped.append(
                SkippedFile(path=path, reason=f"cannot read the frontmatter: {parsed.error}")
            )
            return None
        return _File(path, self.dest if path == self.source else path, text, parsed)

    def _searched(self) -> list[tuple[str, bool]]:
        """Every file searched for links, in path order: ``(path, frontmatter too)``."""
        found = [(path, True) for path in self.session.all_markdown]
        for folder in _GUIDANCE_DIRS:
            base = self.root / folder
            if base.is_dir():
                found.extend(
                    (p.relative_to(self.root).as_posix(), False)
                    for p in base.rglob("*.md")
                    if p.is_file()
                )
        return sorted(found)

    def _exists(self, target: str) -> bool:
        return _exists_exact_case(self.root, target, self.session.list_dir)

    # .. finding links ..

    def _new_target(self, holder: _File, target: str | None) -> str | None:
        """Where a link of ``holder`` that names ``target`` must point after the move;
        None when the link is left alone."""
        if target == self.source:
            return self.dest
        if holder.path == self.source and self.folder_changes and target is not None:
            return target
        return None

    def _plan_frontmatter(self, holder: _File, schema: Schema) -> None:
        own = holder.path == self.source and self.folder_changes
        frontmatter = holder.parsed.frontmatter or {}
        for name, definition in schema.properties.items():
            for at, reference, value in _link_values(definition, (name,), frontmatter.get(name)):
                named = _value_path(value, reference=reference)
                line = holder.parsed.line_of(at)
                if named is None:
                    # a `kid:` or a URI names no path; anything else is malformed
                    text = value.strip()
                    is_other = text.startswith(KID_PREFIX) or (
                        not reference and bool(_URL_SCHEME.match(text))
                    )
                    if own and not is_other:
                        self._unchanged(holder, line, at, value, f"`{text}` is not a path")
                    continue
                target = _normal(holder.path, named.path)
                if target is None or not self._exists(target):
                    if own:
                        self._unchanged(holder, line, at, value, _why(named.path, target))
                    continue
                new_target = self._new_target(holder, target)
                if new_target is None:
                    continue
                path = relative_path(new_target, holder.new_path)
                new_value = named.with_path(value, path)
                if new_value == value:
                    continue
                holder.edits.append(
                    self._frontmatter_edit(holder, at, value, new_value, new_target, reference)
                )

    def _plan_body(self, holder: _File) -> None:
        own = holder.path == self.source and self.folder_changes
        links = body_links(holder.text, _body_start(holder.text, holder.parsed))
        for index, link in enumerate(links):
            if not link.relative:
                continue
            target = _normal(holder.path, link.path)
            line = _line_of(holder.text, link.start)
            if target is None or not self._exists(target):
                if own:
                    value = link.raw + link.fragment
                    self._unchanged(holder, line, None, value, _why(link.path, target))
                continue
            new_target = self._new_target(holder, target)
            if new_target is None:
                continue
            path = _encode(relative_path(new_target, holder.new_path), link.wrapped, body=True)
            if path == link.raw:
                continue
            holder.edits.append(
                _Edit(
                    start=link.start,
                    end=link.end,
                    text=path,
                    target=new_target,
                    line=line,
                    at=None,
                    old=link.raw + link.fragment,
                    new=path + link.fragment,
                    index=index,
                )
            )

    def _unchanged(
        self, holder: _File, line: int | None, at: KeyPath | None, value: str, reason: str
    ) -> None:
        self.unchanged.append(
            UnchangedLink(
                path=holder.new_path,
                line=line,
                field=None if at is None else format_field_path(at),
                value=value,
                reason=reason,
            )
        )

    # .. editing a frontmatter value in place ..

    def _frontmatter_edit(
        self,
        holder: _File,
        at: KeyPath,
        value: str,
        new_value: str,
        target: str,
        reference: bool,
    ) -> _Edit:
        field_name = format_field_path(at)
        loc = holder.parsed.scalars.get(at)
        problem = None
        if loc is None or loc.start is None or loc.end is None:
            problem = "its value comes from a YAML merge or alias"
        elif loc.shared:
            problem = "its value is shared through a YAML alias"
        elif loc.style in ("|", ">"):
            problem = "it is written as a block scalar"
        if problem is None:
            assert loc is not None and loc.start is not None and loc.end is not None
            start, end = self._offsets(holder.text, loc.start, loc.end)
            source = holder.text[start:end]
            if "\n" in source or "\r" in source:
                problem = "its value spans several lines"
            elif not _is_scalar_text(source, loc.style, loc.raw):
                problem = "its value cannot be located in the file"
        if problem is not None:
            raise KnottError(
                f"cannot rewrite `{field_name}` in {holder.path} in place: {problem}; "
                f"write it as a one-line value, then run the move again"
            )
        assert loc is not None
        expected = copy.deepcopy(holder.parsed.frontmatter)
        _set(expected, at, new_value)
        if loc.style == "'":
            forms = ["'" + new_value.replace("'", "''") + "'"]
        elif loc.style == '"':
            forms = [_double_quoted(new_value)]
        else:
            forms = [new_value, _double_quoted(new_value)]
        for form in forms:
            candidate = holder.text[:start] + form + holder.text[end:]
            reparsed = parse_markdown(candidate, holder.path)
            if reparsed.error is None and _same(reparsed.frontmatter, expected):
                return _Edit(
                    start=start,
                    end=end,
                    text=form,
                    target=target,
                    line=holder.parsed.line_of(at) or _line_of(holder.text, start),
                    at=at,
                    old=value,
                    new=new_value,
                    reference=reference,
                )
        raise KnottError(
            f"cannot rewrite `{field_name}` in {holder.path} in place: "
            f"the new value `{new_value}` cannot be written there"
        )

    @staticmethod
    def _offsets(text: str, start: int, end: int) -> tuple[int, int]:
        """Offsets in the file's text of ``[start, end)`` of its frontmatter's YAML text."""
        starts = _line_starts(text)
        offset = len(_BOM) if text.startswith(_BOM) else 0
        lines = _LINE.split(text[offset:])
        yaml_text = "\n".join(lines[1 : lines.index(FRONTMATTER_DELIMITER, 1)])

        def locate(index: int) -> int:
            line = yaml_text.count("\n", 0, index)
            column = index - (yaml_text.rfind("\n", 0, index) + 1)
            return starts[line + 1] + column

        return locate(start), locate(end)

    # .. the plan ..

    def plan(self) -> list[_File]:
        """Read every searched file and prepare its edits; the moved file is always
        included. Raises ``KnottError`` when an edit cannot be made or a check fails."""
        files: list[_File] = []
        for path, with_frontmatter in self._searched():
            holder = self._read(path)
            if holder is None:
                if path == self.source:
                    raise KnottError(f"cannot read {path}: {self.skipped[-1].reason}")
                continue
            entity_type = holder.parsed.type if holder.parsed.is_entity else None
            schema = self.session.schemas.get(entity_type) if type(entity_type) is str else None
            if with_frontmatter and schema is not None:
                self._plan_frontmatter(holder, schema)
            self._plan_body(holder)
            if holder.edits or path == self.source:
                self._apply(holder)
                files.append(holder)
        return files

    def _apply(self, holder: _File) -> None:
        """Build the file's new text and check it (decision 0013, point 3)."""
        text = holder.text
        for edit in sorted(holder.edits, key=lambda e: e.start, reverse=True):
            text = text[: edit.start] + edit.text + text[edit.end :]
        holder.new_text = text
        if not holder.edits:
            return
        expected = copy.deepcopy(holder.parsed.frontmatter)
        for edit in holder.edits:
            if edit.at is not None:
                _set(expected, edit.at, edit.new)
        reparsed = parse_markdown(text, holder.path)
        if reparsed.error is not None or not _same(reparsed.frontmatter, expected):
            raise KnottError(
                f"check failed for {holder.path}: the rewritten frontmatter does not read "
                "back as the old one with only the links changed; nothing was written"
            )
        old_links = body_links(holder.text, _body_start(holder.text, holder.parsed))
        new_links = body_links(text, _body_start(text, reparsed))
        if len(old_links) != len(new_links):
            raise KnottError(
                f"check failed for {holder.path}: its body links changed; nothing was written"
            )
        for edit in holder.edits:
            if edit.at is None:
                named: str | None = new_links[edit.index].path
            else:
                value = _value_path(_get(reparsed.frontmatter, edit.at), reference=edit.reference)
                named = None if value is None else value.path
            if named is None or _normal(holder.new_path, named) != edit.target:
                where = "body" if edit.at is None else format_field_path(edit.at)
                raise KnottError(
                    f"check failed for {holder.path}:{edit.line} ({where}): the rewritten link "
                    f"`{edit.new}` would not name {edit.target}; nothing was written"
                )

    # .. the result ..

    def result(self, files: list[_File], *, dry_run: bool) -> MoveResult:
        updated = [
            UpdatedLink(
                path=holder.new_path,
                line=edit.line,
                field=None if edit.at is None else format_field_path(edit.at),
                old=edit.old,
                new=edit.new,
            )
            for holder in files
            for edit in holder.edits
        ]
        moved = next(holder for holder in files if holder.path == self.source)
        return MoveResult(
            from_=self.source,
            to=self.dest,
            kid=entity_kid(self.session, self.source) if moved.parsed.is_entity else None,
            dry_run=dry_run,
            updated=sorted(updated, key=lambda u: (u.path, u.line or 0, u.field or "")),
            unchanged=sorted(self.unchanged, key=lambda u: (u.path, u.line or 0, u.field or "")),
            skipped=sorted(self.skipped, key=lambda s: s.path),
            issues=self._placement_issues(moved),
        )

    def _placement_issues(self, moved: _File) -> list[Issue]:
        """`entity-misplaced` and `entity-invalid-name` for the entity at its new path."""
        entity_type = moved.parsed.type if moved.parsed.is_entity else None
        schema = self.session.schemas.get(entity_type) if type(entity_type) is str else None
        if schema is None:
            return []
        at_dest = dataclasses.replace(moved.parsed, path=self.dest)
        return [*_check_location(at_dest, schema), *_check_name(at_dest, schema)]

    # .. writing ..

    def write(self, files: list[_File]) -> None:
        """Write the moved file at its new path, then each referring file, then remove
        the old file. Raises ``MoveError`` naming the files already written."""
        moved = next(holder for holder in files if holder.path == self.source)
        source, dest = self.root / self.source, self.root / self.dest
        in_place = (
            dest.exists()
        )  # a rename that only changes case, on a file system that ignores it
        written: list[str] = []
        try:
            if not in_place:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "xb") as handle:
                    try:
                        handle.write(moved.new_text.encode("utf-8"))
                    except OSError:
                        # never leave half a file where the next run would refuse to write
                        dest.unlink(missing_ok=True)
                        raise
                written.append(self.dest)
                os.chmod(dest, source.stat().st_mode & 0o7777)
            for holder in files:
                if holder is not moved:
                    _write_atomic(self.root / holder.path, holder.new_text)
                    written.append(holder.path)
            if in_place:
                if moved.new_text != moved.text:
                    _write_atomic(source, moved.new_text)
                os.rename(source, dest)
                written.append(self.dest)
            else:
                source.unlink()
        except OSError as exc:
            listed = ", ".join(written) or "none"
            raise MoveError(
                f"the move stopped: {exc.strerror or exc} ({exc.filename or self.dest}); "
                f"files already written: {listed}; {self.source} "
                f"{'still exists' if source.exists() else 'is gone'}",
                written=written,
            ) from exc


def _is_scalar_text(source: str, style: str | None, raw: str | None) -> bool:
    """Whether ``source`` is the text of a one-line scalar: the plain value itself,
    or a quoted one with its quotes."""
    if style is None:
        return source == raw
    return len(source) >= 2 and source[0] == source[-1] == style


def _why(path: str, target: str | None) -> str:
    if target is None:
        return f"`{path}` resolves to a path outside the vault root"
    return f"`{path}` does not exist"


def _double_quoted(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _set(data: Any, at: KeyPath, value: Any) -> None:
    for key in at[:-1]:
        data = data[key]
    data[at[-1]] = value


def _get(data: Any, at: KeyPath) -> Any:
    for key in at:
        data = data[key]
    return data


def _same(a: Any, b: Any) -> bool:
    """Equal values of the same kinds: ``1`` is not ``1.0`` or ``True``, ``.nan`` is itself."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return list(a) == list(b) and all(_same(a[key], b[key]) for key in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) and math.isnan(a):
        return math.isnan(b)
    return bool(a == b)


# --- checking SOURCE and DEST ---------------------------------------------------


def check_destination(root: Path, source: str, dest: Path) -> str:
    """The vault-relative path of the new file. ``dest`` is absolute; an existing
    directory keeps the file's name. Raises ``KnottError`` for a place a file cannot
    be moved to."""
    if dest.is_dir():
        dest = dest / posixpath.basename(source)
    absolute = Path(os.path.abspath(dest))
    # Resolve symlinks in the folders that exist, so the path is the one discovery sees.
    existing = absolute.parent
    missing: list[str] = []
    while not existing.exists():
        missing.append(existing.name)
        existing = existing.parent
    if not existing.is_dir():
        raise KnottError(f"DEST is under a file, not a folder: {existing.name}")
    real = existing.resolve().joinpath(*reversed(missing)) / absolute.name
    try:
        rel = real.relative_to(root.resolve())
    except ValueError:
        raise KnottError(f"DEST is outside the vault {root}: {dest}") from None
    rel_posix = rel.as_posix()
    if not rel_posix.endswith(".md"):
        raise KnottError(
            f"DEST must be a Markdown file or an existing folder: {rel_posix} does not end in `.md`"
        )
    if any(part.startswith(".") for part in rel.parts[:-1]):
        raise KnottError(f"DEST is in a hidden folder, where knott does not look: {rel_posix}")
    if "#" in rel_posix:
        raise KnottError(f"DEST has a `#` in its path, so no reference could name it: {rel_posix}")
    if rel_posix == source:
        raise KnottError(f"SOURCE and DEST are the same file: {rel_posix}")
    if os.path.lexists(root / rel_posix):
        same = (root / rel_posix).exists() and os.path.samefile(root / rel_posix, root / source)
        if not (same and rel_posix.lower() == source.lower()):
            raise KnottError(f"DEST already exists: {rel_posix}; nothing is ever overwritten")
    return rel_posix


def move_file(
    session: VaultSession, source: str, dest: Path, *, dry_run: bool = False
) -> MoveResult:
    """Move ``source`` (vault-relative, a file discovery sees) to ``dest`` (absolute)."""
    root = session.root
    if source not in session.all_markdown:
        raise KnottError(
            f"not a Markdown file knott sees: {source}; expected a `.md` file in the vault, "
            "outside `.knott/` and hidden folders"
        )
    if (root / source).is_symlink():
        raise KnottError(f"SOURCE is a symbolic link, which knott does not follow: {source}")
    parsed = session.lookup(source)
    if parsed.error is not None:
        raise KnottError(f"cannot read the frontmatter of {source}: {parsed.error}")
    mover = Mover(session, source, check_destination(root, source, dest))
    files = mover.plan()
    result = mover.result(files, dry_run=dry_run)
    if not dry_run:
        mover.write(files)
    return result
