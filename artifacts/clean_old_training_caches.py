#!/usr/bin/env python3
"""Remove eight user-listed derived caches; preserve all model weights/results.

Default is preview. --apply removes only the exact filenames and sizes below.
Old experiments may need to rebuild these caches before training resumes.
This does not delete the original IQ bank, h0_raw, the shared WVD HDF5 cache,
checkpoints, scorebanks, CSVs, or figures. No training is started by this script.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

FILES = (
    ("output_sim_r10_b257_wang_supcon_stage34_v1/train_stage2.npy", 2408448128),
    ("output_sim_r10_b257_wang_supcon_stage34_v1/val_stage2.npy", 802816128),
    ("output_sim_r10_b242_stft_simam_train_v1/stft_base_float32/train_stft_base.npy", 1981440128),
    ("output_sim_r10_b242_stft_simam_train_v1/stft_base_float32/val_stft_base.npy", 330240128),
    ("output_sim_r10_b268_tdfc_l1tail_full_v1/train_wvd128.npy", 786432128),
    ("output_sim_r10_b268_tdfc_l1tail_full_v1/val_wvd128.npy", 262144128),
    ("output_sim_r10_b269_tdfc_full_finetune_v1/train_wvd128.npy", 786432128),
    ("output_sim_r10_b269_tdfc_full_finetune_v1/val_wvd128.npy", 262144128),
)
TAGS = ("b257", "b242", "b268", "b269")


def candidates(root, files=FILES):
    root = Path(root).resolve(strict=True)
    result = []
    for relative, expected_bytes in files:
        path = root / relative
        if not path.exists() and not path.is_symlink():
            print("Missing; skipped:", relative)
            continue
        if path.is_symlink() or path.resolve() != path or root not in path.resolve().parents or not path.is_file():
            raise RuntimeError("Refusing symlink, escaped path or non-file: " + relative)
        stat = path.stat()
        if stat.st_size != expected_bytes:
            raise RuntimeError("Size changed; nothing deleted. Inspect: " + relative)
        with path.open("rb") as stream:
            if stream.read(6) != b"\x93NUMPY":
                raise RuntimeError("Not a NumPy cache; nothing deleted: " + relative)
        result.append((path, stat))
    return result


def busy_processes(items):
    paths = {str(path.resolve()) for path, _ in items}
    busy = set()
    for process in Path("/proc").iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        try:
            argv = (process / "cmdline").read_bytes().split(b"\0")
            executable = Path(os.fsdecode(argv[0])).name if argv else ""
            text = b" ".join(argv).decode("utf-8", "replace").lower()
            if executable.startswith("python"):
                for tag in TAGS:
                    if tag in text:
                        busy.add(f"PID {process.name}: {tag} Python job is running")
            for descriptor in (process / "fd").iterdir():
                try:
                    opened = os.readlink(descriptor).removesuffix(" (deleted)")
                    if opened in paths:
                        busy.add(f"PID {process.name}: cache file open: {opened}")
                except OSError:
                    continue
        except (OSError, IndexError):
            continue
    return sorted(busy)


def delete_verified(items):
    # Verify every item before deleting the first, then recheck at unlink time.
    def unchanged(path, before):
        now = path.stat()
        return not path.is_symlink() and (now.st_dev, now.st_ino, now.st_size, now.st_mtime_ns) == (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    if not all(unchanged(path, before) for path, before in items):
        raise RuntimeError("Cache changed after preview; nothing deleted")
    for path, before in items:
        if not unchanged(path, before):
            raise RuntimeError("Cache changed during cleanup; stopped: " + str(path))
        path.unlink()
        print("Removed:", path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="AutoDL project root; standalone scripts default to the current directory")
    parser.add_argument("--apply", action="store_true", help="Delete the verified eight derived caches")
    args = parser.parse_args(argv)
    if args.root is None:
        location = Path(__file__).resolve()
        package = location.parent.parent
        args.root = package.parent if location.parent.name == "tools" and (package / "b270_model.py").is_file() else Path.cwd()
    items = candidates(args.root)
    total = sum(stat.st_size for _, stat in items)
    print(f"Candidates: {len(items)}; logical size: {total / 2**30:.3f} GiB")
    for path, stat in items:
        print(f"{stat.st_size / 2**30:.3f} GiB  {path}")
    if not args.apply:
        print("PREVIEW ONLY. Use --apply to remove these caches; old training may need to rebuild them.")
        return
    busy = busy_processes(items)
    if busy:
        raise RuntimeError("No files deleted. Finish the related jobs first:\n" + "\n".join(busy))
    delete_verified(items)
    print("CLEANUP_DONE. Check actual disk availability with df -h /root/autodl-tmp")


if __name__ == "__main__":
    main()
