#!/usr/bin/env python3
"""Read selected small research sources/metadata; export no IQ or score arrays."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile


SOURCE_DIRS = (
    "SIM_R10_STAGE_B223_EXTERNAL_BASELINES_V1",
    "SIM_R10_B227_FROZEN_SCORE_FUSION_V1",
    "B251_LMDA_L1_SCORE_BRIDGE_V1",
    "B244_LMDA_L1_COMPLEMENTARITY_AUDIT_V1",
    "B251_TAIL_AWARE_GATE_V1",
    "B260_L1_INTERNAL_ADSCM_V1",
    "B263_L1_EARLY_TF_ADAPT_V1",
)
OUTPUT_DIRS = (
    "output_sim_r10_b223_external_baselines_v1",
    "output_sim_r10_b227_score_fusion_exploratory_v1",
    "output_sim_r10_b244_lmda_l1_complementarity_v1",
    "output_sim_r10_b251_tail_aware_gate_v1",
    "output_b270_adn_l1_tdfc_v2",
)
SMALL_FILES = (
    "output_sim_r10_b213_dev_pfa1e4_1e5_v1/protocol_frozen.json",
    "output_sim_r10_b213_dev_pfa1e4_1e5_v1/progress.json",
    "output_sim_r10_b215_tpht_train_v1/trainseed_20261022/L1_TAIL/training_contract.json",
    "output_sim_r10_b270_wvd_rebuilt_v1/recovery_validation.json",
    "SIM_R10_IQ512_TRAIN30000_VAL5000_SEED20261009_V1/sim_r10_iq512_v1_contract.json",
    "codex_b270_recovery_night.log",
)
TEXT_EXTENSIONS = {".py", ".json", ".csv", ".md", ".txt", ".sha256"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".cache", ".matplotlib_cache", ".venv"}


def iter_files(directory):
    for parent, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (Path(parent) / d).is_symlink()]
        for name in files:
            yield Path(parent) / name


def collect(root, destination, max_file_bytes=4 << 20, max_total_bytes=32 << 20):
    root = Path(root).resolve()
    destination = Path(destination).resolve()
    if not root.is_dir():
        raise RuntimeError(f"Project root not found: {root}")
    if destination.exists():
        raise RuntimeError(f"Archive exists; preserve it and choose another --out: {destination}")
    selected, skipped, missing = {}, [], []

    def consider(path, lmda_weight=False):
        if not path.is_file() or path.is_symlink():
            return
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            return
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() not in TEXT_EXTENSIONS and not lmda_weight and relative not in SMALL_FILES:
            return
        size = path.stat().st_size
        if size > max_file_bytes:
            skipped.append(dict(path=relative, bytes=size, reason="larger than per-file export limit"))
            return
        selected[relative] = path

    for name in SOURCE_DIRS:
        folder = root / name
        if not folder.is_dir():
            missing.append(name)
            continue
        for path in iter_files(folder):
            consider(path)
    for path in root.glob("*.py"):
        if any(tag in path.name.lower() for tag in ("b223", "b227", "b244", "b251")):
            consider(path)
    for name in OUTPUT_DIRS:
        folder = root / name
        if not folder.is_dir():
            missing.append(name)
            continue
        for path in iter_files(folder):
            relative = path.relative_to(folder)
            if name == "output_sim_r10_b223_external_baselines_v1":
                # Keep top-level metadata and the actual SIM LMDA branch only;
                # no other external baseline checkpoints or generated arrays.
                if len(relative.parts) > 1 and not any("lmda" in part.lower() for part in relative.parts):
                    continue
            lmda_weight = name == "output_sim_r10_b223_external_baselines_v1" and path.suffix.lower() in (".pt", ".pth") and any("lmda" in part.lower() for part in relative.parts)
            consider(path, lmda_weight)
    for name in SMALL_FILES:
        path = root / name
        if path.is_file():
            consider(path)
        else:
            missing.append(name)
    total = sum(path.stat().st_size for path in selected.values())
    if total > max_total_bytes:
        raise RuntimeError(f"Selected files total {total / 2**20:.1f} MiB; nothing exported. Inspect files or increase --max-total-mib.")
    records = []
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        raise RuntimeError(f"Export temporary file already exists: {temporary}")
    with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for relative, path in sorted(selected.items()):
            data = path.read_bytes()
            records.append(dict(path=relative, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            archive.writestr("B271_REFERENCE/" + relative, data)
        manifest = dict(version="B271_REFERENCE_EXPORT_V1", included_files=len(records), uncompressed_bytes=total,
                        files=records, missing_paths=missing, skipped_files=skipped,
                        excluded="No HDF5/IQ, NPY/NPZ score arrays, raw radar data, or large model checkpoints; no original files changed.")
        archive.writestr("B271_REFERENCE/EXPORT_MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(destination)
    print(f"Created: {destination}\nZIP: {destination.stat().st_size / 2**20:.2f} MiB; files: {len(records)}", flush=True)
    for name in missing:
        print(f"Not found: {name}", flush=True)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--out", type=Path)
    p.add_argument("--max-file-mib", type=int, default=4)
    p.add_argument("--max-total-mib", type=int, default=32)
    a = p.parse_args()
    if min(a.max_file_mib, a.max_total_mib) < 1:
        p.error("Export limits must be positive")
    collect(a.root, a.out or a.root / "B271_REFERENCE_MINI.zip", a.max_file_mib << 20, a.max_total_mib << 20)


if __name__ == "__main__":
    main()
