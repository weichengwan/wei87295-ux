"""Launch full B295/B296, safely replacing an already queued medium job only."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

PACKAGE='B295_B296_TAIL_MODULES_V1'

def process(pid):
    try:
        p=Path('/proc')/str(pid);fields=(p/'stat').read_text().rsplit(')',1)[1].split()
        if fields[0]=='Z':return None
        argv=[v.decode(errors='replace') for v in (p/'cmdline').read_bytes().split(b'\0') if v]
        return dict(pid=int(pid),start=fields[19],argv=argv,cwd=p.joinpath('cwd').resolve())
    except (OSError,ValueError,IndexError):return None

def targets(root):
    expected={(root/PACKAGE/name).resolve() for name in ('run_tails.py','run_b295_b296.sh')}
    rows=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        item=process(int(path.name))
        if not item:continue
        if any((item['cwd']/arg).resolve() in expected for arg in item['argv']
               if Path(arg).name in ('run_tails.py','run_b295_b296.sh')):
            rows.append(item)
    return rows

def trained(root):
    try:
        for arm in ('HGNL_tail','MDFG_tail'):
            folder=root/'output_b295_b296_tails_v1'/arm
            c=json.loads((folder/'training_contract.json').read_text())
            if c['status']!='PASS_B295_B296_TAIL_TRAIN_VAL_ONLY' or c['best_epoch']<1 or c['source_fallback']:return False
            if not (folder/'best.pt').is_file():return False
        return True
    except (OSError,ValueError,KeyError):return False

def same(p):
    q=process(p['pid']);return bool(q and q['start']==p['start'])

def terminate_own_medium(root,rows):
    # Start-tick and exact package path checks exclude B293 and unrelated Python jobs.
    live={p['pid']:p for p in targets(root)}
    for old in rows:
        now=live.get(old['pid'])
        if now and now['start']==old['start']:
            if '--full' in now['argv']:raise RuntimeError('Full-profile job appeared; no further process was stopped')
            try:
                if hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'):
                    fd=os.pidfd_open(now['pid'])
                    try:
                        if same(now):signal.pidfd_send_signal(fd,signal.SIGTERM)
                    finally:os.close(fd)
                elif same(now):os.kill(now['pid'],signal.SIGTERM)
            except ProcessLookupError:pass
    deadline=time.monotonic()+20
    while any(same(p) for p in rows):
        if time.monotonic()>=deadline:raise RuntimeError('Old B295/B296 did not exit; no duplicate job started')
        time.sleep(.2)
    # A conda wrapper may have spawned its child between snapshot and TERM.
    remaining=targets(root)
    if remaining:raise RuntimeError('B295/B296 process still exists; no duplicate full job started. Run this helper again.')

def worker(root,conda,interval=5):
    lock_path=root/'codex_b295_b296_start.lock'
    with lock_path.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another B295/B296 starter/switcher is active; no duplicate job launched.',flush=True);return
        while True:
            rows=targets(root)
            if any('--full' in r['argv'] for r in rows):
                print('B295/B296 full profile is already active or queued. Keeping it unchanged.',flush=True);return
            if not rows:break
            manifest=root/'output_b295_b296_tails_v1/run_manifest.json'
            # If training/cache extraction already started, let it commit both checkpoints first.
            # Fresh queued jobs can be switched immediately without touching cache files.
            if trained(root) or not manifest.exists():
                print('Switching only the existing B295/B296 medium job to FULL; B293 is untouched.',flush=True)
                terminate_own_medium(root,rows);break
            print('Existing B295/B296 training is active. Letting both tails finish before replacing medium scoring with FULL.',flush=True)
            time.sleep(interval)
        log=root/'codex_b295_b296_tails.log';script=root/PACKAGE/'run_b295_b296.sh'
        with log.open('ab',buffering=0) as output:
            output.write((datetime.datetime.now().astimezone().isoformat()+' FULL profile requested: CAL3M/AUDIT1M, H1 1024x37, Pfa1e-4 and1e-5\n').encode())
            job=subprocess.Popen(['nohup',str(conda),'run','--no-capture-output','-n','mpdnet-r10',
                'bash',str(script),'--wait-for-gpu','--full'],stdin=subprocess.DEVNULL,stdout=output,
                stderr=subprocess.STDOUT,start_new_session=True,close_fds=True,cwd=root)
        path=root/'codex_b295_b296_tails.pid';temp=path.with_suffix('.pid.tmp')
        temp.write_text(str(job.pid)+'\n');temp.replace(path)
        print(f'FULL B295/B296 queued: PID={job.pid}; log={log}; original checkpoints/medium results preserved.',flush=True)
        return job

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('/root/autodl-tmp/MTDSP_NATIVE_LMDA_V1'))
    parser.add_argument('--conda',type=Path)
    parser.add_argument('--worker',action='store_true')
    a=parser.parse_args();root=a.root.resolve()
    if not (root/PACKAGE/'run_b295_b296.sh').is_file():
        raise RuntimeError('First extract B295_B296_TAIL_MODULES_V1.zip in '+str(root))
    conda=a.conda or Path('/root/miniconda3/bin/conda')
    if not conda.is_file():conda=Path(shutil.which('conda') or '/nonexistent-conda')
    if not conda.is_file() or not os.access(conda,os.X_OK):raise RuntimeError('Conda executable unavailable')
    conda=conda.resolve()
    if a.worker:worker(root,conda);return
    log=root/'codex_b295_b296_full_switch.log'
    with log.open('ab',buffering=0) as output:
        job=subprocess.Popen(['nohup',sys_executable(),str(Path(__file__).resolve()),'--worker',
            '--root',str(root),'--conda',str(conda)],stdin=subprocess.DEVNULL,stdout=output,
            stderr=subprocess.STDOUT,start_new_session=True,close_fds=True,cwd=root)
    print(f'FULL switcher running in background: PID={job.pid}; log={log}',flush=True)
    print('B293 continues. Existing tail training is preserved; medium scoring is skipped/replaced.',flush=True)

def sys_executable():
    import sys
    return sys.executable

if __name__=='__main__':main()
