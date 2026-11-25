"""
Copies the dependencies of `requirements.txt` into the `dependencies` list of `pyproject.toml`.
Used after `pip-audit --fix`, which can add a pin for a vulnerable subdependency to `requirements.txt` only.
"""

import json
import re
import sys
import tomllib

from check_dependencies_sync import (
    COMMENT_PATTERN,
    SERVICE_DIR,
    UnsupportedRequirementError,
    read_pyproject_toml,
    read_requirements_txt,
)

PYPROJECT_PATH = SERVICE_DIR / "pyproject.toml"
REQUIREMENTS_PATH = SERVICE_DIR / "requirements.txt"

# The whole `dependencies = [ ... ]` block of the [project] table.
DEPENDENCIES_PATTERN = re.compile(
    r"^dependencies = \[\n.*?^\]\n", re.DOTALL | re.MULTILINE
)


def build_dependencies_block() -> str:
    lines = REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
    requirements = [COMMENT_PATTERN.sub("", line).strip() for line in lines]
    entries = "".join(
        f"    {json.dumps(requirement)},\n"
        for requirement in requirements
        if requirement
    )
    return f"dependencies = [\n{entries}]\n"


def main() -> int:
    try:
        if read_requirements_txt() == read_pyproject_toml():
            print("pyproject.toml already lists the dependencies of requirements.txt")
            return 0
    except UnsupportedRequirementError as error:
        print(error)
        return 1

    raw = PYPROJECT_PATH.read_bytes().decode("utf-8")
    uses_crlf = "\r\n" in raw
    content = raw.replace("\r\n", "\n")
    updated, replacements = DEPENDENCIES_PATTERN.subn(
        lambda _: build_dependencies_block(), content, count=1
    )
    if replacements != 1:
        print("pyproject.toml: could not find the `dependencies = [ ... ]` block")
        return 1

    # Fails before the file is written if the result is not valid TOML.
    tomllib.loads(updated)
    if uses_crlf:
        updated = updated.replace("\n", "\r\n")
    PYPROJECT_PATH.write_bytes(updated.encode("utf-8"))
    print("pyproject.toml: dependencies replaced with those of requirements.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
