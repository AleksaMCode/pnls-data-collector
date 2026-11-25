"""
Fails when a Python service pins a dependency differently than `util/requirements.txt`.
The services install both files, so a different pin for the same package is a drift.
"""

import re
import sys
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

REPO_DIR = Path(__file__).resolve().parent.parent
UTIL_DIR_NAME = "util"
REQUIREMENTS_FILE_NAME = "requirements.txt"

# A "#" starts a comment only at the start of a line or after whitespace, so URL fragments are kept.
COMMENT_PATTERN = re.compile(r"(^|\s)#.*$")


class UnsupportedRequirementError(Exception):
    pass


def read_pins(requirements_path: Path) -> dict[str, str]:
    """Returns the pin (version or URL, and environment marker) of every package in the file."""
    source = requirements_path.relative_to(REPO_DIR).as_posix()
    pins = {}
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        requirement_line = COMMENT_PATTERN.sub("", line).strip()
        if not requirement_line:
            continue
        try:
            requirement = Requirement(requirement_line)
        except InvalidRequirement as error:
            raise UnsupportedRequirementError(
                f"{source}: unsupported requirement '{requirement_line}' ({error}). "
                "Use the 'name==version' or 'name @ url' form."
            ) from error

        pin = f"@ {requirement.url}" if requirement.url else str(requirement.specifier)
        if requirement.marker:
            pin += f"; {requirement.marker}"
        pins[canonicalize_name(requirement.name)] = pin
    return pins


def find_service_requirements() -> list[Path]:
    return sorted(
        path
        for path in REPO_DIR.glob(f"*/{REQUIREMENTS_FILE_NAME}")
        if path.parent.name != UTIL_DIR_NAME
    )


def main() -> int:
    try:
        util_pins = read_pins(REPO_DIR / UTIL_DIR_NAME / REQUIREMENTS_FILE_NAME)
        service_pins = {
            path.parent.name: read_pins(path) for path in find_service_requirements()
        }
    except UnsupportedRequirementError as error:
        print(error)
        return 1

    drifts = [
        f"  {service}: {package}{pin or ' (no version)'}, "
        f"util: {package}{util_pins[package] or ' (no version)'}"
        for service, pins in service_pins.items()
        for package, pin in sorted(pins.items())
        if package in util_pins and pin != util_pins[package]
    ]
    if drifts:
        print("Dependencies pinned differently than in util/requirements.txt:")
        print("\n".join(drifts))
        return 1

    print(
        f"{len(service_pins)} services pin their shared dependencies "
        "the same as util/requirements.txt"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
