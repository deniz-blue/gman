from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import Repository, RepositoryStatus


@dataclass(slots=True, frozen=True)
class StatusRow:
    repository: Repository
    status: RepositoryStatus


class SequenceOperator[T](Protocol):
    def apply(self, items: list[T]) -> list[T]:
        ...


@dataclass(slots=True, frozen=True)
class NameContainsFilter:
    needle: str

    def apply(self, items: list[Repository]) -> list[Repository]:
        lowered = self.needle.lower()
        return [repo for repo in items if lowered in repo.name.lower()]


@dataclass(slots=True, frozen=True)
class PathContainsFilter:
    needle: str

    def apply(self, items: list[Repository]) -> list[Repository]:
        lowered = self.needle.lower()
        return [repo for repo in items if lowered in str(repo.path).lower()]


@dataclass(slots=True, frozen=True)
class UnderRootsFilter:
    roots: tuple[Path, ...]

    def apply(self, items: list[Repository]) -> list[Repository]:
        return [repo for repo in items if any(repo.path.is_relative_to(root) for root in self.roots)]


@dataclass(slots=True, frozen=True)
class DirtyFilter:
    def apply(self, items: list[StatusRow]) -> list[StatusRow]:
        return [row for row in items if row.status.is_dirty]


@dataclass(slots=True, frozen=True)
class UpToDateFilter:
    def apply(self, items: list[StatusRow]) -> list[StatusRow]:
        return [row for row in items if row.status.is_up_to_date]


@dataclass(slots=True, frozen=True)
class RepositorySort:
    sort_by: str
    descending: bool = False

    def apply(self, items: list[Repository]) -> list[Repository]:
        if self.sort_by == "name":
            return sorted(items, key=lambda repository: repository.name.lower(), reverse=self.descending)
        return sorted(items, key=lambda repository: str(repository.path).lower(), reverse=self.descending)


@dataclass(slots=True, frozen=True)
class StatusSort:
    sort_by: str
    descending: bool = False

    def apply(self, items: list[StatusRow]) -> list[StatusRow]:
        if self.sort_by == "name":
            return sorted(items, key=lambda row: row.repository.name.lower(), reverse=self.descending)
        if self.sort_by == "branch":
            return sorted(items, key=lambda row: row.status.current_branch.lower(), reverse=self.descending)
        if self.sort_by == "ahead":
            return sorted(items, key=lambda row: row.status.ahead_count, reverse=self.descending)
        if self.sort_by == "behind":
            return sorted(items, key=lambda row: row.status.behind_count, reverse=self.descending)
        return sorted(items, key=lambda row: str(row.repository.path).lower(), reverse=self.descending)


@dataclass(slots=True, frozen=True)
class LimitFilter[T]:
    limit: int | None

    def apply(self, items: list[T]) -> list[T]:
        if self.limit is None or self.limit < 0:
            return items
        return items[: self.limit]


@dataclass(slots=True, frozen=True)
class RepositorySelection:
    name_contains: str | None
    path_contains: str | None
    under_roots: tuple[Path, ...]
    sort_by: str
    descending: bool
    limit: int | None

    @classmethod
    def from_args(cls, args) -> RepositorySelection:
        roots = tuple(root.expanduser().resolve() for root in (getattr(args, "under_root", None) or []))
        return cls(
            name_contains=getattr(args, "name_contains", None),
            path_contains=getattr(args, "path_contains", None),
            under_roots=roots,
            sort_by=getattr(args, "sort_by", "path"),
            descending=getattr(args, "descending", False),
            limit=getattr(args, "limit", None),
        )

    def repository_filters(self) -> list[SequenceOperator[Repository]]:
        filters: list[SequenceOperator[Repository]] = []
        if self.name_contains:
            filters.append(NameContainsFilter(self.name_contains))
        if self.path_contains:
            filters.append(PathContainsFilter(self.path_contains))
        if self.under_roots:
            filters.append(UnderRootsFilter(self.under_roots))
        return filters

    def repository_ordering(self) -> list[SequenceOperator[Repository]]:
        return [RepositorySort(sort_by=self.sort_by, descending=self.descending)]

    def repository_limit(self) -> list[SequenceOperator[Repository]]:
        return [LimitFilter[Repository](self.limit)]


@dataclass(slots=True, frozen=True)
class ListOptions:
    status: bool
    dirty_only: bool
    up_to_date_only: bool

    @classmethod
    def from_args(cls, args) -> ListOptions:
        return cls(
            status=args.status,
            dirty_only=args.dirty,
            up_to_date_only=args.clean,
        )

    def requires_status(self, sort_by: str) -> bool:
        return bool(
            self.status
            or self.dirty_only
            or self.up_to_date_only
            or sort_by in {"branch", "ahead", "behind"}
        )

    def should_print_status(self, sort_by: str) -> bool:
        return self.requires_status(sort_by)

    def status_filters(self) -> list[SequenceOperator[StatusRow]]:
        filters: list[SequenceOperator[StatusRow]] = []
        if self.dirty_only:
            filters.append(DirtyFilter())
        if self.up_to_date_only:
            filters.append(UpToDateFilter())
        return filters


def status_rows(repositories: list[Repository]) -> list[StatusRow]:
    return [StatusRow(repository=repository, status=repository.status()) for repository in repositories]


def apply_operators[T](items: list[T], operators: list[SequenceOperator[T]]) -> list[T]:
    result = items
    for operator in operators:
        result = operator.apply(result)
    return result