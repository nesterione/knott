"""Entity file names: the concept's `filename` key (spec 0012)."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import FilenamePart, FilenamePattern, Knott
from knott.cli import app
from knott.models import Issue
from knott.schema.filenames import entity_stem, match_problem, split_pattern
from knott.schema.loader import load_definitions
from knott.view import render_ontology

runner = CliRunner()

SPEC = """\
  pattern: "{number}-{slug}"
  parts:
    number:
      match: "[0-9]{4}"
      description: The next free number in specs/.
    slug:
      match: "[a-z0-9]+(-[a-z0-9]+)*"
      description: >
        What the change does,
        in two to five lowercase words.
"""


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _vault(tmp_path: Path, filename_yaml: str | None = SPEC, extra: str = "") -> Path:
    """A vault with one concept, `spec`; `filename_yaml` is the indented block under the key."""
    root = tmp_path / "vault"
    block = "" if filename_yaml is None else f"filename:\n{filename_yaml}"
    _write(root, ".knott/concepts/spec.md", f"---\nname: spec\n{extra}{block}---\n")
    return root


def _entity(root: Path, rel: str) -> None:
    _write(root, rel, "---\ntitle: x\ntype: spec\n---\n")


def _name_issues(root: Path) -> list[Issue]:
    return [i for i in Knott.open(root).validate().issues if i.code == "entity-invalid-name"]


def _invalid(root: Path, *names: str) -> list[str]:
    for name in names:
        _entity(root, f"specs/{name}.md")
    return sorted(Path(i.path).stem for i in _name_issues(root))


# --- the pattern ---------------------------------------------------------------


def test_split_pattern() -> None:
    assert split_pattern("{number}-{slug}") == [
        ("part", "number"),
        ("text", "-"),
        ("part", "slug"),
    ]
    assert split_pattern("index") == [("text", "index")]
    assert split_pattern("a.{b}(c)") == [("text", "a."), ("part", "b"), ("text", "(c)")]


@pytest.mark.parametrize(
    ("pattern", "fragment"),
    [
        ("{a", "never closed"),
        ("a}", "no `{` before it"),
        ("{}", "empty `{}`"),
        ("{A}", "part name must match"),
        ("{1a}", "part name must match"),
        ("{a b}", "part name must match"),
        ("{{a}}", "part name must match"),
        ("{a}-{a}", "twice"),
        ("x/{a}", "contains `/`"),
        ("x\\{a}", "contains `\\`"),
    ],
)
def test_split_pattern_problems(pattern: str, fragment: str) -> None:
    problem = split_pattern(pattern)
    assert isinstance(problem, str)
    assert fragment in problem


@pytest.mark.parametrize(
    ("match", "fragment"),
    [
        ("[0-9", "not a valid regular expression"),
        ("(a", "not a valid regular expression"),
        ("[0-9]*", "can match the empty string"),
        ("a?", "can match the empty string"),
    ],
)
def test_match_problems(match: str, fragment: str) -> None:
    problem = match_problem(match)
    assert problem is not None
    assert fragment in problem


@pytest.mark.parametrize(
    "match",
    [
        "[0-9]{4}",
        "[a-z0-9]+(-[a-z0-9]+)*",
        "a|b",
        "^[0-9]{4}$",
        "(?i:abc)",
        r"\\[0-9]",
        r"\d+",
        ".",
        "(?P<n>a)",
        r"(a)\1",
        "(?i)[a-z]+",
    ],
)
def test_valid_matches(match: str) -> None:
    assert match_problem(match) is None


def test_entity_stem_is_nfc() -> None:
    decomposed = unicodedata.normalize("NFD", "café")
    assert entity_stem(f"notes/{decomposed}.md") == "café"
    assert entity_stem("a.b.md") == "a.b"


# --- concept files -------------------------------------------------------------


def test_definition_loads(tmp_path: Path) -> None:
    loaded = load_definitions(_vault(tmp_path))
    assert loaded.issues == []
    definition = loaded.schemas["spec"].filename
    assert definition is not None
    assert definition.pattern == "{number}-{slug}"
    assert [(p.name, p.match) for p in definition.parts] == [
        ("number", "[0-9]{4}"),
        ("slug", "[a-z0-9]+(-[a-z0-9]+)*"),
    ]
    assert definition.parts[0].description == "The next free number in specs/."


def test_parts_follow_the_pattern_order(tmp_path: Path) -> None:
    root = _vault(tmp_path, '  pattern: "{b}.{a}"\n  parts:\n    a:\n    b: { match: "x+" }\n')
    definition = load_definitions(root).schemas["spec"].filename
    assert definition is not None
    assert [(p.name, p.match, p.description) for p in definition.parts] == [
        ("b", "x+", None),
        ("a", None, None),
    ]


@pytest.mark.parametrize(
    ("block", "field", "line", "fragment"),
    [
        ("  - a\n", "filename", 3, "must be a mapping"),
        ("  parts:\n    a:\n", "filename", 3, "needs `pattern`"),
        ('  pattern: ""\n', "filename.pattern", 4, "needs `pattern`"),
        ("  pattern: 4\n", "filename.pattern", 4, "got integer"),
        ('  pattern: "{a"\n  parts:\n    a:\n', "filename.pattern", 4, "never closed"),
        ('  pattern: "{a}-{a}"\n  parts:\n    a:\n', "filename.pattern", 4, "twice"),
        ('  pattern: "x/{a}"\n  parts:\n    a:\n', "filename.pattern", 4, "contains `/`"),
        ('  pattern: "{a}"\n', "filename.pattern", 4, "`parts` does not define"),
        ('  pattern: "{a}"\n  parts:\n    b:\n    a:\n', "filename.parts.b", 6, "does not use"),
        ("  pattern: index\n  parts: [a]\n", "filename.parts", 5, "must be a mapping"),
        ('  pattern: "{a}"\n  parts:\n    a: text\n', "filename.parts.a", 6, "must be empty or"),
        ('  pattern: "{a}"\n  parts:\n    A:\n    a:\n', "filename.parts", 5, "part name"),
        (
            '  pattern: "{a}"\n  parts:\n    a:\n      match: 4\n',
            "filename.parts.a.match",
            7,
            "must be a string",
        ),
        (
            '  pattern: "{a}"\n  parts:\n    a:\n      match: "[0-9"\n',
            "filename.parts.a.match",
            7,
            "not a valid regular expression",
        ),
        (
            '  pattern: "{a}"\n  parts:\n    a:\n      match: "[0-9]*"\n',
            "filename.parts.a.match",
            7,
            "can match the empty string",
        ),
        (
            '  pattern: "{a}"\n  parts:\n    a:\n      description: [x]\n',
            "filename.parts.a.description",
            7,
            "expected a string",
        ),
        (
            '  pattern: "{a}"\n  parts:\n    a:\n      mach: "x"\n',
            "filename.parts.a.mach",
            7,
            "did you mean `match`?",
        ),
        ("  pattern: index\n  part:\n", "filename.part", 5, "did you mean `parts`?"),
    ],
)
def test_invalid_filename_is_reported_and_dropped(
    tmp_path: Path, block: str, field: str, line: int, fragment: str
) -> None:
    root = _vault(tmp_path, block)
    loaded = load_definitions(root)
    assert [(i.code, i.field, i.line) for i in loaded.issues] == [
        ("schema-invalid-field", field, line)
    ]
    assert fragment in loaded.issues[0].message
    # The concept still loads, without `filename`.
    assert loaded.schemas["spec"].filename is None
    assert _invalid(root, "anything at all") == []


def test_unquoted_values_that_yaml_reads_otherwise(tmp_path: Path) -> None:
    mapping = load_definitions(_vault(tmp_path / "a", "  pattern: {slug}\n  parts:\n    slug:\n"))
    assert [(i.code, i.field) for i in mapping.issues] == [
        ("schema-invalid-field", "filename.pattern")
    ]
    assert 'quote it, YAML reads a leading `{` as a mapping: `pattern: "{slug}"`' in (
        mapping.issues[0].message
    )
    for block in (
        "  pattern: {number}-{slug}\n",
        '  pattern: "{a}"\n  parts:\n    a:\n      match: [0-9]{4}\n',
    ):
        broken = load_definitions(_vault(tmp_path / str(len(block)), block))
        assert [i.code for i in broken.issues] == ["schema-invalid-yaml"]
    boolean = load_definitions(_vault(tmp_path / "b", '  pattern: "{no}"\n  parts:\n    no:\n'))
    assert [(i.code, i.field) for i in boolean.issues] == [
        ("schema-invalid-field", "filename.parts")
    ]
    assert 'quote a name YAML reads otherwise: `"no":`' in boolean.issues[0].message
    quoted = load_definitions(_vault(tmp_path / "c", '  pattern: "{no}"\n  parts:\n    "no":\n'))
    assert quoted.issues == []


def test_empty_filename_key_means_no_constraint(tmp_path: Path) -> None:
    root = _vault(tmp_path, "")
    loaded = load_definitions(root)
    assert loaded.issues == []
    assert loaded.schemas["spec"].filename is None


def test_no_filename_means_any_name(tmp_path: Path) -> None:
    root = _vault(tmp_path, None)
    assert _invalid(root, "Loops spec", "0001-x") == []


# --- entities ------------------------------------------------------------------


def test_names_are_checked(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    assert _invalid(
        root,
        "0011-entity-location",
        "0012-x",
        "loops",
        "0013-Entity",
        "0011-",
        "011-x",
        "00111-x",
        "0011-x-",
        "0011_x",
        " 0011-x",
    ) == sorted(
        [
            " 0011-x",
            "0011-",
            "0013-Entity",
            "00111-x",
            "0011_x",
            "0011-x-",
            "011-x",
            "loops",
        ]
    )


def test_message(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    _entity(root, "specs/loops.md")
    (issue,) = _name_issues(root)
    assert (issue.path, issue.line, issue.field) == ("specs/loops.md", 3, None)
    assert issue.message == (
        "`spec` files are named `{number}-{slug}.md` (number: `[0-9]{4}`, "
        "slug: `[a-z0-9]+(-[a-z0-9]+)*`), but this one is `loops.md`"
    )


def test_message_leaves_out_parts_without_match(tmp_path: Path) -> None:
    root = _vault(tmp_path, '  pattern: "{a}-{b}"\n  parts:\n    a:\n    b: { match: "[0-9]+" }\n')
    assert _invalid(root, "x-y-z", "x-1", "x-y-2", "x", "-1") == ["-1", "x", "x-y-z"]
    assert "`{a}-{b}.md` (b: `[0-9]+`), but" in _name_issues(root)[0].message
    free = _vault(tmp_path / "free", '  pattern: "{a}"\n  parts:\n    a:\n')
    assert _invalid(free, "anything") == []


def test_literal_text_is_not_a_regular_expression(tmp_path: Path) -> None:
    root = _vault(tmp_path, '  pattern: "{date}.{slug}(v1)"\n  parts:\n    date:\n    slug:\n')
    assert _invalid(root, "2026.loops(v1)", "2026xloops(v1)", "2026.loopsv1") == [
        "2026.loopsv1",
        "2026xloops(v1)",
    ]


def test_fixed_name_and_md_in_the_pattern(tmp_path: Path) -> None:
    root = _vault(tmp_path, "  pattern: index\n")
    assert _invalid(root, "index", "index2", "ndex") == ["index2", "ndex"]
    twice = _vault(tmp_path / "md", '  pattern: "{slug}.md"\n  parts:\n    slug:\n')
    assert _invalid(twice, "a", "a.md") == ["a"]


def test_alternation_and_anchors_in_a_part(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        '  pattern: "{kind}-{n}"\n  parts:\n    kind: { match: "adr|rfc" }\n'
        '    n: { match: "^[0-9]+$" }\n',
    )
    assert _invalid(root, "adr-1", "rfc-22", "adr-x", "note-1", "adr-1-rfc-2") == [
        "adr-1-rfc-2",
        "adr-x",
        "note-1",
    ]


def test_each_part_keeps_its_own_groups_flags_and_backreferences(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        '  pattern: "{a}-{b}-{c}"\n  parts:\n'
        '    a: { match: "(?i)[a-z]+" }\n'
        "    b: { match: '(x|y)\\1' }\n"
        "    c: { match: '(z)\\1' }\n",
    )
    assert load_definitions(root).issues == []
    assert _invalid(root, "Ab-xx-zz", "cd-yy-zz", "ef-xy-zz", "gh-xx-xz", "a1-xx-zz") == [
        "a1-xx-zz",
        "ef-xy-zz",
        "gh-xx-xz",
    ]


def test_adjacent_parts_and_repeated_separators(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        '  pattern: "{year}{n}-{slug}"\n  parts:\n'
        '    year: { match: "[0-9]{4}" }\n    n: { match: "[a-z]" }\n    slug:\n',
    )
    assert _invalid(root, "2026a-x-y-z", "2026-x", "2026ab-x", "2026a-") == [
        "2026-x",
        "2026a-",
        "2026ab-x",
    ]


def test_a_long_name_that_does_not_fit_is_quick(tmp_path: Path) -> None:
    root = _vault(
        tmp_path, '  pattern: "{a}{b}{c}{d}!"\n  parts:\n    a:\n    b:\n    c:\n    d:\n'
    )
    assert _invalid(root, "x" * 200) == ["x" * 200]


def test_name_is_compared_in_nfc(tmp_path: Path) -> None:
    root = _vault(tmp_path, '  pattern: "{w}"\n  parts:\n    w: { match: "caf\\u00e9" }\n')
    _entity(root, "specs/" + unicodedata.normalize("NFD", "café") + ".md")
    assert _name_issues(root) == []


def test_name_and_location_are_independent(tmp_path: Path) -> None:
    root = _vault(tmp_path, extra="path: specs\n")
    _entity(root, "notes/loops.md")
    _entity(root, "notes/0001-ok.md")
    _entity(root, "specs/bad name.md")
    issues = Knott.open(root).validate().issues
    assert sorted((i.path, i.code) for i in issues) == [
        ("notes/0001-ok.md", "entity-misplaced"),
        ("notes/loops.md", "entity-invalid-name"),
        ("notes/loops.md", "entity-misplaced"),
        ("specs/bad name.md", "entity-invalid-name"),
    ]


# --- CLI, API, view ------------------------------------------------------------


def test_ontology_filename(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    _write(root, ".knott/concepts/note.md", "---\nname: note\n---\n")
    by_type = {t.type: t for t in Knott.open(root).ontology().types}
    assert by_type["note"].filename is None
    assert by_type["spec"].filename == FilenamePattern(
        pattern="{number}-{slug}",
        parts=[
            FilenamePart(
                name="number", match="[0-9]{4}", description="The next free number in specs/."
            ),
            FilenamePart(
                name="slug",
                match="[a-z0-9]+(-[a-z0-9]+)*",
                description="What the change does, in two to five lowercase words.",
            ),
        ],
    )


def test_types_verbose_prints_the_pattern(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(tmp_path, extra="path: specs\n")
    monkeypatch.chdir(root)
    out = runner.invoke(app, ["types", "--verbose"]).output
    assert (
        "  template: no\n"
        "  path: specs\n"
        "  filename: {number}-{slug}.md\n"
        "    number  [0-9]{4}                The next free number in specs/.\n"
        "    slug    [a-z0-9]+(-[a-z0-9]+)*  "
        "What the change does, in two to five lowercase words.\n"
        "  references: none\n"
    ) in out


def test_types_verbose_with_bare_parts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(
        tmp_path,
        '  pattern: "{a}-{bb}-{c}"\n  parts:\n    a:\n    bb: { description: Two words. }\n'
        '    c: { match: "[0-9]+" }\n',
    )
    monkeypatch.chdir(root)
    out = runner.invoke(app, ["types", "--verbose"]).output
    assert (
        "  filename: {a}-{bb}-{c}.md\n    a\n    bb          Two words.\n    c   [0-9]+\n"
    ) in out
    fixed = _vault(tmp_path / "fixed", "  pattern: index\n")
    monkeypatch.chdir(fixed)
    out = runner.invoke(app, ["types", "--verbose"]).output
    assert "  filename: index.md\n  references: none\n" in out


def test_validate_prints_the_issue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(tmp_path)
    _entity(root, "specs/loops.md")
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert "✗ specs/loops.md:3\n  `spec` files are named `{number}-{slug}.md` (" in result.output


def test_view_embeds_the_pattern(tmp_path: Path) -> None:
    html = render_ontology(Knott.open(_vault(tmp_path)).ontology())
    assert '"pattern": "{number}-{slug}"' in html
    assert '"match": "[0-9]{4}"' in html
