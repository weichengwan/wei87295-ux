#!/usr/bin/env python3
"""Only the 14 obsolete .npy feature caches seen in the 2026-10-16 inventory.

No directory deletion, glob expansion, checkpoint deletion or data-bank cleanup.
Run without --apply for a preview. Uses the standard library, not NumPy/Conda.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import stat

DEFAULT_ROOT=Path('/root/autodl-tmp/MTDSP_NATIVE_LMDA_V1')
ALLOWLIST=(
    'output_sim_r10_b242_stft_simam_train_v1/stft_base_float32/train_stft_base.npy',
    'output_sim_r10_b242_stft_simam_train_v1/stft_base_float32/val_stft_base.npy',
    'output_sim_r10_b247_clutter_front_train_v1/train_logsp128_f16.npy',
    'output_sim_r10_b269_tdfc_full_finetune_v1/train_wvd128.npy',
    'output_sim_r10_b269_tdfc_full_finetune_v1/val_wvd128.npy',
    'output_sim_r10_b268_tdfc_l1tail_full_v1/train_wvd128.npy',
    'output_sim_r10_b268_tdfc_l1tail_full_v1/val_wvd128.npy',
    'output_sim_r10_b263_l1_early_tf_adapt_v1/train_wvd128.npy',
    'output_sim_r10_b263_l1_early_tf_adapt_v1/val_wvd128.npy',
    'output_sim_r10_b260_l1_internal_adscm_v1/train_wvd128_fp32.npy',
    'output_sim_r10_b249_strip_stage3_train_v1/val_layer3_fp16.npy',
    'output_sim_r10_b248_spatial_ca_train_v1/val_layer4_fp16.npy',
    'output_sim_r10_b238_fsst_corrected_train_v1/fsst_base_float32/val_fsst_base.npy',
    'output_sim_r10_b225_real_four_dl_train_v1/fsst_base_float32/val_fsst_base.npy',
)

def candidate(root,relative):
    p=root/relative
    # Reject symlinks at every path component, including a linked directory.
    for q in [p,*p.parents]:
        if q==root:break
        if q.is_symlink():return None,'symlink skipped'
    if not p.exists():return None,'already absent'
    s=p.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:return None,'not a unique regular file'
    if p.suffix!='.npy' or root not in p.resolve().parents:return None,'outside scope'
    with p.open('rb') as f:
        if f.read(6)!=b'\x93NUMPY':return None,'not a NumPy .npy file'
    return s,None

def open_candidates(paths):
    """Check fd links AND memory mappings; an mmap may outlive its file fd."""
    targets={str(p):[] for p in paths};errors=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            uid=proc.stat().st_uid
            # On non-root test machines, other users' processes are inaccessible.
            # AutoDL is run as root and checks every readable PID.
            if os.geteuid()!=0 and uid!=os.geteuid():continue
            entries=list((proc/'fd').iterdir())
            for fd in entries:
                try:target=os.readlink(fd).removesuffix(' (deleted)')
                except (FileNotFoundError,ProcessLookupError):continue
                if target in targets:targets[target].append(int(proc.name))
            for line in (proc/'maps').read_text(errors='replace').splitlines():
                parts=line.split(None,5)
                if len(parts)==6:
                    target=parts[-1].removesuffix(' (deleted)')
                    if target in targets:targets[target].append(int(proc.name))
        except (FileNotFoundError,ProcessLookupError):continue
        except PermissionError:errors.append(int(proc.name))
    return {p:sorted(set(ids)) for p,ids in targets.items() if ids},errors

def free_bytes(root):
    s=os.statvfs(root);return s.f_bavail*s.f_frsize

def execute(root,apply=False):
    root=Path(root).resolve(strict=True)
    if not root.is_dir():raise RuntimeError('Project root is not a directory')
    records=[];eligible={}
    for relative in ALLOWLIST:
        s,reason=candidate(root,relative)
        row=dict(path=relative,status=reason or 'candidate',bytes=s.st_size if s else 0);records.append(row)
        if s:eligible[root/relative]=(s,row)
    busy,errors=open_candidates(eligible)
    if errors:
        raise RuntimeError('Cannot verify open files for PIDs '+str(errors)+'. No files were deleted; paste this error for review.')
    total=0
    for p,(s,row) in eligible.items():
        if str(p) in busy:row.update(status='IN USE; retained',pids=busy[str(p)])
        else:total+=s.st_size
    print(('APPLY' if apply else 'PREVIEW')+' | root='+str(root))
    print(f'Eligible old caches: {total/1024**3:.3f} GiB; protected data and model files are outside the allowlist.',flush=True)
    before=free_bytes(root)
    if apply:
        # Commit the exact scope before unlinking anything.
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
        audit=root/('legacy_cache_cleanup_'+stamp+'.json')
        report=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(root),free_before=before,records=records)
        audit.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        for p,(old,row) in eligible.items():
            if row['status']!='candidate':continue
            try:
                # Recheck file identity and open-process use immediately before deletion.
                busy_now,errors_now=open_candidates([p])
                if errors_now:row['status']='process check unavailable; retained';continue
                if str(p) in busy_now:row.update(status='IN USE; retained',pids=busy_now[str(p)]);continue
                current,reason=candidate(root,row['path'])
                if reason or (current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns)!=(old.st_dev,old.st_ino,old.st_size,old.st_mtime_ns):
                    row['status']='changed during check; retained';continue
                p.unlink();row['status']='deleted'
            except OSError as exc:row['status']='retained: '+str(exc)
            finally:
                report['free_after']=free_bytes(root);audit.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print('Audit: '+str(audit))
    for row in records:
        if row['status']!='already absent':print(f'{row["status"]}: {row["bytes"]/1024**3:.3f} GiB  {row["path"]}')
    after=free_bytes(root)
    print(f'Free space now: {after/1024**3:.3f} GiB; net change: {(after-before)/1024**3:+.3f} GiB',flush=True)
    return records

def main():
    p=argparse.ArgumentParser(description=__doc__)
    # Literal root: downloading this file into /tmp is supported.
    p.add_argument('--root',type=Path,default=DEFAULT_ROOT);p.add_argument('--apply',action='store_true')
    a=p.parse_args();execute(a.root,a.apply)

if __name__=='__main__':main()
