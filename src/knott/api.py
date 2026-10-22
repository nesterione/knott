"""The Knott API. The CLI is a thin adapter over this module."""

from __future__ import annotations

import os
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version
from pathlib import Path

from knott import _yaml
from knott.errors import ConfigError, PathNotFoundError, PathOutsideVaultError
from knott.models import (
    FixedEntity,
    InitResult,
    Issue,
    Ontology,
    OntologyAttribute,
    OntologyRelation,
    OntologyType,
    SchemaInfo,
    Stats,
    ValidationResult,
)
from knott.schema.loader import SCHEMAS_DIR, load_schemas
from knott.schema.models import (
    AttributeDef,
    ListShape,
    MapShape,
    ObjectShape,
    RelationDef,
    shape_kind,
)
from knott.schema.validator import validate_entity
from knott.vault.discovery import KNOTT_DIR, find_vault_root, iter_markdown
from knott.vault.entity import MarkdownFile, read_markdown
from knott.vault.fix import insert_kid
from knott.vault.kid import (
    KID_KEY,
    Claim,
    KidIndex,
    build_index,
    format_claims,
    is_canonical,
    new_kid,
)
from knott.vault.links import ResolvedReference, resolve_reference

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
        """Create ``.knott/schemas/`` and ``.knott/config.yaml`` in ``path``.

        Changes nothing if ``.knott/`` already exists.
        """
        root = Path(path)
        if not root.is_dir():
            raise PathNotFoundError(f"directory does not exist: {path}")
        knott_dir = root / KNOTT_DIR
        if knott_dir.exists():
            return InitResult(root=str(root.resolve()), created=False)
        (root / SCHEMAS_DIR).mkdir(parents=True)
        (root / CONFIG_FILE).write_text(f"knott_version: {version()}\n", encoding="utf-8")
        return InitResult(root=str(root.resolve()), created=True)

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
        """The vault's types, their attributes and relations, and entity counts.

        Types are sorted by name; attributes and relations keep their schema order,
        with relations to undefined types last (``target_known=False``). Files with
        invalid frontmatter are not counted.
        """
        schemas, issues = load_schemas(self.root)
        counts: dict[str, int] = {}
        for rel_path in iter_markdown(self.root):
            parsed = read_markdown(self.root / rel_path, rel_path)
            if parsed.error is None and parsed.is_entity and isinstance(parsed.type, str):
                counts[parsed.type] = counts.get(parsed.type, 0) + 1

        def relation(r: RelationDef, known: bool) -> OntologyRelation:
            return OntologyRelation(
                name=r.name,
                target=r.target,
                required=r.required,
                description=r.description,
                target_known=known,
            )

        types = [
            OntologyType(
                type=s.type,
                description=s.description,
                path=s.path,
                count=counts.get(s.type, 0),
                kid_required=s.kid_required,
                attributes=[_ontology_attribute(a) for a in s.attributes.values()],
                relations=[relation(r, True) for r in s.relations.values()]
                + [relation(r, False) for r in s.unknown_relations.values()],
            )
            for _, s in sorted(schemas.items())
        ]
        return Ontology(vault=self.root.name, types=types, schema_issues=len(issues))

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
        schemas, issues = load_schemas(self.root)
        files: dict[str, MarkdownFile] = {}

        def lookup(rel_path: str) -> MarkdownFile:
            parsed = files.get(rel_path)
            if parsed is None:
                parsed = read_markdown(self.root / rel_path, rel_path)
                files[rel_path] = parsed
            return parsed

        all_markdown = iter_markdown(self.root)
        kid_index: KidIndex | None = None

        def kids() -> KidIndex:
            """Built on first use, so vaults and runs that never touch a `kid` pay nothing."""
            nonlocal kid_index
            if kid_index is None:
                kid_index = build_index(all_markdown, lookup)
            return kid_index

        def resolve(source: str, reference: str) -> ResolvedReference:
            return resolve_reference(self.root, source, reference, kids)

        if paths is None:
            in_scope = all_markdown
        else:
            in_scope, scope_issues = self._scope(paths, all_markdown)
            issues.extend(scope_issues)

        entities = 0
        relations = 0
        in_scope_kids: set[str] = set()
        for rel_path in in_scope:
            parsed = lookup(rel_path)
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
            report = validate_entity(parsed, schemas, resolve, lookup)
            issues.extend(report.issues)
            relations += report.relations
            assert parsed.frontmatter is not None
            kid = parsed.frontmatter.get(KID_KEY)
            if is_canonical(kid):
                in_scope_kids.add(kid)

        # A duplicate is reported only when one of its claimants is in scope.
        for kid in sorted(in_scope_kids):
            claims = kids()[kid]
            if len(claims) > 1:
                issues.append(_duplicate_kid(kid, claims))

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
                raise PathOutsideVaultError(
                    f"path is outside the vault {self.root}: {given}"
                ) from None
            rel_posix = rel.as_posix()
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
