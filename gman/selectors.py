from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from .models import Repository, RepositoryStatus


@dataclass(slots=True, frozen=True)
class StatusRow:
    repository: Repository
    status: RepositoryStatus


class SequenceOperator[T](ABC):
    @abstractmethod
    def apply(self, items: list[T]) -> list[T]:
        ...


class RepositoryOperator(SequenceOperator[Repository]):
    @classmethod
    def from_args(cls, args) -> RepositoryOperator | None:
        raise NotImplementedError


class StatusOperator(SequenceOperator[StatusRow]):
    @classmethod
    def from_args(cls, args) -> StatusOperator | None:
        raise NotImplementedError


@dataclass(slots=True, frozen=True)
class NameContainsFilter:
    needle: str

    @classmethod
    def from_args(cls, args) -> NameContainsFilter | None:
        needle = getattr(args, "name_contains", None)
        if not needle:
            return None
        return cls(needle)

    def apply(self, items: list[Repository]) -> list[Repository]:
        lowered = self.needle.lower()
        return [repo for repo in items if lowered in repo.name.lower()]


@dataclass(slots=True, frozen=True)
class PathContainsFilter:
    needle: str

    @classmethod
    def from_args(cls, args) -> PathContainsFilter | None:
        needle = getattr(args, "path_contains", None)
        if not needle:
            return None
        return cls(needle)

    def apply(self, items: list[Repository]) -> list[Repository]:
        lowered = self.needle.lower()
        return [repo for repo in items if lowered in str(repo.path).lower()]


@dataclass(slots=True, frozen=True)
class UnderRootsFilter:
    roots: tuple[Path, ...]

    @classmethod
    def from_args(cls, args) -> UnderRootsFilter | None:
        roots = tuple(root.expanduser().resolve() for root in (getattr(args, "under_root", None) or []))
        if not roots:
            return None
        return cls(roots)

    def apply(self, items: list[Repository]) -> list[Repository]:
        return [repo for repo in items if any(repo.path.is_relative_to(root) for root in self.roots)]


@dataclass(slots=True, frozen=True)
class DirtyFilter:
    @classmethod
    def from_args(cls, args) -> DirtyFilter | None:
        if not getattr(args, "dirty", False):
            return None
        return cls()

    def apply(self, items: list[StatusRow]) -> list[StatusRow]:
        return [row for row in items if row.status.is_dirty]


@dataclass(slots=True, frozen=True)
class UpToDateFilter:
    @classmethod
    def from_args(cls, args) -> UpToDateFilter | None:
        if not getattr(args, "clean", False):
            return None
        return cls()

    def apply(self, items: list[StatusRow]) -> list[StatusRow]:
        return [row for row in items if row.status.is_up_to_date]


@dataclass(slots=True, frozen=True)
class LimitFilter[T](SequenceOperator[T]):
    limit: int | None

    def apply(self, items: list[T]) -> list[T]:
        if self.limit is None or self.limit < 0:
            return items
        return items[: self.limit]


@dataclass(slots=True, frozen=True)
class RepositorySort(RepositoryOperator, ABC):
    sort_name: ClassVar[str]
    descending: bool = False

    @classmethod
    def from_args(cls, args) -> RepositorySort | None:
        if getattr(args, "sort_by", "path") != cls.sort_name:
            return None
        return cls(descending=getattr(args, "descending", False))

    @abstractmethod
    def sort_value(self, repository: Repository) -> object:
        raise NotImplementedError

    def apply(self, items: list[Repository]) -> list[Repository]:
        return sorted(items, key=self.sort_value, reverse=self.descending)


@dataclass(slots=True, frozen=True)
class StatusSort(StatusOperator, ABC):
    sort_name: ClassVar[str]
    requires_status: ClassVar[bool] = False
    descending: bool = False

    @classmethod
    def from_args(cls, args) -> StatusSort | None:
        if getattr(args, "sort_by", "path") != cls.sort_name:
            return None
        return cls(descending=getattr(args, "descending", False))

    @abstractmethod
    def sort_value(self, row: StatusRow) -> object:
        raise NotImplementedError

    def apply(self, items: list[StatusRow]) -> list[StatusRow]:
        return sorted(items, key=self.sort_value, reverse=self.descending)


@dataclass(slots=True, frozen=True)
class RepositoryPathSort(RepositorySort):
    sort_name: ClassVar[str] = "path"

    def sort_value(self, repository: Repository) -> object:
        return str(repository.path).lower()


@dataclass(slots=True, frozen=True)
class RepositoryNameSort(RepositorySort):
    sort_name: ClassVar[str] = "name"

    def sort_value(self, repository: Repository) -> object:
        return repository.name.lower()


@dataclass(slots=True, frozen=True)
class StatusPathSort(StatusSort):
    sort_name: ClassVar[str] = "path"

    def sort_value(self, row: StatusRow) -> object:
        return str(row.repository.path).lower()


@dataclass(slots=True, frozen=True)
class StatusNameSort(StatusSort):
    sort_name: ClassVar[str] = "name"

    def sort_value(self, row: StatusRow) -> object:
        return row.repository.name.lower()


@dataclass(slots=True, frozen=True)
class StatusBranchSort(StatusSort):
    sort_name: ClassVar[str] = "branch"
    requires_status: ClassVar[bool] = True

    def sort_value(self, row: StatusRow) -> object:
        return row.status.current_branch.lower()


@dataclass(slots=True, frozen=True)
class StatusAheadSort(StatusSort):
    sort_name: ClassVar[str] = "ahead"
    requires_status: ClassVar[bool] = True

    def sort_value(self, row: StatusRow) -> object:
        return row.status.ahead_count


@dataclass(slots=True, frozen=True)
class StatusBehindSort(StatusSort):
    sort_name: ClassVar[str] = "behind"
    requires_status: ClassVar[bool] = True

    def sort_value(self, row: StatusRow) -> object:
        return row.status.behind_count


def status_rows(repositories: list[Repository]) -> list[StatusRow]:
    return [StatusRow(repository=repository, status=repository.status()) for repository in repositories]


def repository_filters_from_args(args) -> list[SequenceOperator[Repository]]:
    filters: list[SequenceOperator[Repository]] = []
    for operator in (
        NameContainsFilter.from_args(args),
        PathContainsFilter.from_args(args),
        UnderRootsFilter.from_args(args),
    ):
        if operator is not None:
            filters.append(operator)
    return filters


def repository_sort_from_args(args) -> RepositorySort:
    operators = [
        RepositoryPathSort.from_args(args),
        RepositoryNameSort.from_args(args),
    ]
    for operator in operators:
        if operator is not None:
            return operator
    return RepositoryPathSort(descending=getattr(args, "descending", False))


def repository_limit_from_args(args) -> LimitFilter[Repository]:
    return LimitFilter[Repository](getattr(args, "limit", None))


def status_filters_from_args(args) -> list[SequenceOperator[StatusRow]]:
    filters: list[SequenceOperator[StatusRow]] = []
    for operator in (
        DirtyFilter.from_args(args),
        UpToDateFilter.from_args(args),
    ):
        if operator is not None:
            filters.append(operator)
    return filters


def status_sort_from_args(args) -> StatusSort:
    operators = [
        StatusPathSort.from_args(args),
        StatusNameSort.from_args(args),
        StatusBranchSort.from_args(args),
        StatusAheadSort.from_args(args),
        StatusBehindSort.from_args(args),
    ]
    for operator in operators:
        if operator is not None:
            return operator
    return StatusPathSort(descending=getattr(args, "descending", False))


def requires_status(args) -> bool:
    selected_sort = status_sort_from_args(args)
    return bool(getattr(args, "status", False) or status_filters_from_args(args) or selected_sort.requires_status)


def apply_operators[T](items: list[T], operators: list[SequenceOperator[T]]) -> list[T]:
    result = items
    for operator in operators:
        result = operator.apply(result)
    return result