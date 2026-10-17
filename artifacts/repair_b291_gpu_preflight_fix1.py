"""Repair only B291 V1's pre-training CPU/CUDA comparison; reuse replay pool.

No trained checkpoint identity is rewritten. The original run must have stopped
before creating preflight.json or any candidate/scoring artifacts.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path

OLD='8bac1e156e03ed550920fd0722378aa20b171ccd9f9543348be182f565487bf8'
NEW='159f8cc1857aebb33d51cba45d7042ba7e2a1bc5880cbf5c039e5d62c19ae373'
OLD_LINE="    need(any(not torch.equal(v,model.refiner.guide.state_dict()[k]) for k,v in before.items()),'Guide never updated')"
NEW_LINES="    after=snapshot(model.refiner.guide)\n    need(any(not torch.equal(v,after[k]) for k,v in before.items()),'Guide never updated')"

def need(v,msg):
    if not bool(v):raise RuntimeError('B291 FIX1 STOP: '+msg)
def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def readj(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def json_bytes(v):return (json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def fingerprint(v):return sha_bytes(json.dumps(v,sort_keys=True,allow_nan=False).encode())
def atomic(path,data):
    path=Path(path);tmp=path.with_name(path.name+'.fix1.tmp');tmp.write_bytes(data);tmp.replace(path)

def code_files(package):
    paths=sorted(package.glob('*.py'))+sorted((package/'frozen_source').glob('*.py'))
    paths+=[package/n for n in ['frozen_sources.json','expected_source_code.json','paper_contract.json','expected_ours_code.json']]
    need(not any(p.is_symlink() for p in paths),'Package contains symlinked code')
    return {p.relative_to(package).as_posix():sha(p) for p in paths}

def process_running(root):
    pidpath=root/'codex_b291_tchr_full.pid'
    if not pidpath.is_file():return False
    try:
        pid=int(pidpath.read_text().strip());proc=Path('/proc')/str(pid)
        cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace').lower()
        state=(proc/'stat').read_text().split(')',1)[1].split()[0]
        return state!='Z' and 'b291' in cmd
    except (OSError,ValueError,IndexError):return False

def repair(root):
    root=Path(root).resolve();package=root/'B291_TCHR_FULL_V1';out=root/'output_b291_tchr_full_v1'
    need(package.is_dir() and out.is_dir(),'Missing original B291 package or output directory')
    need(not package.is_symlink() and not out.is_symlink(),'Package/output must not be symlinks')
    need(not process_running(root),'B291 is still running; do not modify active experiment code')
    for name in ('conservative','tail_focused','pd_scr_full'):
        folder=out/name
        need(not folder.exists() or (folder.is_dir() and not any(folder.iterdir())),
            'Training/scoring artifacts already exist; preserve them and inspect rather than rewriting their identity')
    need(not (out/'preflight.json').exists(),'Preflight already completed; this narrowly scoped recovery must not alter a trained run')
    path=package/'b291_train.py';manifest=out/'run_manifest.json';sums=package/'SHA256SUMS'
    need(not any(p.is_symlink() for p in (path,manifest,sums)),'Repair input is a symlink')
    value=readj(manifest)
    need(value.get('version')=='B291_TCHR_FULL_V1' and value.get('only_method')=='ADN + TFSE + TCHR','Not the expected B291 run')
    actual=code_files(package);recorded=value['code_sha256']
    need(set(actual)==set(recorded),'Code file list differs from original run')
    need(actual['b291_train.py'] in (OLD,NEW) and recorded['b291_train.py'] in (OLD,NEW),'Unsupported source revision; no generic hash bypass')
    need(all(actual[k]==recorded[k] for k in actual if k!='b291_train.py'),'Another source file changed; no identity rewrite performed')
    data=path.read_bytes();text=data.decode('utf-8')
    if sha_bytes(data)==OLD:
        need(text.count(OLD_LINE)==1,'Expected faulty comparison absent')
        patched=text.replace(OLD_LINE,NEW_LINES).encode()
    else:patched=data
    need(sha_bytes(patched)==NEW,'Fixed source checksum differs')
    lines=sums.read_text(encoding='utf-8').splitlines();entries=[]
    for i,line in enumerate(lines):
        parts=line.split('  ',1)
        if len(parts)==2 and parts[1]=='b291_train.py':entries.append((i,parts[0]))
    need(len(entries)==1 and entries[0][1] in (OLD,NEW),'Unexpected SHA256SUMS entry')
    lines[entries[0][0]]=NEW+'  b291_train.py'
    pool=out/'train_only_replay';protected={}
    if pool.exists():
        need(not pool.is_symlink() and not any(p.is_symlink() for p in pool.rglob('*')),'Replay cache contains symlinks')
        protected={str(p):sha(p) for p in pool.rglob('*') if p.is_file()}
        cp=pool/'contract.json'
        if cp.exists():
            ct=readj(cp);need(ct['identity']['split']=='train_h0_b291' and fingerprint(ct['identity'])==ct['fingerprint'],'Replay contract differs')
            need(sha(pool/'retained.npz')==ct['cache_sha256'],'Retained replay pool checksum differs')
    target=dict(value);target['code_sha256']=dict(recorded);target['code_sha256']['b291_train.py']=NEW
    if actual['b291_train.py']==NEW and recorded['b291_train.py']==NEW and entries[0][1]==NEW:
        print('B291 FIX1 already applied; replay pool unchanged. Restart the original startup script.',flush=True);return
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    backup=package/'repair_backups'/stamp;backup.mkdir(parents=True)
    for old in (path,manifest,sums):(backup/old.name).write_bytes(old.read_bytes())
    journal=dict(repair='B291_GPU_PREFLIGHT_FIX1',reason='Compare two CPU snapshots, retaining the actual guide-update assertion',
        old_train_sha256=actual['b291_train.py'],new_train_sha256=NEW,
        before_manifest_sha256=sha(manifest),after_manifest_sha256=sha_bytes(json_bytes(target)),
        backup_dir=str(backup),replay_files_sha256=protected,training_or_score_identity_rewritten=False,
        migration_scope='Only root pre-training run_manifest code hash; candidate/score folders absent',
        model_loss_hyperparameters_changed=False)
    atomic(backup/'repair_plan.json',json_bytes(journal))
    atomic(path,patched);atomic(sums,('\n'.join(lines)+'\n').encode());atomic(manifest,json_bytes(target))
    need(sha(path)==NEW and readj(manifest)==target,'Repair verification failed')
    need(all(sha(p)==h for p,h in protected.items()),'Replay cache changed during repair')
    journal['status']='PASS_B291_GPU_PREFLIGHT_FIX1';atomic(out/'gpu_preflight_fix1.json',json_bytes(journal))
    print('PASS_B291_GPU_PREFLIGHT_FIX1',flush=True)
    print('Only the preflight tensor comparison and its code identity were repaired.',flush=True)
    print('Replay pool preserved: '+str(len(protected))+' files. The 200,000 proposals will not be rescored.',flush=True)
    print('Backup: '+str(backup),flush=True)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/root/autodl-tmp/MTDSP_NATIVE_LMDA_V1'))
    a=p.parse_args(argv)
    with (a.root/'codex_b291_fix1.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);repair(a.root)

if __name__=='__main__':main()
