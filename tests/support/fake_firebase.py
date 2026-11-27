"""An in-memory stand-in for `firebase_admin.db`, for unit tests of code that walks the tree."""

import copy


class FakeRealtimeDatabase:
    """Behaves like `firebase_admin.db` for `reference()`, `get()`, `child()`, `delete()` and `update()`.

    `get(shallow=True)` returns `True` for child objects and the value for leaves, as Firebase does.
    Paths in `fail_delete` / `fail_update` raise on those calls, as an oversized request would.
    """

    def __init__(self, tree: dict | None = None):
        self.tree = copy.deepcopy(tree or {})
        self.fail_delete: set[str] = set()
        self.fail_update: set[str] = set()
        self.fail_get: dict[str, int] = {}
        self.calls: list[tuple[str, str]] = []

    def reference(self, path: str = "/") -> "FakeReference":
        return FakeReference(self, _parts(path))

    def node(self, parts: list[str]):
        node = self.tree
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node


class FakeReference:
    def __init__(self, database: FakeRealtimeDatabase, parts: list[str]):
        self.database = database
        self.parts = parts

    @property
    def path(self) -> str:
        return "/" + "/".join(self.parts)

    def child(self, key: str) -> "FakeReference":
        return FakeReference(self.database, [*self.parts, *_parts(key)])

    def get(self, shallow: bool = False):
        self.database.calls.append(("get", self.path))
        if self.database.fail_get.get(self.path, 0) > 0:
            self.database.fail_get[self.path] -= 1
            raise RuntimeError(f"Read of {self.path} failed.")
        node = self.database.node(self.parts)
        if not shallow or not isinstance(node, dict):
            return copy.deepcopy(node)
        return {
            key: True if isinstance(value, dict) else value
            for key, value in node.items()
        } or None

    def delete(self):
        self.database.calls.append(("delete", self.path))
        if self.path in self.database.fail_delete:
            raise RuntimeError(f"Delete of {self.path} is too large.")
        if not self.parts:
            self.database.tree = {}
            return
        parent = self.database.node(self.parts[:-1])
        if isinstance(parent, dict):
            parent.pop(self.parts[-1], None)
            self._prune(self.parts[:-1])

    def update(self, values: dict):
        self.database.calls.append(("update", self.path))
        if self.path in self.database.fail_update:
            raise RuntimeError(f"Update of {self.path} failed.")
        node = self.database.tree
        for part in self.parts:
            node = node.setdefault(part, {})
        for key, value in values.items():
            if value is None:
                node.pop(key, None)
            else:
                node[key] = value
        self._prune(self.parts)

    def _prune(self, parts: list[str]):
        # Firebase does not keep empty objects.
        while parts:
            node = self.database.node(parts)
            if node != {}:
                return
            self.database.node(parts[:-1]).pop(parts[-1])
            parts = parts[:-1]


def _parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]
