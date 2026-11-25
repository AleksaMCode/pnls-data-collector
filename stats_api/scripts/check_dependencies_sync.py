"""
Fails when `requirements.txt` and `pyproject.toml` list different dependencies.
`pyproject.toml` is used by the FastAPI Cloud deployment and `requirements.txt` by the Docker image.
"""

import re
import sys
import tomllib
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

SERVICE_DIR = Path(__file__).resolve().parent.parent

# A "#" starts a comment only at the start of a line or after whitespace, so URL fragments are kept.
COMMENT_PATTERN = re.compile(r"(^|\s)#.*$")


class UnsupportedRequirementError(Exception):
    pass


def normalize(requirement_line: str, source: str) -> str:
    """Returns a comparison key made of the name, extras, version or URL, and environment marker."""
    try:
        requirement = Requirement(requirement_line)
    except InvalidRequirement as error:
        raise UnsupportedRequirementError(
            f"{source}: unsupported requirement '{requirement_line}' ({error}). "
            "Use the 'name==version' or 'name @ url' form."
        ) from error

    key = canonicalize_name(requirement.name)
    if requirement.extras:
        key += f"[{','.join(sorted(requirement.extras))}]"
    key += f" @ {requirement.url}" if requirement.url else str(requirement.specifier)
    if requirement.marker:
        key += f"; {requirement.marker}"
    return key


def read_requirements_txt() -> set[str]:
    lines = (SERVICE_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
    stripped = (COMMENT_PATTERN.sub("", line).strip() for line in lines)
    return {normalize(line, "requirements.txt") for line in stripped if line}


def read_pyproject_toml() -> set[str]:
    with open(SERVICE_DIR / "pyproject.toml", "rb") as pyproject_file:
        dependencies = tomllib.load(pyproject_file)["project"]["dependencies"]
    return {normalize(dependency, "pyproject.toml") for dependency in dependencies}


def main() -> int:
    try:
        requirements_txt = read_requirements_txt()
        pyproject_toml = read_pyproject_toml()
    except UnsupportedRequirementError as error:
        print(error)
        return 1

    if requirements_txt == pyproject_toml:
        print("requirements.txt and pyproject.toml list the same dependencies")
        return 0

    print("requirements.txt and pyproject.toml list different dependencies:")
    for dependency in sorted(requirements_txt - pyproject_toml):
        print(f"  only in requirements.txt: {dependency}")
    for dependency in sorted(pyproject_toml - requirements_txt):
        print(f"  only in pyproject.toml:   {dependency}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
