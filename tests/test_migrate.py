from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from knott import Knott, MigrateResult
from knott.errors import KnottError, MigrateError
from knott.schema.migrate import convert_legacy, legacy_list_fields, migrate_vault
from knott.vault.entity import parse_markdown


def frontmatter(text: str) -> dict[str, Any]:
    assert text.startswith("---\n") and text.endswith("---\n")
    parsed = parse_markdown(text, "concept.md")
    assert parsed.error is None
    assert parsed.frontmatter is not None
    return parsed.frontmatter


def test_attributes_pass_through_unchanged_and_relation_becomes_reference() -> None:
    nested = {
        "type": "list",
        "required": True,
        "items": {
            "type": "object",
            "fields": {
                "lang": {"type": "string", "required": True},
                "tags": {"type": "map", "values": {"type": "integer"}},
            },
        },
    }
    data = {
        "type": "transcript",
        "attributes": {
            "title": {"type": "string", "required": True},
            "senses": nested,
        },
        "relations": {
            "derived_from": {"target": "script", "required": True, "description": "Source."},
        },
    }
    assert frontmatter(convert_legacy(data, set())) == {
        "name": "transcript",
        "properties": {
            "title": {"type": "string", "required": True},
            "senses": nested,
            "derived_from": {
                "type": "reference",
                "target": "script",
                "required": True,
                "description": "Source.",
            },
        },
    }


def test_list_used_relation_becomes_list_of_reference_with_required_on_list() -> None:
    data = {
        "type": "decision",
        "relations": {
            "affects": {"target": "concept", "required": True, "description": "Concepts."},
            "supersedes": {"target": "decision"},
        },
    }
    result = frontmatter(convert_legacy(data, {"affects"}))
    assert result["properties"] == {
        "affects": {
            "type": "list",
            "required": True,
            "description": "Concepts.",
            "items": {"type": "reference", "target": "concept"},
        },
        "supersedes": {"type": "reference", "target": "decision"},
    }


def test_key_order_is_name_description_kid_then_attributes_then_relations() -> None:
    data = {
        "relations": {"z_rel": {"target": "a"}, "a_rel": {"target": "a"}},
        "kid": "required",
        "attributes": {"zeta": {"type": "string"}, "alpha": {"type": "date"}},
        "description": "A thing.",
        "type": "a",
    }
    result = frontmatter(convert_legacy(data, set()))
    assert list(result) == ["name", "description", "kid", "properties"]
    assert list(result["properties"]) == ["zeta", "alpha", "z_rel", "a_rel"]
    assert result["kid"] == "required"


def test_descriptions_survive_including_multi_line() -> None:
    folded = "An architecture decision record: a choice made where the spec was silent.\n"
    multi = "First line.\nSecond line.\n\nNew paragraph.\n"
    long_line = "word " * 60
    data = {
        "type": "decision",
        "description": folded,
        "attributes": {
            "status": {"type": "string", "description": multi},
            "note": {"type": "string", "description": long_line.strip()},
        },
        "relations": {"affects": {"target": "concept", "description": multi}},
    }
    text = convert_legacy(data, {"affects"})
    assert "description: >\n" in text
    # Wide output: a long single-line description is never wrapped.
    assert f"description: {long_line.strip()}\n" in text
    result = frontmatter(text)
    assert result["description"] == folded
    assert result["properties"]["status"]["description"] == multi
    assert result["properties"]["note"]["description"] == long_line.strip()
    assert result["properties"]["affects"]["description"] == multi


def test_schema_without_fields_has_no_properties_key() -> None:
    assert frontmatter(convert_legacy({"type": "empty"}, set())) == {"name": "empty"}


def test_output_is_block_style() -> None:
    data = {"type": "a", "relations": {"r": {"target": "a"}}}
    assert convert_legacy(data, set()) == (
        "---\nname: a\nproperties:\n  r:\n    type: reference\n    target: a\n---\n"
    )


@pytest.mark.parametrize("data", [None, [], "type: a", 3])
def test_non_mapping_input_raises(data: Any) -> None:
    with pytest.raises(MigrateError, match="must be a YAML mapping"):
        convert_legacy(data, set())


def test_missing_type_raises() -> None:
    with pytest.raises(MigrateError, match="missing required key `type`"):
        convert_legacy({"description": "x"}, set())


def test_unknown_top_level_key_names_it() -> None:
    with pytest.raises(MigrateError, match="unknown key `fields`"):
        convert_legacy({"type": "a", "fields": {}}, set())


def test_unknown_relation_key_names_it() -> None:
    data = {"type": "a", "relations": {"r": {"target": "a", "inverse": "b"}}}
    with pytest.raises(MigrateError, match=r"unknown key `inverse` in `relations\.r`"):
        convert_legacy(data, set())


def test_relation_without_target_raises() -> None:
    with pytest.raises(MigrateError, match="relation `r` is missing `target`"):
        convert_legacy({"type": "a", "relations": {"r": {"required": True}}}, set())


def test_name_declared_as_attribute_and_relation_raises() -> None:
    data = {
        "type": "a",
        "attributes": {"x": {"type": "string"}},
        "relations": {"x": {"target": "a"}},
    }
    with pytest.raises(MigrateError, match="field `x` is declared both"):
        convert_legacy(data, set())


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"type": 3}, "`type` must be a string"),
        ({"type": "a", "attributes": ["x"]}, "`attributes` must be a mapping"),
        ({"type": "a", "relations": {"r": "script"}}, r"`relations\.r` must be a mapping"),
    ],
)
def test_malformed_sections_raise(data: dict[str, Any], message: str) -> None:
    with pytest.raises(MigrateError, match=message):
        convert_legacy(data, set())


def test_migrate_error_is_a_knott_error() -> None:
    assert issubclass(MigrateError, KnottError)


def test_legacy_list_fields_only_counts_lists_on_entities_of_that_type() -> None:
    entities: list[dict[str, Any]] = [
        {"type": "decision", "affects": ["[a](a.md)"], "supersedes": "[b](b.md)"},
        {"type": "decision", "affects": "[c](c.md)"},
        {"type": "concept", "supersedes": ["[d](d.md)"]},
        {"type": "decision", "related": ["[e](e.md)"]},
        {"title": "no type", "supersedes": ["[f](f.md)"]},
    ]
    found = legacy_list_fields("decision", ["affects", "supersedes"], entities)
    assert found == {"affects"}


def test_legacy_list_fields_empty_when_no_entities() -> None:
    assert legacy_list_fields("decision", ["affects"], []) == set()


# --- migrate_vault / Knott.migrate ---------------------------------------------


def snapshot(root: Path) -> dict[str, bytes | None]:
    """Every path under ``root`` with its content (``None`` for directories)."""
    return {
        p.relative_to(root).as_posix(): None if p.is_dir() else p.read_bytes()
        for p in sorted(root.rglob("*"))
    }


def concept(root: Path, rel: str) -> dict[str, Any]:
    text = (root / rel).read_text(encoding="utf-8")
    assert text.endswith("---\n")  # frontmatter only, empty body
    return frontmatter(text)


def test_migrate_legacy_layout_writes_concepts_and_gives_a_valid_vault(
    copy_fixture: Callable[[str], Path],
) -> None:
    root = copy_fixture("legacy-layout")
    vault = Knott.open(root)
    assert [i.code for i in vault.validate().issues] == ["schema-legacy-layout"]

    result = vault.migrate()

    assert result == MigrateResult(
        written=[
            ".knott/concepts/compilation.md",
            ".knott/concepts/media/episode.md",
            ".knott/concepts/script.md",
        ],
        removed=".knott/schemas",
        list_fields=["compilation.sources"],
    )
    assert not (root / ".knott/schemas").exists()
    assert concept(root, ".knott/concepts/compilation.md") == {
        "name": "compilation",
        "properties": {
            "title": {"type": "string"},
            "sources": {
                "type": "list",
                "required": True,
                "description": "Scripts collected here.",
                "items": {"type": "reference", "target": "script"},
            },
            "featured": {"type": "reference", "target": "episode"},
        },
    }
    assert concept(root, ".knott/concepts/media/episode.md") == {
        "name": "episode",
        "description": "A published episode, recorded from one script.\n",
        "kid": "required",
        "properties": {
            "title": {"type": "string", "required": True},
            "script": {
                "type": "reference",
                "target": "script",
                "required": True,
                "description": "The script this episode was recorded from.",
            },
        },
    }
    validation = vault.validate()
    assert validation.ok, validation.issues
    assert (validation.stats.schemas, validation.stats.entities) == (3, 4)
    assert validation.stats.relations == 4
    assert vault.types() == ["compilation", "episode", "script"]


def test_migrate_ignores_entities_of_other_types_and_invalid_frontmatter(tmp_path: Path) -> None:
    (tmp_path / ".knott/schemas").mkdir(parents=True)
    (tmp_path / ".knott/schemas/note.yaml").write_text(
        "type: note\nrelations:\n  about:\n    target: note\n", encoding="utf-8"
    )
    (tmp_path / "other.md").write_text("---\ntype: other\nabout: [a.md]\n---\n")
    (tmp_path / "broken.md").write_text("---\ntype: note\nabout: [\n---\n")
    result = migrate_vault(tmp_path)
    assert result.list_fields == []
    assert concept(tmp_path, ".knott/concepts/note.md")["properties"] == {
        "about": {"type": "reference", "target": "note"}
    }


def test_migrate_empty_legacy_folder_creates_concepts_folder(tmp_path: Path) -> None:
    (tmp_path / ".knott/schemas").mkdir(parents=True)
    (tmp_path / ".knott/schemas/.DS_Store").write_bytes(b"\0")
    result = migrate_vault(tmp_path)
    assert result.written == []
    assert (tmp_path / ".knott/concepts").is_dir()
    assert not (tmp_path / ".knott/schemas").exists()


def _legacy_vault(root: Path) -> Path:
    (root / ".knott/schemas/sub").mkdir(parents=True)
    (root / ".knott/schemas/a.yaml").write_text("type: a\n", encoding="utf-8")
    (root / ".knott/schemas/sub/b.yaml").write_text("type: b\n", encoding="utf-8")
    return root


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        pytest.param(
            lambda r: (r / ".knott/schemas/sub/b.yaml").write_text("type: [b\n"),
            ".knott/schemas/sub/b.yaml:2: invalid YAML",
            id="broken-yaml",
        ),
        pytest.param(
            lambda r: (r / ".knott/schemas/sub/b.yaml").write_text("type: b\nfields: {}\n"),
            ".knott/schemas/sub/b.yaml: unknown key `fields`",
            id="unknown-key",
        ),
        pytest.param(
            lambda r: (r / ".knott/schemas/a.yaml").write_text(
                "type: a\nrelations:\n  x:\n    target: a\n    kind: one\n"
            ),
            ".knott/schemas/a.yaml: unknown key `kind` in `relations.x`",
            id="unknown-relation-key",
        ),
        pytest.param(
            lambda r: (r / ".knott/schemas/a.yaml").write_bytes(b"type: \xff\n"),
            ".knott/schemas/a.yaml: file is not valid UTF-8",
            id="not-utf8",
        ),
        pytest.param(
            lambda r: (
                (r / ".knott/concepts").mkdir(parents=True),
                (r / ".knott/concepts/sub").write_text("a file\n"),
            ),
            ".knott/concepts/sub is not a folder",
            id="parent-is-a-file",
        ),
        pytest.param(
            lambda r: (r / ".knott/concepts").write_text("a file\n"),
            ".knott/concepts is not a folder",
            id="concepts-is-a-file",
        ),
        pytest.param(
            lambda r: (r / ".knott/schemas/notes.txt").write_text("keep me\n"),
            ".knott/schemas/notes.txt: not a `.yaml` schema",
            id="other-file",
        ),
        pytest.param(
            lambda r: (
                (r / ".knott/concepts/sub").mkdir(parents=True),
                (r / ".knott/concepts/sub/b.md").write_text("---\nname: b\n---\n"),
            ),
            ".knott/concepts/sub/b.md already exists",
            id="existing-concept",
        ),
    ],
)
def test_migrate_refuses_and_changes_nothing(
    tmp_path: Path, setup: Callable[[Path], object], message: str
) -> None:
    root = _legacy_vault(tmp_path)
    setup(root)
    before = snapshot(root)
    with pytest.raises(MigrateError) as raised:
        migrate_vault(root)
    assert message in str(raised.value)
    assert snapshot(root) == before


def test_migrate_without_legacy_folder_refuses(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    before = snapshot(tmp_path)
    with pytest.raises(MigrateError, match="nothing to migrate"):
        Knott.open(tmp_path).migrate()
    assert snapshot(tmp_path) == before


def test_migrate_refuses_symlinked_legacy_folder(tmp_path: Path) -> None:
    real = tmp_path / "real-schemas"
    real.mkdir()
    (real / "a.yaml").write_text("type: a\n", encoding="utf-8")
    root = tmp_path / "vault"
    (root / ".knott").mkdir(parents=True)
    (root / ".knott/schemas").symlink_to(real, target_is_directory=True)
    before = snapshot(tmp_path)
    with pytest.raises(MigrateError, match="is a symbolic link"):
        migrate_vault(root)
    assert snapshot(tmp_path) == before


def test_migrate_write_failure_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _legacy_vault(tmp_path)
    before = snapshot(root)
    real_write = Path.write_text

    def failing_write(self: Path, *args: Any, **kwargs: Any) -> int:
        if self.name == "b.md":
            raise OSError(28, "No space left on device", str(self))
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write)
    with pytest.raises(MigrateError) as raised:
        migrate_vault(root)
    message = str(raised.value)
    assert ".knott/concepts/sub/b.md: No space left on device" in message
    assert "nothing was changed" in message
    assert snapshot(root) == before


def test_migrate_write_failure_keeps_existing_concepts_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _legacy_vault(tmp_path)
    (root / ".knott/concepts").mkdir()
    before = snapshot(root)

    def failing_write(self: Path, *args: Any, **kwargs: Any) -> int:
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "write_text", failing_write)
    with pytest.raises(MigrateError, match="nothing was changed"):
        migrate_vault(root)
    assert snapshot(root) == before


def test_migrate_keeps_concepts_when_legacy_folder_cannot_be_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _legacy_vault(tmp_path)

    def failing_rmtree(path: Path) -> None:
        raise PermissionError(13, "Permission denied", str(path / "a.yaml"))

    monkeypatch.setattr("knott.schema.migrate.shutil.rmtree", failing_rmtree)
    with pytest.raises(MigrateError) as raised:
        migrate_vault(root)
    message = str(raised.value)
    assert "concept files written, but `.knott/schemas/` could not be removed" in message
    assert ".knott/schemas/a.yaml: Permission denied" in message
    assert "delete `.knott/schemas/` by hand" in message
    assert concept(root, ".knott/concepts/a.md") == {"name": "a"}
    assert concept(root, ".knott/concepts/sub/b.md") == {"name": "b"}
