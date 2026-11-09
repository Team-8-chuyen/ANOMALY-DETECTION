from __future__ import annotations
import argparse
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from itd.data.load_cert import build_canonical_events, load_bucket
from itd.data.ldap import load_ldap_snapshots, role_days_asof
from itd.data.labels import build_user_day_labels
from itd.features.contexts import add_past_only_pc_context
from itd.features.count_features import build_behaviour_features, FEATURE_NAMES
from itd.features.sequence_tokens import build_sequence_fields, compress_runs, sequence_length_stats
from itd.utils.config import load_config
from itd.utils.io import atomic_json, write_parquet
from itd.utils.checkpoint import BucketCheckpoint, ProcessLock
from itd.features.user_worker import process_user


def _canonical_ready(cfg)->bool:
    manifest=cfg.root/"data/artifacts/manifests/prepare_data.json"
    root=cfg.paths.interim/"canonical_events"
    if not manifest.is_file() or not root.is_dir(): return False
    try:
        import json
        raw=json.loads(manifest.read_text(encoding="utf-8"))
        return all(int(raw.get("sources",{}).get(s,{}).get("rows",0))>0 and (root/f"source={s}").is_dir() for s in ("logon","device","file","http","email"))
    except (OSError,ValueError,TypeError): return False


def _bucket_outputs(cfg,bucket:int,ocean_enabled:bool)->list[Path]:
    outputs=[cfg.paths.processed/"user_day_features"/f"bucket-{bucket:03d}.parquet",cfg.paths.processed/"user_day_sequences"/f"bucket-{bucket:03d}.parquet"]
    if ocean_enabled: outputs.append(cfg.paths.processed/"user_day_features_ocean"/f"bucket-{bucket:03d}.parquet")
    return outputs


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description="Prepare CERT r4.2 for Behaviour and Sequence branches")
    parser.add_argument("--config",default="configs/base.yaml"); parser.add_argument("--force",action="store_true"); parser.add_argument("--resume",action="store_true"); parser.add_argument("--canonical-only",action="store_true")
    args=parser.parse_args(argv); cfg=load_config(ROOT/args.config if not Path(args.config).is_absolute() else args.config)
    if args.force and args.resume: parser.error("--force and --resume are mutually exclusive")
    lock_path=cfg.root/"data/artifacts/manifests/prepare_data.lock"
    with ProcessLock(lock_path):
        return _run(args,cfg)


def _run(args,cfg)->int:
    if args.force:
        for target in (cfg.paths.interim/"canonical_events",cfg.paths.processed/"user_day_features",cfg.paths.processed/"user_day_sequences",cfg.paths.processed/"user_day_features_ocean"):
            if target.exists(): shutil.rmtree(target)
        checkpoint_path=cfg.root/"data/artifacts/manifests/feature_checkpoint.json"
        checkpoint_path.unlink(missing_ok=True)
    if args.resume and _canonical_ready(cfg):
        import json
        manifest=json.loads((cfg.root/"data/artifacts/manifests/prepare_data.json").read_text(encoding="utf-8"))
        print("[resume] Canonical events complete; skipping 32.7M-event CSV conversion.",flush=True)
    else:
        print("[canonical] Converting five raw CSV sources...",flush=True)
        manifest=build_canonical_events(cfg,args.force)
    if args.canonical_only: return 0
    ldap=load_ldap_snapshots(cfg.paths.raw/"LDAP")
    all_stats=[]; all_labels=[]
    ocean_path=cfg.paths.raw/"psychometric.csv"; ocean=pd.read_csv(ocean_path,dtype={"user_id":str}) if ocean_path.exists() else pd.DataFrame()
    checkpoint=BucketCheckpoint.load(cfg.root/"data/artifacts/manifests/feature_checkpoint.json")
    started=time.monotonic(); done_at_start=len(checkpoint.completed) if args.resume else 0
    for bucket in range(cfg.data.user_buckets):
        required=_bucket_outputs(cfg,bucket,not ocean.empty)
        if args.resume and checkpoint.is_complete(bucket,required):
            print(f"[resume] bucket {bucket:03d}/{cfg.data.user_buckets-1:03d} already complete; skipped.",flush=True)
            continue
        bucket_started=time.monotonic()
        print(f"[features] bucket {bucket:03d}/{cfg.data.user_buckets-1:03d} started.",flush=True)
        events=load_bucket(cfg.paths.interim,bucket)
        if events.empty:
            checkpoint.mark_complete(bucket)
            print(f"[features] bucket {bucket:03d} empty; checkpoint saved.",flush=True)
            continue
        events=add_past_only_pc_context(events,cfg.features.pc_history_days,cfg.features.own_pc_min_days)
        part_root=cfg.paths.processed/".user_checkpoints"/f"bucket-{bucket:03d}"
        users=sorted(events.user.astype(str).unique()); futures={}
        # Windows processes bypass the Python GIL; cap at three to protect RAM.
        with ProcessPoolExecutor(max_workers=min(3,len(users))) as pool:
            for user in users:
                safe=user.replace("/","_").replace("\\","_")
                futures[pool.submit(process_user,events[events.user.astype(str).eq(user)].copy(),ldap,cfg,part_root/"features"/f"{safe}.parquet",part_root/"sequences"/f"{safe}.parquet")]=user
            completed_users=0
            for future in as_completed(futures):
                user=futures[future]; state=future.result(); completed_users+=1
                print(f"[user-checkpoint] bucket {bucket:03d}: {completed_users}/{len(users)} users ({user}, {state}).",flush=True)
        feature_parts=sorted((part_root/"features").glob("*.parquet")); sequence_parts=sorted((part_root/"sequences").glob("*.parquet"))
        if len(feature_parts)!=len(users) or len(sequence_parts)!=len(users): raise RuntimeError(f"Incomplete user checkpoints for bucket {bucket}")
        features=pd.concat((pd.read_parquet(p) for p in feature_parts),ignore_index=True)
        write_parquet(features,cfg.paths.processed/"user_day_features"/f"bucket-{bucket:03d}.parquet")
        if not ocean.empty:
            ab=features.merge(ocean[["user_id","O","C","E","A","N"]],left_on="user",right_on="user_id",how="left").drop(columns="user_id")
            write_parquet(ab,cfg.paths.processed/"user_day_features_ocean"/f"bucket-{bucket:03d}.parquet")
        seq=pd.concat((pd.read_parquet(p) for p in sequence_parts),ignore_index=True)
        write_parquet(seq,cfg.paths.processed/"user_day_sequences"/f"bucket-{bucket:03d}.parquet")
        # Per-user workers already compressed the sequence. Re-compressing the
        # full bucket here was redundant and dominated runtime.
        all_stats.append(sequence_length_stats(events,seq))
        labels=build_user_day_labels(cfg.paths.raw/"answers",events)
        if labels.available:
            all_labels.append(labels.frame)
        checkpoint.mark_complete(bucket)
        completed=len(checkpoint.completed); elapsed=time.monotonic()-started
        newly_done=max(1,completed-done_at_start); eta=(elapsed/newly_done)*(cfg.data.user_buckets-completed)
        print(f"[checkpoint] bucket {bucket:03d} complete in {time.monotonic()-bucket_started:.1f}s; {completed}/{cfg.data.user_buckets}; ETA {eta/60:.1f} min.",flush=True)
    atomic_json(cfg.root/"data/artifacts/reports/sequence_length_stats.json",{"buckets":all_stats,"max_len_selected":False})
    if all_labels:
        write_parquet(pd.concat(all_labels,ignore_index=True),cfg.paths.processed/"labels"/"user_day_labels.parquet")
    manifest["labels_available"]=bool(all_labels); manifest["feature_count"]=len(FEATURE_NAMES); manifest["sequence_fields"]=24
    atomic_json(cfg.root/"data/artifacts/manifests/prepare_data.json",manifest)
    return 0

if __name__=="__main__": raise SystemExit(main())
