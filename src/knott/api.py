"""The Knott API. The CLI is a thin adapter over this module."""

from __future__ import annotations

import os
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version
from pathlib import Path
from typing import overload

from knott import _yaml
from knott.errors import ConfigError, KnottError, PathNotFoundError, PathOutsideVaultError
from knott.models import (
    ConnectorDefinition,
    EntityRef,
    EnumOption,
    FilenamePart,
    FilenamePattern,
    FixedEntity,
    InitResult,
    Issue,
    LoopReport,
    MigrateResult,
    Ontology,
    OntologyAttribute,
    OntologyType,
    Refs,
    RelationDefinition,
    SchemaInfo,
    Stats,
    ValidationResult,
)
from knott.schema.filenames import FilenameDef
from knott.schema.loader import load_definitions, load_ontology, load_schemas
from knott.schema.migrate import migrate_vault
from knott.schema.models import (
    AttributeDef,
    EnumShape,
    FileShape,
    ListShape,
    MapShape,
    ObjectShape,
    ReferenceShape,
    shape_kind,
)
from knott.schema.validator import validate_entity
from knott.vault.cycles import checked_relations, cycle_issues
from knott.vault.discovery import CONCEPTS_DIR, KNOTT_DIR, find_vault_root, iter_markdown
from knott.vault.entity import read_markdown
from knott.vault.fix import insert_kid
from knott.vault.index import VaultSession
from knott.vault.kid import (
    KID_KEY,
    Claim,
    format_claims,
    is_canonical,
    new_kid,
)
from knott.vault.links import KID_PREFIX, LinkError
from knott.vault.loops import loop_definition, loop_report, unmet_issues
from knott.vault.refs import entity_kid, reverse_lookup, type_name

CONFIG_FILE = Path(KNOTT_DIR) / "config.yaml"


def version() -> str:
    """The installed Knott version."""
    try:
        return _dist_version("knott")
    except PackageNotFoundError:  # running from a source tree without install
        return "0.0.0"


class Knott:
    """A Knott vault on disk."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def open(cls, path: str | Path = ".") -> Knott:
        """Open the vault containing ``path``, walking up to the nearest ``.knott/``.

        Raises ``VaultNotFoundError``, ``PathNotFoundError`` or ``ConfigError``.
        """
        start = Path(path)
        if not start.exists():
            raise PathNotFoundError(f"path does not exist: {path}")
        vault = cls(find_vault_root(start))
        vault._check_config()
        return vault

    @staticmethod
    def init(path: str | Path = ".") -> InitResult:
        """Create ``.knott/concepts/`` and ``.knott/config.yaml`` in ``path``.

        Changes nothing if ``.knott/`` already exists.
        """
        root = Path(path)
        if not root.is_dir():
            raise PathNotFoundError(f"directory does not exist: {path}")
        knott_dir = root / KNOTT_DIR
        if knott_dir.exists():
            return InitResult(root=str(root.resolve()), created=False)
        (root / CONCEPTS_DIR).mkdir(parents=True)
        (root / CONFIG_FILE).write_text(f"knott_version: {version()}\n", encoding="utf-8")
        return InitResult(root=str(root.resolve()), created=True)

    def migrate(self) -> MigrateResult:
        """Convert ``.knott/schemas/**/*.yaml`` into ``.knott/concepts/**/*.md``.

        Works without loading schemas, so it runs on a vault that reports
        ``schema-legacy-layout``. A relation that any entity stores as a YAML list
        becomes ``list`` of ``reference``. Raises ``MigrateError`` (nothing written
        or removed) when there is no legacy folder, the legacy folder is a symbolic
        link, a legacy file can't be read or converted, a target concept file or a
        non-folder on its path already exists, or writing a concept file fails
        (files written so far are removed again). If only deleting
        ``.knott/schemas/`` fails, the concept files are kept and ``MigrateError``
        says to delete the legacy folder by hand.
        """
        return migrate_vault(self.root)

    def types(self) -> list[str]:
        """Discovered type names, sorted. Schemas with errors may be missing."""
        return [info.type for info in self.schemas()]

    def schemas(self) -> list[SchemaInfo]:
        """Discovered types with their description and schema file, sorted by type."""
        registry, _ = load_schemas(self.root)
        return [
            SchemaInfo(type=s.type, description=s.description, path=s.path)
            for _, s in sorted(registry.items())
        ]

    def schema_issues(self) -> list[Issue]:
        """Problems found while loading schemas, sorted."""
        _, issues = load_schemas(self.root)
        return _sorted(issues)

    def ontology(self) -> Ontology:
        """The vault's types, their properties and templates, entity counts, and relations.

        Types are sorted by name; properties keep their schema order, references
        included (``type == "reference"``, at any depth). Target types no concept
        defines are listed in ``unknown_targets``. Files with invalid frontmatter
        are not counted. Relations and connectors are sorted by name.
        """
        loaded = load_definitions(self.root)
        schemas, relation_defs, issues = loaded.schemas, loaded.relations, loaded.issues
        counts: dict[str, int] = {}
        for rel_path in iter_markdown(self.root):
            parsed = read_markdown(self.root / rel_path, rel_path)
            if parsed.error is None and parsed.is_entity and isinstance(parsed.type, str):
                counts[parsed.type] = counts.get(parsed.type, 0) + 1

        types = [
            OntologyType(
                type=s.type,
                description=s.description,
                path=s.path,
                count=counts.get(s.type, 0),
                extends=s.extends,
                abstract=s.abstract,
                ancestors=list(s.ancestors),
                subtypes=sorted(c.type for c in schemas.values() if c.extends == s.type),
                inherited={
                    key: owner
                    for key, owner in (
                        ("template", s.template_from),
                        ("path", s.entity_paths_from),
                        ("filename", s.filename_from),
                        ("kid", s.kid_required_from),
                    )
                    if owner is not None
                },
                kid_required=s.kid_required,
                entity_paths=list(s.entity_paths),
                filename=_filename_pattern(s.filename),
                properties=[
                    _ontology_attribute(a).model_copy(
                        update={"inherited_from": s.declared_in.get(name)}
                    )
                    for name, a in s.properties.items()
                ],
                template=s.template,
            )
            for _, s in sorted(schemas.items())
        ]
        relations = [
            RelationDefinition(
                name=r.name,
                description=r.description,
                inverse=r.inverse,
                symmetric=r.symmetric,
                acyclic=r.acyclic,
                guidance=r.guidance,
                path=r.path,
            )
            for _, r in sorted(relation_defs.items())
        ]
        connectors = [
            ConnectorDefinition(
                name=c.name, description=c.description, guidance=c.guidance, path=c.path
            )
            for _, c in sorted(loaded.connectors.items())
        ]
        return Ontology(
            vault=self.root.name,
            types=types,
            schema_issues=len(issues),
            relations=relations,
            connectors=connectors,
            loops=[loop_definition(loop) for _, loop in sorted(loaded.loops.items())],
        )

    def validate(
        self, paths: Sequence[str | Path] | None = None, *, fix: bool = False
    ) -> ValidationResult:
        """Validate all schemas, and entities (all, or those within ``paths``).

        Relative ``paths`` are resolved against the vault root. Validation problems
        are returned as data; only usage errors raise.

        With ``fix=True``, every in-scope entity without a `kid` key first gets a new
        one (a single inserted frontmatter line), and the result lists them in ``fixed``.
        """
        fixed = self._assign_kids(paths) if fix else []
        result = self._validate(paths)
        return result.model_copy(update={"fixed": fixed}) if fixed else result

    def refs(self, path_or_kid: str | Path) -> Refs:
        """Every reference in the vault that resolves to one entity, grouped (spec 0006).

        ``path_or_kid`` is an entity file (relative paths are resolved against the
        vault root) or ``kid:<uuid>``. Does not validate: it works with the concepts
        and relations that load. Raises ``PathNotFoundError`` when the path doesn't
        exist, ``PathOutsideVaultError`` when it is outside the vault, and
        ``KnottError`` when it isn't an entity or a `kid` matches no entity or several.
        """
        schemas, relations, _ = load_ontology(self.root)
        session = VaultSession(self.root, schemas)
        if isinstance(path_or_kid, str) and path_or_kid.strip().startswith(KID_PREFIX):
            try:
                target = session.resolve("", path_or_kid).target
            except LinkError as error:
                raise KnottError(error.message) from None
        else:
            target = self._entity_path(path_or_kid, session)
        entity = session.lookup(target)
        return Refs(
            entity=EntityRef(
                path=target, type=type_name(entity.type), kid=entity_kid(session, target)
            ),
            groups=reverse_lookup(session, relations, target),
        )

    @overload
    def loops(self) -> list[LoopReport]: ...
    @overload
    def loops(self, name: str) -> LoopReport: ...
    def loops(self, name: str | None = None) -> list[LoopReport] | LoopReport:
        """Where every entity stands in each loop, sorted by loop name (spec 0010).

        With ``name``, that one loop; raises ``KnottError`` when no loaded loop has
        the name. Does not validate: it works with the definitions that load.
        """
        loaded = load_definitions(self.root)
        session = VaultSession(self.root, loaded.schemas)
        if name is None:
            return [loop_report(session, loop) for _, loop in sorted(loaded.loops.items())]
        loop = loaded.loops.get(name)
        if loop is None:
            raise KnottError(f"no loop named {name}")
        return loop_report(session, loop)

    def _entity_path(self, given: str | Path, session: VaultSession) -> str:
        """The vault-relative path of the entity file ``given``."""
        rel_posix = self._vault_relative(given)
        parsed = session.lookup(rel_posix) if rel_posix in session.all_markdown else None
        if parsed is not None and parsed.error is not None:
            raise KnottError(f"cannot read the frontmatter of {rel_posix}: {parsed.error}")
        if parsed is None or not parsed.is_entity:
            raise KnottError(
                f"not a Knott entity: {rel_posix}; expected a Markdown file in the vault "
                "(outside `.knott/` and hidden folders) whose YAML frontmatter has a `type` key"
            )
        return rel_posix

    def _assign_kids(self, paths: Sequence[str | Path] | None) -> list[FixedEntity]:
        all_markdown = iter_markdown(self.root)
        in_scope = all_markdown if paths is None else self._scope(paths, all_markdown)[0]
        fixed: list[FixedEntity] = []
        for rel_path in in_scope:
            kid = new_kid()
            if insert_kid(self.root, rel_path, kid):
                fixed.append(FixedEntity(path=rel_path, kid=kid))
        return fixed

    def _validate(self, paths: Sequence[str | Path] | None) -> ValidationResult:
        loaded = load_definitions(self.root)
        schemas, relation_defs, issues = loaded.schemas, loaded.relations, loaded.issues
        if any(i.code == "schema-legacy-layout" for i in issues):
            # Every entity would also be `entity-unknown-type`; report only the cause.
            return ValidationResult(issues=issues, stats=Stats(schemas=0, entities=0, relations=0))
        session = VaultSession(self.root, schemas, loaded.connectors)
        all_markdown = session.all_markdown

        if paths is None:
            in_scope = all_markdown
        else:
            in_scope, scope_issues = self._scope(paths, all_markdown)
            issues.extend(scope_issues)

        entities = 0
        relations = 0
        in_scope_kids: set[str] = set()
        for rel_path in in_scope:
            parsed = session.lookup(rel_path)
            if parsed.error is not None:
                issues.append(
                    Issue(
                        code="entity-invalid-frontmatter",
                        path=rel_path,
                        line=parsed.error_line,
                        message=parsed.error,
                    )
                )
                continue
            if not parsed.is_entity:
                continue
            entities += 1
            report = validate_entity(
                parsed, schemas, session.resolve, session.lookup, session.resolve_file
            )
            issues.extend(report.issues)
            relations += report.relations
            assert parsed.frontmatter is not None
            kid = parsed.frontmatter.get(KID_KEY)
            if is_canonical(kid):
                in_scope_kids.add(kid)

        # A duplicate is reported only when one of its claimants is in scope.
        for kid in sorted(in_scope_kids):
            claims = session.kids()[kid]
            if len(claims) > 1:
                issues.append(_duplicate_kid(kid, claims))

        # The reference graph is built only when some property names an acyclic relation.
        scope = None if paths is None else set(in_scope)
        for name in checked_relations(schemas, relation_defs):
            issues.extend(cycle_issues(session.references(), name, scope))

        for _, loop in sorted(loaded.loops.items()):
            issues.extend(unmet_issues(session, loop_report(session, loop), scope))

        stats = Stats(schemas=len(schemas), entities=entities, relations=relations)
        return ValidationResult(issues=_sorted(issues), stats=stats)

    def _scope(
        self,
        paths: Sequence[str | Path],
        all_markdown: list[str],
    ) -> tuple[list[str], list[Issue]]:
        selected: set[str] = set()
        issues: list[Issue] = []
        for given in paths:
            rel_posix = self._vault_relative(given)
            absolute = self.root / rel_posix
            if absolute.is_dir():
                prefix = "" if rel_posix == "." else rel_posix + "/"
                selected.update(p for p in all_markdown if p.startswith(prefix))
                continue
            parsed = read_markdown(absolute, rel_posix) if rel_posix.endswith(".md") else None
            if parsed is not None and (parsed.is_entity or parsed.error is not None):
                selected.add(rel_posix)
            else:
                issues.append(
                    Issue(
                        code="not-an-entity",
                        path=rel_posix,
                        message=(
                            "not a Knott entity: expected a Markdown file whose YAML "
                            "frontmatter has a `type` key"
                        ),
                    )
                )
        return sorted(selected), issues

    def _vault_relative(self, given: str | Path) -> str:
        """``given`` as a vault-relative POSIX path (``.`` for the root).

        Relative paths are resolved against the vault root. Raises
        ``PathNotFoundError`` or ``PathOutsideVaultError``.
        """
        candidate = Path(given)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        if not candidate.exists():
            raise PathNotFoundError(f"path does not exist: {given}")
        # Resolve symlinks in the parent only, so a symlinked file keeps its own path.
        absolute = Path(os.path.abspath(candidate))
        absolute = absolute.parent.resolve() / absolute.name
        try:
            rel = absolute.relative_to(self.root)
        except ValueError:
            raise PathOutsideVaultError(f"path is outside the vault {self.root}: {given}") from None
        return rel.as_posix()

    def _check_config(self) -> None:
        config = self.root / CONFIG_FILE
        if not config.exists():
            return
        try:
            text = config.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ConfigError(f"cannot read {CONFIG_FILE.as_posix()}: {exc}") from exc
        try:
            data = _yaml.load(text).data
        except _yaml.YamlParseError as exc:
            where = f":{exc.line + 1}" if exc.line is not None else ""
            raise ConfigError(f"malformed {CONFIG_FILE.as_posix()}{where}: {exc.message}") from exc
        if data is not None and not isinstance(data, dict):
            raise ConfigError(f"malformed {CONFIG_FILE.as_posix()}: expected a YAML mapping")


def _filename_pattern(definition: FilenameDef | None) -> FilenamePattern | None:
    if definition is None:
        return None
    return FilenamePattern(
        pattern=definition.pattern,
        parts=[
            FilenamePart(name=p.name, match=p.match, description=p.description)
            for p in definition.parts
        ],
    )


def _ontology_attribute(a: AttributeDef) -> OntologyAttribute:
    shape = a.shape
    return OntologyAttribute(
        name=a.name,
        type=shape_kind(shape),
        required=a.required,
        description=a.description,
        items=_ontology_attribute(shape.items) if isinstance(shape, ListShape) else None,
        values=_ontology_attribute(shape.values) if isinstance(shape, MapShape) else None,
        fields=(
            [_ontology_attribute(f) for f in shape.fields.values()]
            if isinstance(shape, ObjectShape)
            else []
        ),
        targets=list(shape.targets) if isinstance(shape, ReferenceShape) else [],
        unknown_targets=list(shape.unknown) if isinstance(shape, ReferenceShape) else [],
        open=isinstance(shape, ReferenceShape) and shape.open,
        relation=shape.relation if isinstance(shape, ReferenceShape) else None,
        accept=list(shape.accept) if isinstance(shape, FileShape) else [],
        options=(
            [EnumOption(value=v, description=d) for v, d in shape.options]
            if isinstance(shape, EnumShape)
            else []
        ),
    )


def _duplicate_kid(kid: str, claims: list[Claim]) -> Issue:
    first = claims[0]
    return Issue(
        code="kid-duplicate",
        path=first.path,
        line=first.line,
        field=KID_KEY,
        message=(
            f"`kid` {kid} is claimed by {len(claims)} entities: {format_claims(claims)}\n"
            "each entity needs its own `kid`; remove the `kid:` line from the copy, "
            "then run `knott validate --fix`"
        ),
    )


def _sorted(issues: list[Issue]) -> list[Issue]:
    return sorted(
        issues,
        key=lambda i: (i.path, i.line or 0, i.field or "", i.code, i.message),
    )
