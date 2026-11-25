"""Loops: loop files, `loop-stage-unmet`, `knott loops` and the view board (spec 0010)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import Knott, KnottError, LoopNeed
from knott.cli import app
from knott.models import Issue
from knott.view import render_ontology
from tests.conftest import fixture_path

runner = CliRunner()

EPISODE = """---
name: episode
properties:
  title: { type: string }
  status: { type: enum, options: [idea, recorded, published, dropped] }
  mood: { type: enum, options: [good, bad] }
  recorded_at: { type: date }
  tags:
    type: list
    items: { type: enum, options: [a, b] }
---
"""
TRANSCRIPT = """---
name: transcript
properties:
  episode: { type: reference, relation: material_for, target: episode }
---
"""
NOTE = """---
name: note
properties:
  about: { type: reference, target: episode }
---
"""
MATERIAL_FOR = "---\nname: material_for\ninverse: materials\n---\n"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _vault(tmp_path: Path, loops: dict[str, str]) -> Knott:
    Knott.init(tmp_path)
    _write(tmp_path, ".knott/concepts/episode.md", EPISODE)
    _write(tmp_path, ".knott/concepts/transcript.md", TRANSCRIPT)
    _write(tmp_path, ".knott/concepts/note.md", NOTE)
    _write(tmp_path, ".knott/relations/material-for.md", MATERIAL_FOR)
    for name, text in loops.items():
        _write(tmp_path, f".knott/loops/{name}.md", text)
    return Knott.open(tmp_path)


def _loop(stages: str, name: str = "production", extra: str = "") -> str:
    return f"---\nname: {name}\ntype: episode\nproperty: status\n{extra}stages:\n{stages}---\n"


def _brief(issues: list[Issue]) -> list[tuple[str, int | None, str | None, str]]:
    return [(i.path, i.line, i.field, i.code) for i in issues]


GOOD_STAGES = "  idea:\n  recorded: { needs: [recorded_at, materials: transcript] }\n  published:\n"


# --- loop files ---------------------------------------------------------------


def test_fixture_loop_is_loaded() -> None:
    vault = Knott.open(fixture_path("loops"))
    assert vault.schema_issues() == []
    (loop,) = vault.ontology().loops
    assert (loop.name, loop.type, loop.property) == ("episode-production", "episode", "status")
    assert loop.path == ".knott/loops/episode-production.md"
    assert [s.name for s in loop.stages] == ["idea", "planned", "recorded", "published"]
    assert [s.name for s in loop.exits] == ["dropped"]
    assert loop.stages[2].needs == [
        LoopNeed(kind="property", property="recorded_at", since="recorded"),
        LoopNeed(
            kind="inverse",
            inverse="materials",
            relation="material_for",
            type="transcript",
            since="recorded",
        ),
    ]
    # A list of types is one need per type.
    assert [n.type for n in loop.stages[3].needs if n.kind == "inverse"] == [
        "summary",
        "transcript",
    ]


def test_guidance_is_split_by_stage_headings() -> None:
    (loop,) = Knott.open(fixture_path("loops")).ontology().loops
    assert loop.guidance == "Tasks live in GitHub Issues."
    assert loop.stages[2].guidance == "Export the transcript into the episode folder."
    assert loop.exits[0].guidance == "Say why in the body."
    assert loop.stages[0].guidance is None


def test_a_heading_that_is_no_option_stays_in_its_section(tmp_path: Path) -> None:
    body = "General.\n\n## Notes\n\nStill general.\n\n## recorded\n\nDo it.\n\n## Why\n\nBecause.\n"
    vault = _vault(tmp_path, {"p": _loop(GOOD_STAGES) + body})
    (loop,) = vault.ontology().loops
    assert loop.guidance == "General.\n\n## Notes\n\nStill general."
    assert loop.stages[1].guidance == "Do it.\n\n## Why\n\nBecause."


def test_vault_without_loops_has_none(tmp_path: Path) -> None:
    vault = _vault(tmp_path, {})
    assert vault.ontology().loops == []
    assert vault.loops() == []
    assert vault.validate().ok


def test_the_loops_order_is_the_path_and_unlisted_options_are_exits(tmp_path: Path) -> None:
    vault = _vault(tmp_path, {"p": _loop("  published:\n  idea:\n")})
    assert vault.schema_issues() == []
    (loop,) = vault.ontology().loops
    assert [s.name for s in loop.stages] == ["published", "idea"]
    assert [s.name for s in loop.exits] == ["recorded", "dropped"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("no frontmatter\n", (1, None, "schema-invalid-yaml")),
        ("---\nname: [\n---\n", (2, None, "schema-invalid-yaml")),
        ("---\ntype: episode\nproperty: status\nstages:\n  idea:\n---\n", (1, None, None)),
        (_loop("  idea:\n", name="Bad Name"), (2, "name", None)),
        ("---\nname: p\nproperty: status\nstages:\n  idea:\n---\n", (1, None, None)),
        ("---\nname: p\ntype: episode\nstages:\n  idea:\n---\n", (1, None, None)),
        ("---\nname: p\ntype: episode\nproperty: status\n---\n", (1, None, None)),
        ("---\nname: p\ntype: [a]\nproperty: status\nstages:\n  idea:\n---\n", (3, "type", None)),
        (_loop("  idea:\n", extra="stage: status\n"), (5, "stage", None)),
        ("---\nname: p\ntype: episode\nproperty: status\nstages: []\n---\n", (5, "stages", None)),
        (_loop("  idea: yes\n"), (6, "stages", None)),
        (_loop("  idea: { need: [title] }\n"), (6, "stages", None)),
        (_loop("  idea: { needs: [] }\n"), (6, "needs", None)),
        (_loop("  idea: { needs: title }\n"), (6, "needs", None)),
        (_loop("  idea: { needs: [3] }\n"), (6, "needs", None)),
        (_loop("  idea: { needs: [{ materials: transcript, a: b }] }\n"), (6, "needs", None)),
        (_loop("  idea: { needs: [materials: [3]] }\n"), (6, "needs", None)),
    ],
)
def test_malformed_loop_file(
    tmp_path: Path, text: str, expected: tuple[int, str | None, str | None]
) -> None:
    line, field, code = expected
    vault = _vault(tmp_path, {"p": text})
    assert _brief(vault.schema_issues()) == [
        (".knott/loops/p.md", line, field, code or "schema-invalid-field")
    ]
    # An unknown key alone does not keep the loop from loading; everything else does.
    assert [loop.name for loop in vault.ontology().loops] == (
        ["production"] if field == "stage" else []
    )


def test_invalid_description_is_dropped(tmp_path: Path) -> None:
    vault = _vault(tmp_path, {"p": _loop("  idea:\n", extra="description: [x]\n")})
    assert _brief(vault.schema_issues()) == [
        (".knott/loops/p.md", 5, "description", "schema-invalid-field")
    ]
    assert vault.ontology().loops[0].description is None


def test_unquoted_stage_key_gets_the_quoting_hint(tmp_path: Path) -> None:
    vault = _vault(tmp_path, {"p": _loop("  idea:\n  no:\n")})
    (issue,) = vault.schema_issues()
    assert (issue.code, issue.field) == ("schema-invalid-field", "stages")
    assert 'quote it: "no"' in issue.message


@pytest.mark.parametrize(
    ("text", "line", "field", "fragment"),
    [
        (
            "---\nname: p\ntype: episod\nproperty: status\nstages:\n  idea:\n---\n",
            3,
            "type",
            "no concept defines it",
        ),
        (
            "---\nname: p\ntype: episode\nproperty: statu\nstages:\n  idea:\n---\n",
            4,
            "property",
            "did you mean `status`?",
        ),
        (
            "---\nname: p\ntype: episode\nproperty: title\nstages:\n  idea:\n---\n",
            4,
            "property",
            "not an enum",
        ),
        (
            "---\nname: p\ntype: episode\nproperty: tags\nstages:\n  a:\n---\n",
            4,
            "property",
            "not an enum",
        ),
        (_loop("  idea:\n  publshed:\n"), 7, "stages", "did you mean `published`?"),
        (_loop("  idea: { needs: [recorded] }\n"), 6, "needs", "did you mean `recorded_at`?"),
        (_loop("  idea: { needs: [status] }\n"), 6, "needs", "own stage property"),
        (_loop("  idea: { needs: [material: transcript] }\n"), 6, "needs", "not the `inverse`"),
        (_loop("  idea: { needs: [materials: nope] }\n"), 6, "needs", "no concept defines it"),
        (_loop("  idea: { needs: [materials: note] }\n"), 6, "needs", "has no reference"),
    ],
)
def test_loop_invalid_target(
    tmp_path: Path, text: str, line: int, field: str, fragment: str
) -> None:
    vault = _vault(tmp_path, {"p": text})
    (issue,) = vault.schema_issues()
    assert (issue.path, issue.line, issue.field, issue.code) == (
        ".knott/loops/p.md",
        line,
        field,
        "loop-invalid-target",
    )
    assert fragment in issue.message
    assert vault.ontology().loops == []
    # Entities are not checked against a loop that did not load.
    _write(tmp_path, "e.md", "---\ntype: episode\nstatus: recorded\n---\n")
    assert [i.code for i in vault.validate().issues] == ["loop-invalid-target"]


def test_duplicate_loop_name(tmp_path: Path) -> None:
    vault = _vault(
        tmp_path,
        {
            "a": _loop("  idea:\n"),
            "b": "---\nname: production\ntype: episode\nproperty: mood\nstages:\n  good:\n---\n",
        },
    )
    (issue,) = vault.schema_issues()
    assert (issue.path, issue.line, issue.field, issue.code) == (
        ".knott/loops/b.md",
        2,
        "name",
        "schema-duplicate-loop",
    )
    assert "`.knott/loops/a.md`" in issue.message
    assert [loop.property for loop in vault.ontology().loops] == ["status"]


def test_two_loops_on_one_property(tmp_path: Path) -> None:
    vault = _vault(tmp_path, {"a": _loop("  idea:\n"), "b": _loop("  idea:\n", name="other")})
    (issue,) = vault.schema_issues()
    assert (issue.path, issue.line, issue.field, issue.code) == (
        ".knott/loops/b.md",
        4,
        "property",
        "schema-duplicate-loop",
    )
    assert [loop.name for loop in vault.ontology().loops] == ["production"]


def test_two_loops_on_two_properties_of_one_type(tmp_path: Path) -> None:
    mood = "---\nname: mood\ntype: episode\nproperty: mood\nstages:\n  good:\n---\n"
    vault = _vault(tmp_path, {"a": _loop("  idea:\n"), "b": mood})
    assert vault.schema_issues() == []
    assert [loop.name for loop in vault.ontology().loops] == ["mood", "production"]


# --- entities -----------------------------------------------------------------


def test_fixture_report() -> None:
    report = Knott.open(fixture_path("loops")).loops("episode-production")
    assert [(p.stage, [e.path for e in p.entities]) for p in report.stages] == [
        ("idea", []),
        ("planned", ["episodes/ep-002/episode.md"]),
        ("recorded", ["episodes/ep-001/episode.md"]),
        ("published", ["episodes/ep-003/episode.md"]),
    ]
    assert [(p.stage, [e.path for e in p.entities]) for p in report.exits] == [
        ("dropped", ["episodes/ep-004/episode.md"])
    ]
    assert [e.path for e in report.unplaced] == ["episodes/ep-005/episode.md"]

    planned = report.stages[1].entities[0]
    assert (planned.title, planned.unmet, planned.next) == ("Agents", [], "recorded")
    assert [(n.property, n.type) for n in planned.missing_next] == [
        ("recorded_at", None),
        (None, "transcript"),
    ]
    recorded = report.stages[2].entities[0]
    assert recorded.unmet == []
    assert [(n.property, n.type) for n in recorded.missing_next] == [
        ("published_at", None),
        ("links", None),
        (None, "summary"),
    ]
    published = report.stages[3].entities[0]
    assert (published.next, published.missing_next) == (None, [])
    # Needs add up; a need a later stage repeats is reported once, at its first stage.
    assert [(n.property, n.type, n.since) for n in published.unmet] == [
        ("recorded_at", None, "recorded"),
        (None, "transcript", "recorded"),
    ]
    dropped = report.exits[0].entities[0]
    assert (dropped.unmet, dropped.next, dropped.missing_next) == ([], None, [])


def test_fixture_validation() -> None:
    result = Knott.open(fixture_path("loops")).validate()
    assert _brief(result.issues) == [
        ("episodes/ep-003/episode.md", 4, "status", "loop-stage-unmet"),
        ("episodes/ep-003/episode.md", 4, "status", "loop-stage-unmet"),
    ]
    assert [i.message for i in result.issues] == [
        "stage `published` of loop `episode-production` needs "
        "`recorded_at` (needed since `recorded`)",
        "stage `published` of loop `episode-production` needs a `transcript` in `materials` "
        "(`material_for` pointing here) (needed since `recorded`)",
    ]


def test_needs_of_the_entitys_own_stage_have_no_since(tmp_path: Path) -> None:
    vault = _vault(tmp_path, {"p": _loop(GOOD_STAGES)})
    _write(tmp_path, "e.md", "---\ntype: episode\nstatus: recorded\n---\n")
    assert [i.message for i in vault.validate().issues] == [
        "stage `recorded` of loop `production` needs `recorded_at`",
        "stage `recorded` of loop `production` needs "
        "a `transcript` in `materials` (`material_for` pointing here)",
    ]


@pytest.mark.parametrize("value", ["", "null", '""', "publshed", "3", "[recorded]"])
def test_no_stage(tmp_path: Path, value: str) -> None:
    vault = _vault(tmp_path, {"p": _loop(GOOD_STAGES)})
    _write(tmp_path, "e.md", f"---\ntype: episode\nstatus: {value}\n---\n")
    report = vault.loops("production")
    assert [e.path for e in report.unplaced] == ["e.md"]
    assert "loop-stage-unmet" not in [i.code for i in vault.validate().issues]


def test_empty_values_do_not_meet_a_property_need(tmp_path: Path) -> None:
    stages = "  idea:\n  recorded: { needs: [title, tags] }\n"
    vault = _vault(tmp_path, {"p": _loop(stages)})
    _write(tmp_path, "e.md", '---\ntype: episode\nstatus: recorded\ntitle: ""\ntags: []\n---\n')
    assert len(vault.loops("production").stages[1].entities[0].unmet) == 2
    _write(tmp_path, "e.md", "---\ntype: episode\nstatus: recorded\ntitle: T\ntags: [a]\n---\n")
    assert vault.validate().ok


def test_inverse_need_counts_only_the_named_relation_and_type(tmp_path: Path) -> None:
    vault = _vault(tmp_path, {"p": _loop(GOOD_STAGES)})
    episode = "---\ntype: episode\nstatus: recorded\nrecorded_at: 2026-10-06\n---\n"
    _write(tmp_path, "e.md", episode)
    # A plain reference to the episode names no relation: it does not count.
    _write(tmp_path, "n.md", "---\ntype: note\nabout: e.md\n---\n")
    assert [i.code for i in vault.validate().issues] == ["loop-stage-unmet"]
    _write(tmp_path, "t1.md", "---\ntype: transcript\nepisode: e.md\n---\n")
    _write(tmp_path, "t2.md", "---\ntype: transcript\nepisode: e.md\n---\n")
    assert vault.validate().ok


def test_title_falls_back_to_the_file_name(tmp_path: Path) -> None:
    vault = _vault(tmp_path, {"p": _loop(GOOD_STAGES)})
    _write(tmp_path, "eps/one.md", "---\ntype: episode\nstatus: idea\n---\n")
    _write(tmp_path, "eps/two.md", "---\ntype: episode\nstatus: idea\ntitle: Two\n---\n")
    titles = [e.title for e in vault.loops("production").stages[0].entities]
    assert titles == ["one.md", "Two"]


def test_scoped_run_reports_only_entities_in_scope(
    copy_fixture: Callable[[str], Path],
) -> None:
    root = copy_fixture("loops")
    vault = Knott.open(root)
    assert vault.validate(["episodes/ep-001"]).ok
    assert len(vault.validate(["episodes/ep-003"]).issues) == 2
    # The file an episode lacks is not what makes it in scope.
    (root / "episodes/ep-001/transcript.md").unlink()
    _write(root, "episodes/ep-001/notes.md", "---\ntype: summary\nepisode: episode.md\n---\n")
    assert vault.validate(["episodes/ep-001/notes.md"]).ok
    assert [i.path for i in vault.validate(["episodes/ep-001"]).issues] == [
        "episodes/ep-001/episode.md"
    ]


def test_unknown_loop_name() -> None:
    with pytest.raises(KnottError, match="no loop named nope"):
        Knott.open(fixture_path("loops")).loops("nope")


# --- CLI ------------------------------------------------------------------------


@pytest.fixture
def in_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("loops"))


def test_cli_loops_summary(in_fixture: None) -> None:
    result = runner.invoke(app, ["loops"])
    assert result.exit_code == 0
    assert result.output == (
        "episode-production  episode.status  idea 0 · planned 1 · recorded 1 · published 1"
        " · (dropped 1) · no stage 1\n"
    )


def test_cli_loops_one_loop(in_fixture: None) -> None:
    result = runner.invoke(app, ["loops", "episode-production"])
    assert result.exit_code == 0
    assert result.output == (
        "planned\n"
        "  episodes/ep-002/episode.md\n"
        "    next: recorded — missing recorded_at, transcript in materials\n"
        "recorded\n"
        "  episodes/ep-001/episode.md\n"
        "    next: published — missing published_at, links, summary in materials\n"
        "published\n"
        "  episodes/ep-003/episode.md\n"
        "    ✗ needs `recorded_at`\n"
        "    ✗ needs a `transcript` in `materials` (`material_for` pointing here)\n"
        "dropped\n"
        "  episodes/ep-004/episode.md\n"
        "no stage\n"
        "  episodes/ep-005/episode.md\n"
    )


def test_cli_loops_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _vault(tmp_path, {"p": _loop(GOOD_STAGES)})
    _write(tmp_path, "e.md", "---\ntype: episode\nstatus: recorded\nrecorded_at: 2026-10-06\n---\n")
    _write(tmp_path, "t.md", "---\ntype: transcript\nepisode: e.md\n---\n")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["loops", "production"])
    assert result.output == "recorded\n  e.md\n    next: published — ready\n"


def test_cli_loops_json(in_fixture: None) -> None:
    result = runner.invoke(app, ["loops", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    (report,) = data["loops"]
    assert report["loop"]["name"] == "episode-production"
    assert report["loop"]["stages"][2]["guidance"].startswith("Export the transcript")
    assert report["stages"][3]["entities"][0]["unmet"][0]["property"] == "recorded_at"
    one = runner.invoke(app, ["loops", "episode-production", "--format", "json"])
    assert json.loads(one.output) == data


def test_cli_loops_unknown_name(in_fixture: None) -> None:
    result = runner.invoke(app, ["loops", "nope"])
    assert result.exit_code == 2
    assert "error: no loop named nope" in result.output


def test_cli_loops_without_loops_prints_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vault(tmp_path, {})
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["loops"])
    assert (result.exit_code, result.output) == (0, "")


def test_cli_loops_with_schema_errors_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vault(tmp_path, {"a": _loop(GOOD_STAGES), "b": _loop("  nope:\n", name="broken")})
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["loops"])
    assert result.exit_code == 1
    assert result.output.startswith("production  episode.status  idea 0")
    assert "loop-invalid-target" not in result.output  # the code is not part of text output
    assert "stage `nope` is not an option" in result.output


def test_cli_types_verbose_lists_loops(in_fixture: None) -> None:
    result = runner.invoke(app, ["types", "--verbose"])
    assert result.exit_code == 0
    assert result.output.endswith(
        "loops:\n"
        "  episode-production  episode.status\n"
        "    From an episode idea to a published episode.\n"
        "    stages: idea → planned → recorded → published\n"
        "    exits: dropped\n"
        "    planned needs: participants\n"
        "    recorded needs: recorded_at, transcript in materials\n"
        "    published needs: published_at, links, summary in materials, "
        "transcript in materials\n"
        "    Tasks live in GitHub Issues.\n"
        "    ## recorded\n"
        "    Export the transcript into the episode folder.\n"
        "    ## dropped\n"
        "    Say why in the body.\n"
    )


def test_cli_validate_reports_unmet_needs(in_fixture: None) -> None:
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert "✗ episodes/ep-003/episode.md:4  status" in result.output
    assert "2 validation errors" in result.output


# --- view -----------------------------------------------------------------------


def test_view_embeds_loop_reports() -> None:
    vault = Knott.open(fixture_path("loops"))
    page = render_ontology(vault.ontology(), vault.loops())
    data = json.loads(page.split("const DATA = ", 1)[1].split(";\n", 1)[0])
    (report,) = data["loop_reports"]
    assert [loop["name"] for loop in data["loops"]] == ["episode-production"]
    assert [p["stage"] for p in report["stages"]] == ["idea", "planned", "recorded", "published"]
    assert report["stages"][1]["entities"][0]["title"] == "Agents"
    assert report["unplaced"][0]["path"] == "episodes/ep-005/episode.md"


def test_view_without_loops_embeds_an_empty_list() -> None:
    vault = Knott.open(fixture_path("valid-vault"))
    page = render_ontology(vault.ontology())
    data = json.loads(page.split("const DATA = ", 1)[1].split(";\n", 1)[0])
    assert data["loops"] == []
    assert data["loop_reports"] == []


def test_cli_view_writes_the_board_data(in_fixture: None, tmp_path: Path) -> None:
    target = tmp_path / "page.html"
    result = runner.invoke(app, ["view", "--no-open", "-o", str(target)])
    assert result.exit_code == 0
    page = target.read_text(encoding="utf-8")
    assert '"title": "Robots"' in page
    assert 'id="board"' in page
