"""
Fails when `requirements.txt` and `pyproject.toml` list different dependencies.
`pyproject.toml` is used by the FastAPI Cloud deployment and `requirements.txt` by the Docker image.
"""

import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

SERVICE_DIR = Path(__file__).resolve().parent.parent


def normalize(requirement_line: str) -> str:
    requirement = Requirement(requirement_line)
    extras = ",".join(sorted(requirement.extras))
    name = canonicalize_name(requirement.name)
    return (
        f"{name}[{extras}]{requirement.specifier}"
        if extras
        else f"{name}{requirement.specifier}"
    )


def read_requirements_txt() -> set[str]:
    lines = (SERVICE_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
    stripped = (line.split("#", 1)[0].strip() for line in lines)
    return {normalize(line) for line in stripped if line}


def read_pyproject_toml() -> set[str]:
    with open(SERVICE_DIR / "pyproject.toml", "rb") as pyproject_file:
        dependencies = tomllib.load(pyproject_file)["project"]["dependencies"]
    return {normalize(dependency) for dependency in dependencies}


def main() -> int:
    requirements_txt = read_requirements_txt()
    pyproject_toml = read_pyproject_toml()
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
