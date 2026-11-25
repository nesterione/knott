"""File properties and connector files (spec 0008)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import ConnectorDefinition, Knott
from knott.cli import app
from knott.models import Issue
from knott.schema.loader import load_definitions
from knott.schema.models import FileShape, ListShape
from knott.vault.files import file_extension
from tests.conftest import fixture_path, triples

runner = CliRunner()

CONCEPT = """---
name: recording
properties:
  audio: { type: file, accept: [mp3, wav] }
  slides: { type: file }
  images:
    type: list
    items: { type: file, accept: [png] }
---
"""


def _write(root: Path, rel: str, text: str = "x") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _vault(
    tmp_path: Path,
    concept: str = CONCEPT,
    connectors: dict[str, str] | None = None,
) -> Path:
    Knott.init(tmp_path)
    _write(tmp_path, ".knott/concepts/recording.md", concept)
    for name, text in (
        {"gdrive": "---\nname: gdrive\n---\n"} if connectors is None else connectors
    ).items():
        _write(tmp_path, f".knott/connectors/{name}.md", text)
    _write(tmp_path, "audio/take.mp3")
    _write(tmp_path, "img/a.png")
    return tmp_path


def _entity(root: Path, frontmatter: str, rel: str = "recordings/ep.md") -> list[Issue]:
    _write(root, rel, f"---\ntype: recording\n{frontmatter}---\n")
    return Knott.open(root).validate().issues


def _codes(issues: list[Issue]) -> list[tuple[str | None, str]]:
    return [(i.field, i.code) for i in issues]


# --- the fixture vault --------------------------------------------------------


def test_fixture_vault_is_valid_and_output_is_unchanged() -> None:
    result = Knott.open(fixture_path("file-properties")).validate()
    assert result.ok, result.issues
    # File values are attributes: they never count as relations, and add no stats.
    assert result.stats.model_dump() == {"schemas": 1, "entities": 1, "relations": 0}


def test_connectors_are_discovered_by_name() -> None:
    loaded = load_definitions(fixture_path("file-properties"))
    assert loaded.issues == []
    # Subfolders only organise; the file name is not the identity; other files are ignored.
    assert sorted(loaded.connectors) == ["gdrive", "s3"]
    assert loaded.connectors["s3"].path == ".knott/connectors/cloud/bucket.md"
    assert loaded.connectors["s3"].guidance is None
    assert loaded.connectors["gdrive"].guidance == (
        "<!-- Open as https://drive.google.com/file/d/<id>. Upload with the drive skill. -->\n"
    )
    audio = loaded.schemas["recording"].properties["audio"].shape
    assert audio == FileShape(("mp3", "wav"))
    images = loaded.schemas["recording"].properties["images"].shape
    assert isinstance(images, ListShape) and images.items.shape == FileShape(("png", "jpg"))


def test_ontology_lists_connectors_and_accept() -> None:
    ontology = Knott.open(fixture_path("file-properties")).ontology()
    assert ontology.connectors == [
        ConnectorDefinition(
            name="gdrive",
            description=(
                "The team's shared Google Drive. Written gdrive:<file id from the share link>."
            ),
            guidance=(
                "<!-- Open as https://drive.google.com/file/d/<id>. "
                "Upload with the drive skill. -->\n"
            ),
            path=".knott/connectors/gdrive.md",
        ),
        ConnectorDefinition(
            name="s3", description=None, guidance=None, path=".knott/connectors/cloud/bucket.md"
        ),
    ]
    (recording,) = ontology.types
    by_name = {p.name: p for p in recording.properties}
    assert by_name["audio"].type == "file"
    assert by_name["audio"].accept == ["mp3", "wav"]
    assert by_name["slides"].accept == []
    assert by_name["images"].notation == "list of file"
    assert by_name["images"].items is not None and by_name["images"].items.accept == ["png", "jpg"]
    # A file is not a reference: no edge, nothing for `knott refs`.
    assert recording.references() == []


def test_types_verbose_shows_files_and_connectors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("file-properties"))
    result = runner.invoke(app, ["types", "--verbose"])
    assert result.exit_code == 0
    assert (
        result.stdout
        == """\
recording  (.knott/concepts/recording.md)
  A recorded episode with its audio and pictures.
  template: no
  references: none
  properties:
    title*   string
    audio*   file .mp3 | .wav          The mixed take.
    slides   file
    images   list of file .png | .jpg
    extras   map of file
    credits  list of object
      photo*   file
      caption  string

connectors:
  gdrive
    The team's shared Google Drive. Written gdrive:<file id from the share link>.
    <!-- Open as https://drive.google.com/file/d/<id>. Upload with the drive skill. -->

  s3
"""
    )


def test_validate_text_and_json_gain_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("file-properties"))
    text = runner.invoke(app, ["validate"])
    assert text.stdout == "✓ 1 schema\n✓ 1 entity\n✓ 0 relations\n✓ vault is valid\n"
    payload = json.loads(runner.invoke(app, ["validate", "--format", "json"]).stdout)
    assert payload == {
        "ok": True,
        "stats": {"schemas": 1, "entities": 1, "relations": 0},
        "issues": [],
    }


def test_view_embeds_connectors_and_accept() -> None:
    from knott.view import render_ontology

    page = render_ontology(Knott.open(fixture_path("file-properties")).ontology())
    assert '"connectors": [{"name": "gdrive"' in page
    assert '"accept": ["mp3", "wav"]' in page
    assert '"edges": []' in page


# --- the `file` shape in a concept ----------------------------------------------


@pytest.mark.parametrize(
    ("properties", "field", "fragment"),
    [
        ("  a: { type: file, accept: [MP3] }", "properties.a.accept.0", "write `mp3`"),
        ("  a: { type: file, accept: [.mp3] }", "properties.a.accept.0", "write `mp3`"),
        ("  a: { type: file, accept: [mp3, mp3] }", "properties.a.accept.1", "twice"),
        ("  a: { type: file, accept: [] }", "properties.a.accept", "an empty list"),
        ("  a: { type: file, accept: mp3 }", "properties.a.accept", "non-empty list"),
        ("  a: { type: file, accept: [3] }", "properties.a.accept.0", "got integer"),
        ("  a: { type: string, accept: [mp3] }", "properties.a.accept", "only allowed when"),
        (
            "  a: { type: list, accept: [mp3], items: { type: file } }",
            "properties.a.accept",
            "put `accept:` on `items`",
        ),
        (
            "  a: { type: map, accept: [mp3], values: { type: file } }",
            "properties.a.accept",
            "put `accept:` on `values`",
        ),
        ("  a: { type: file, target: note }", "properties.a.target", "only allowed when"),
        ("  a: { type: file, relation: about }", "properties.a.relation", "only allowed when"),
        ("  a: { type: file, stores: [vault] }", "properties.a.stores", "allowed keys"),
    ],
)
def test_file_definition_errors(tmp_path: Path, properties: str, field: str, fragment: str) -> None:
    root = _vault(tmp_path, f"---\nname: recording\nproperties:\n{properties}\n---\n")
    issues = Knott.open(root).schema_issues()
    assert [(i.field, i.code) for i in issues] == [(field, "schema-invalid-field")]
    assert fragment in issues[0].message


def test_unknown_type_message_lists_file(tmp_path: Path) -> None:
    root = _vault(tmp_path, "---\nname: recording\nproperties:\n  a: { type: files }\n---\n")
    (issue,) = Knott.open(root).schema_issues()
    assert issue.message.endswith("list, object, map, reference, file, enum")


# --- connector files --------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "code", "field", "fragment"),
    [
        ("---\ndescription: x\n---\n", "schema-invalid-field", "name", "missing required key"),
        ("---\nname: G_Drive\n---\n", "schema-invalid-field", "name", "lowercase URI scheme"),
        ("---\nname: my_store\n---\n", "schema-invalid-field", "name", "lowercase URI scheme"),
        ("---\nname: 3d\n---\n", "schema-invalid-field", "name", "lowercase URI scheme"),
        ("---\nname: kid\n---\n", "schema-invalid-field", "name", "cannot be named `kid`"),
        ("no frontmatter\n", "schema-invalid-yaml", None, "needs YAML frontmatter"),
        ("---\n- a\n---\n", "schema-invalid-yaml", None, "must be a YAML mapping"),
        ("---\nname: [\n---\n", "schema-invalid-yaml", None, ""),
    ],
)
def test_connector_file_that_defines_nothing(
    tmp_path: Path, text: str, code: str, field: str | None, fragment: str
) -> None:
    root = _vault(tmp_path, connectors={"x": text})
    loaded = load_definitions(root)
    assert [(i.path, i.field, i.code) for i in loaded.issues] == [
        (".knott/connectors/x.md", field, code)
    ]
    assert fragment in loaded.issues[0].message
    assert loaded.connectors == {}


def test_connector_with_invalid_optional_keys_still_loads(tmp_path: Path) -> None:
    root = _vault(tmp_path, connectors={"x": "---\nname: git+ssh\ndescription: 3\nnmae: y\n---\n"})
    loaded = load_definitions(root)
    assert [(i.line, i.field, i.code) for i in loaded.issues] == [
        (4, "nmae", "schema-invalid-field"),
        (3, "description", "schema-invalid-field"),
    ]
    assert "did you mean `name`?" in loaded.issues[0].message
    assert loaded.connectors["git+ssh"].description is None


def test_duplicate_connector_first_file_wins(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        connectors={
            "a": "---\nname: s3\ndescription: first\n---\n",
            "b": "---\ndescription: second\nname: s3\n---\n",
        },
    )
    loaded = load_definitions(root)
    assert [(i.path, i.line, i.field, i.code) for i in loaded.issues] == [
        (".knott/connectors/b.md", 3, "name", "schema-duplicate-connector")
    ]
    assert ".knott/connectors/a.md" in loaded.issues[0].message
    assert loaded.connectors["s3"].description == "first"
    # Schema issues from connector files reach `validate` and `types`.
    assert [i.code for i in Knott.open(root).schema_issues()] == ["schema-duplicate-connector"]
    assert "schema-duplicate-connector" in {i.code for i in Knott.open(root).validate().issues}


def test_legacy_layout_loads_no_connectors(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    (root / ".knott" / "schemas").mkdir()
    loaded = load_definitions(root)
    assert loaded.connectors == {}
    assert [i.code for i in loaded.issues] == ["schema-legacy-layout"]


# --- value shape ----------------------------------------------------------------


REQUIRED = """---
name: recording
properties:
  audio: { type: file, required: true }
  images: { type: list, required: true, items: { type: file } }
  extras: { type: map, values: { type: file } }
---
"""


@pytest.mark.parametrize(
    ("frontmatter", "expected"),
    [
        ("", [("audio", "file-missing"), ("images", "file-missing")]),
        ('audio: ""\nimages: []\n', [("audio", "file-missing"), ("images", "file-missing")]),
        ("audio:\nimages:\n", [("audio", "file-missing"), ("images", "file-missing")]),
        (
            "audio: []\nimages: {}\n",
            [("audio", "file-invalid-value"), ("images", "file-invalid-value")],
        ),
        ("audio: {}\nimages: [a.png]\n", [("audio", "file-invalid-value")]),
        ('audio: "   "\nimages: [a.png]\n', [("audio", "file-invalid-value")]),
        ("audio: 42\nimages: [a.png]\n", [("audio", "file-invalid-value")]),
        ("audio: true\nimages: [a.png]\n", [("audio", "file-invalid-value")]),
        ("audio: {a: 1}\nimages: [a.png]\n", [("audio", "file-invalid-value")]),
        ("audio: [a.png, a.png]\nimages: [a.png]\n", [("audio", "file-invalid-value")]),
        ("audio: [[take.mp3]]\nimages: [a.png]\n", [("audio", "file-invalid-value")]),
        ("audio: a.png\nimages: a.png\n", [("images", "file-invalid-value")]),
        ("audio: a.png\nimages: 3\n", [("images", "file-invalid-value")]),
        (
            'audio: a.png\nimages: [a.png, "", null, 7]\n',
            [
                ("images[1]", "file-invalid-value"),
                ("images[2]", "file-invalid-value"),
                ("images[3]", "file-invalid-value"),
            ],
        ),
        ("audio: a.png\nimages: [a.png]\nextras: {}\n", []),
        ("audio: a.png\nimages: [a.png]\nextras: []\n", [("extras", "file-invalid-value")]),
        (
            "audio: a.png\nimages: [a.png]\nextras: {x: a.png, y: , 3: a.png}\n",
            [("extras", "file-invalid-value"), ("extras.y", "file-invalid-value")],
        ),
    ],
)
def test_value_shape(tmp_path: Path, frontmatter: str, expected: list[tuple[str, str]]) -> None:
    root = _vault(tmp_path, REQUIRED)
    _write(root, "recordings/a.png")
    assert sorted(_codes(_entity(root, frontmatter))) == sorted(expected)


def test_value_shape_messages(tmp_path: Path) -> None:
    root = _vault(tmp_path, REQUIRED)
    by_field = {
        i.field: i.message
        for i in _entity(root, "audio: [a, b]\nimages: a.png\nextras: {x: [[a]]}\n")
    }
    assert "declare `type: list` with file `items` for several" in by_field["audio"]
    assert "write it as a list of files, even for one" in by_field["images"]
    assert "use a Markdown link such as" in by_field["extras.x"]
    missing = {i.field: i.message for i in _entity(root, "")}
    assert missing["audio"] == "required file `audio` (file) is missing or empty; add a file"
    assert missing["images"].endswith("; add at least one file")


def test_object_holding_files(tmp_path: Path) -> None:
    concept = """---
name: recording
properties:
  credits:
    type: list
    required: true
    items:
      type: object
      fields:
        photo: { type: file, required: true }
---
"""
    root = _vault(tmp_path, concept)
    assert _codes(_entity(root, "")) == [("credits", "attribute-missing")]
    assert _codes(_entity(root, "credits: [{photo: }, {photo: nope.png}, 3]\n")) == [
        ("credits[0].photo", "file-missing"),
        ("credits[1].photo", "file-not-found"),
        ("credits[2]", "attribute-type-mismatch"),
    ]


# --- resolving a value ----------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "code", "fragment"),
    [
        # paths
        ("../audio/take.mp3", None, ""),
        ('"[take 1](../audio/take.mp3)"', None, ""),
        ('"[take 1](<../audio/take.mp3>)"', None, ""),
        ('"[x](../audio/take%2Emp3)"', None, ""),
        ("../audio/Take.mp3", "file-not-found", "does not exist (resolved to `audio/Take.mp3`)"),
        ("../audio/missing.flac", "file-not-found", "does not exist"),
        ("../audio", "file-not-found", "is a folder, not a file"),
        ("..", "file-not-found", "is a folder, not a file"),
        (
            "../img/a.png",
            "file-extension-mismatch",
            "expects `.mp3` or `.wav`, but `../img/a.png` is `.png`",
        ),
        ("../audio/noext", "file-extension-mismatch", "has no extension"),
        ("../audio/.mp3", "file-extension-mismatch", "has no extension"),
        ("../../outside.mp3", "file-outside-vault", "outside the vault root"),
        ("/srv/take.mp3", "file-invalid-value", "absolute path"),
        ("../audio/take.mp3#t=3", "file-invalid-value", "#fragment"),
        ('"[x](../audio/take%23.mp3)"', "file-invalid-value", "#fragment"),
        ('"[x](%2E%2E/%2E%2E/outside.mp3)"', "file-outside-vault", "outside the vault root"),
        ('"[x](../audio/take%zz.mp3)"', "file-not-found", "take%zz.mp3"),
        ('"[x]()"', "file-invalid-value", "empty path"),
        ('"a\\0b.mp3"', "file-invalid-value", "null character"),
        ('"[x](a%00b.mp3)"', "file-invalid-value", "null character"),
        ('"[x](../audio/my take.mp3)"', "file-invalid-value", "contains spaces"),
        ('"[x](../audio/take.mp3"', "file-invalid-value", "not a valid Markdown link"),
        ('"[[take.mp3]]"', "file-invalid-value", "wikilinks are not supported"),
        # URIs
        ("gdrive:1AbC", None, ""),
        ('"gdrive:1AbC#page=3 and more"', None, ""),
        ("GDrive:1AbC", None, ""),
        ("gdrive://folder/1AbC.flac", None, ""),
        ('"gdrive:"', "file-invalid-value", "nothing after the scheme"),
        ('"gdrive:   "', "file-invalid-value", "nothing after the scheme"),
        ("gdrv:1AbC", "file-unknown-connector", "did you mean `gdrive`?"),
        (
            "https://drive.google.com/file/d/1AbC",
            "file-unknown-connector",
            "add `.knott/connectors/https.md`",
        ),
        ("a:b.mp3", "file-unknown-connector", "`./a:b.mp3` if the name has a colon"),
        ("C:/Users/me/take.mp3", "file-unknown-connector", "scheme `c`"),
        ("kid:0190a5c0-0000-7000-8000-000000000001", "file-invalid-value", "`reference` property"),
        ('"[x](gdrive:1AbC)"', "file-invalid-value", "write `gdrive:1AbC` on its own"),
        ('"[x](<gdrive:1 AbC>)"', "file-invalid-value", "on its own"),
        ('"[x](nope:1AbC)"', "file-invalid-value", "on its own"),
    ],
)
def test_resolving_one_value(tmp_path: Path, value: str, code: str | None, fragment: str) -> None:
    root = _vault(tmp_path)
    _write(root, "audio/noext")
    _write(root, "audio/.mp3")
    issues = _entity(root, f"audio: {value}\n")
    if code is None:
        assert issues == []
        return
    # One issue per value: the first step that fails.
    assert [(i.field, i.line, i.code) for i in issues] == [("audio", 3, code)]
    assert fragment in issues[0].message
    assert issues[0].message.startswith("file `audio`")


def test_file_name_with_a_colon(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    _write(root, "recordings/a:b.mp3")
    assert _entity(root, "audio: ./a:b.mp3\n") == []
    assert _entity(root, 'audio: "[x](a%3Ab.mp3)"\n') == []
    assert _codes(_entity(root, "audio: a:b.mp3\n")) == [("audio", "file-unknown-connector")]


def test_unknown_connector_with_none_declared(tmp_path: Path) -> None:
    root = _vault(tmp_path, connectors={})
    (issue,) = _entity(root, "slides: s3://talks/a.pdf\n")
    assert issue.code == "file-unknown-connector"
    assert "(known connectors: none)" in issue.message


def test_accept_applies_to_paths_only_and_is_case_insensitive(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    _write(root, "audio/LOUD.MP3")
    assert _entity(root, "audio: ../audio/LOUD.MP3\n") == []
    assert _entity(root, "audio: gdrive:notes.txt\n") == []


def test_any_vault_file_passes_including_entities_and_hidden_folders(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    _write(root, ".assets/deck.pdf")
    assert _entity(root, "slides: ../.assets/deck.pdf\n") == []
    assert _entity(root, "slides: ../.knott/concepts/recording.md\n") == []
    assert _entity(root, "slides: ./ep.md\n") == []
    assert _entity(root, "slides: ep.md\n") == []


def test_symlink_out_of_the_vault(tmp_path: Path) -> None:
    (tmp_path / "vault").mkdir()
    root = _vault(tmp_path / "vault")
    _write(tmp_path, "elsewhere/take.mp3")
    os.symlink(tmp_path / "elsewhere" / "take.mp3", root / "audio" / "link.mp3")
    os.symlink(tmp_path / "elsewhere", root / "linked")
    os.symlink(root / "audio" / "take.mp3", root / "audio" / "inside.mp3")
    assert _codes(_entity(root, "audio: ../audio/link.mp3\n")) == [("audio", "file-outside-vault")]
    assert _codes(_entity(root, "audio: ../linked/take.mp3\n")) == [("audio", "file-outside-vault")]
    assert _entity(root, "audio: ../audio/inside.mp3\n") == []


def test_list_mixes_vault_files_and_connectors(tmp_path: Path) -> None:
    root = _vault(
        tmp_path, connectors={"gdrive": "---\nname: gdrive\n---\n", "s3": "---\nname: s3\n---\n"}
    )
    issues = _entity(
        root,
        "images:\n  - ../img/a.png\n  - gdrive:1AbC\n  - s3://talks/b.png\n"
        "  - ../img/missing.png\n  - ftp://host/c.png\n  - ../audio/take.mp3\n",
    )
    assert [(i.field, i.line, i.code) for i in issues] == [
        ("images[3]", 7, "file-not-found"),
        ("images[4]", 8, "file-unknown-connector"),
        ("images[5]", 9, "file-extension-mismatch"),
    ]


def test_undeclared_key_is_not_checked_and_two_entities_may_share_a_file(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    assert _entity(root, "audio: ../audio/take.mp3\nmystery: nope:1\nother: ../missing.bin\n") == []
    assert _entity(root, "audio: ../audio/take.mp3\n", "recordings/second.md") == []


def test_scoped_run_resolves_only_in_scope_files(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    _entity(root, "audio: ../audio/missing.mp3\n", "recordings/bad.md")
    _entity(root, "audio: ../audio/take.mp3\n", "recordings/good.md")
    vault = Knott.open(root)
    assert vault.validate(["recordings/good.md"]).ok
    assert triples(vault.validate(["recordings/bad.md"])) == [
        ("recordings/bad.md", 3, "file-not-found")
    ]


def test_cli_reports_a_file_issue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(tmp_path)
    _entity(root, "audio: ../img/a.png\n")
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert result.stdout == (
        "✗ recordings/ep.md:3  audio\n"
        "  file `audio`: expects `.mp3` or `.wav`, but `../img/a.png` is `.png`\n"
        "\n1 validation error\n"
    )


@pytest.mark.parametrize(
    ("name", "extension"),
    [
        ("take.mp3", "mp3"),
        ("TAKE.MP3", "mp3"),
        ("a.tar.gz", "gz"),
        ("noext", ""),
        (".env", ""),
        ("a.", ""),
    ],
)
def test_file_extension(name: str, extension: str) -> None:
    assert file_extension(name) == extension
