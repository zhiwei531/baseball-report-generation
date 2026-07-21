from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def tracked_files(suffix: str) -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z", f"*{suffix}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return tuple(
        ROOT / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item and not Path(item.decode("utf-8")).name.startswith("._")
    )


def validate_python(path: Path) -> tuple[int, int]:
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    tree = ast.parse(source, filename=str(path))
    path_mutations = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if (
            isinstance(owner, ast.Attribute)
            and isinstance(owner.value, ast.Name)
            and owner.value.id == "sys"
            and owner.attr == "path"
            and node.func.attr in {"append", "insert", "extend"}
        ):
            path_mutations += 1
    return 1, path_mutations


def validate_repository(*, check_node: bool = True) -> dict[str, int]:
    python_files = tracked_files(".py")
    mutation_count = 0
    for path in python_files:
        _count, mutations = validate_python(path)
        mutation_count += mutations
    if mutation_count:
        raise RuntimeError(f"tracked Python sources contain {mutation_count} sys.path mutations")

    node_files = tracked_files(".mjs") if check_node else ()
    for path in node_files:
        subprocess.run(["node", "--check", str(path)], cwd=ROOT, check=True)
    return {
        "python_files": len(python_files),
        "node_files": len(node_files),
        "sys_path_mutations": mutation_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate only Git-tracked source files, ignoring macOS AppleDouble sidecars."
    )
    parser.add_argument("--skip-node", action="store_true")
    args = parser.parse_args()
    try:
        summary = validate_repository(check_node=not args.skip_node)
    except (OSError, SyntaxError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"source validation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
