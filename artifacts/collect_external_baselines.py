#!/usr/bin/env python3
"""Collect existing baseline code and small reports; never train or modify source files."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import stat
from zipfile import ZipFile, ZIP_DEFLATED

TOKENS = ('b223', 'b224', 'b225', 'b226', 'b232', 'b238', 'b241', 'b242',
          'fsst', 'farccat', 'farc_cat', 'cvhst', 'stft_simam')
EXTRA_FILES = ('r10_sim_stage_b213_scorebank_v1.py',
               'r10_sim_iq512_builder_v1_EARLIEST_HDF5.py')
SMALL_SUFFIXES = {'.py', '.sh', '.json', '.csv', '.md', '.txt', '.pdf', '.yaml', '.yml'}
SKIP_DIRS = {'__pycache__', '.git', '.cache', 'node_modules', 'h0_raw', 'final203_pack'}
MAX_FILE = 2 * 1024**2
MAX_TOTAL = 80 * 1024**2


def selected(name):
    return any(token in name.lower() for token in TOKENS)


def regular_file(path):
    return stat.S_ISREG(path.lstat().st_mode)


def scan(root):
    candidates = sorted(p for p in root.iterdir()
                        if selected(p.name) or p.name in EXTRA_FILES)
    rows, candidates_report, errors = [], [], []
    for candidate in candidates:
        rel = candidate.relative_to(root).as_posix()
        if candidate.is_symlink():
            candidates_report.append({'path': rel, 'kind': 'symlink', 'target': os.readlink(candidate)})
            continue
        candidates_report.append({'path': rel, 'kind': 'directory' if candidate.is_dir() else 'file'})
        if candidate.is_dir():
            def onerror(error):
                errors.append(str(error))
            files = []
            for base, dirs, names in os.walk(candidate, followlinks=False, onerror=onerror):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (Path(base) / d).is_symlink())
                files.extend(Path(base) / name for name in sorted(names))
        else:
            files = [candidate]
        for path in files:
            try:
                relative = path.relative_to(root).as_posix()
                if path.is_symlink():
                    rows.append({'path': relative, 'kind': 'symlink', 'target': os.readlink(path), 'included': False})
                    continue
                if not regular_file(path):
                    continue
                s = path.stat()
                rows.append({'path': relative, 'kind': 'file', 'bytes': s.st_size,
                             'mtime_ns': s.st_mtime_ns, 'included': False})
            except OSError as exc:
                errors.append(f'{path}: {exc}')
    return candidates_report, rows, errors


def collect(root, output):
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Root must be a directory')
    output = output.absolute()
    if output.exists():
        raise FileExistsError(f'Output already exists; choose a different --output: {output}')
    candidates, rows, errors = scan(root)
    summary = {'schema': 'EXTERNAL_BASELINE_INVENTORY_V1', 'root': str(root),
               'created_utc': datetime.now(timezone.utc).isoformat(),
               'scope': 'Existing local source and small reports; not proof of faithful reproduction or matched evaluation',
               'no_training_or_inference': True, 'source_files_modified': False,
               'weights_and_arrays': 'Paths, sizes and timestamps only; no checkpoint, raw IQ, NPY or HDF5 contents included',
               'selected_top_level': candidates, 'files': rows, 'errors': errors}
    total, count = 0, 0
    with ZipFile(output, 'x', ZIP_DEFLATED, compresslevel=6) as z:
        for row in rows:
            path = root / row['path']
            if row['kind'] != 'file':
                continue
            if path.suffix.lower() not in SMALL_SUFFIXES or row['bytes'] > MAX_FILE:
                continue
            if total + row['bytes'] > MAX_TOTAL:
                row['skip_reason'] = 'Total uncompressed collection limit reached'
                continue
            try:
                before = path.stat()
                data = path.read_bytes()
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(data) != before.st_size:
                    row['skip_reason'] = 'File changed while reading; retry after that job finishes'
                    continue
                if len(data) > MAX_FILE or total + len(data) > MAX_TOTAL:
                    row['skip_reason'] = 'Size limit'
                    continue
                z.writestr('server_files/' + row['path'], data)
                row['included'] = True
                row['sha256'] = hashlib.sha256(data).hexdigest()
                total += len(data)
                count += 1
            except OSError as exc:
                errors.append(f'{path}: {exc}')
        log = root / 'codex_b283_full_ablation.log'
        if log.is_file() and not log.is_symlink():
            with log.open('rb') as f:
                f.seek(max(0, log.stat().st_size - 32768))
                tail = f.read().decode('utf-8', errors='replace').splitlines()[-25:]
            z.writestr('b283_recent_log.txt', '\n'.join(tail) + '\n')
        summary['included_files'] = count
        summary['included_uncompressed_bytes'] = total
        z.writestr('inventory.json', json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
        lines = [f"{x.get('bytes', 0):>12}  {'PACKED' if x['included'] else 'LISTED'}  {x['path']}" for x in rows]
        z.writestr('inventory.txt', '\n'.join(lines) + '\n')
    print('Collection complete; no training or inference started.')
    print('Source root:', root)
    print('Matched top-level items:', len(candidates))
    for candidate in candidates:
        print(' ', candidate['path'])
    print(f'Included small files: {count}; source bytes: {total:,}')
    print(f'Upload this file: {output} ({output.stat().st_size:,} bytes)')
    if errors:
        print('Read warnings:', len(errors), '(see inventory.json)')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output = args.output or args.root / f'EXTERNAL_BASELINE_MINI_{stamp}.zip'
    collect(args.root, output)


if __name__ == '__main__':
    main()
