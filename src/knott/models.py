"""Public result types. All plain data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Issue(_Frozen):
    """One validation problem."""

    code: str
    path: str
    """Vault-relative POSIX path of the file with the problem."""
    line: int | None = None
    """1-based line number, when known."""
    field: str | None = None
    message: str


class Stats(_Frozen):
    schemas: int = 0
    entities: int = 0
    relations: int = 0


class ValidationResult(_Frozen):
    issues: list[Issue]
    stats: Stats

    @property
    def ok(self) -> bool:
        return not self.issues


class SchemaInfo(_Frozen):
    """A discovered entity type."""

    type: str
    description: str | None
    path: str
    """Vault-relative path of the schema file."""


class InitResult(_Frozen):
    root: str
    created: bool
