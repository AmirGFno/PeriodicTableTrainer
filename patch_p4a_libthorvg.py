"""Patch p4a's libthorvg recipe for NDK layouts used by r25b and newer.

Usage: python patch_p4a_libthorvg.py /path/to/python-for-android

The upstream recipe currently searches only lib/clang. NDK r25b can place
libomp.so under lib64/clang, so the patch makes the lookup try both locations.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def patch_recipe(p4a_root: Path) -> None:
    recipe = p4a_root / "pythonforandroid" / "recipes" / "libthorvg" / "__init__.py"
    if not recipe.is_file():
        raise FileNotFoundError(f"libthorvg recipe not found in p4a checkout: {recipe}")
    source = recipe.read_text(encoding="utf-8")

    # Make the operation idempotent for local rebuilds.
    if '"lib64/clang/*/lib/linux"' in source and "matches = [path for pattern" in source:
        print(f"libthorvg already supports both clang library layouts: {recipe}")
        return

    lookup = re.compile(
        r'(?m)^(?P<indent>[ ]*)pattern = join\(self\.ctx\.ndk\.llvm_prebuilt_dir, "lib/clang/\*/lib/linux", lib_arch\)\n'
        r'(?P=indent)clang_lib_dir = glob\(pattern\)\[0\]'
    )
    match = lookup.search(source)
    if not match:
        raise RuntimeError(
            "Could not find the expected libthorvg clang-library lookup. "
            "The upstream recipe may have changed; inspect it before rebuilding."
        )

    indent = match.group("indent")
    replacement = "\n".join(
        [
            f'{indent}patterns = [',
            f'{indent}    join(self.ctx.ndk.llvm_prebuilt_dir, "lib/clang/*/lib/linux", lib_arch),',
            f'{indent}    join(self.ctx.ndk.llvm_prebuilt_dir, "lib64/clang/*/lib/linux", lib_arch),',
            f'{indent}]',
            f'{indent}matches = [path for pattern in patterns for path in glob(pattern)]',
            f'{indent}if not matches:',
            f'{indent}    raise RuntimeError(f"NDK libomp.so not found; checked {{patterns}}")',
            f'{indent}clang_lib_dir = matches[0]',
        ]
    )
    patched, count = lookup.subn(replacement, source, count=1)
    if count != 1:
        raise RuntimeError("Failed to patch libthorvg recipe")
    compile(patched, str(recipe), "exec")
    recipe.write_text(patched, encoding="utf-8")
    print(f"Patched libthorvg recipe to search lib/clang and lib64/clang: {recipe}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python patch_p4a_libthorvg.py /path/to/python-for-android")
    patch_recipe(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    main()
