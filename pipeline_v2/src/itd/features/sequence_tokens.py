"""Sequence fields and run compression (SPEC-001 §4.5–4.6)."""
from __future__ import annotations

import json
import numpy as np
import pandas as pd
import polars as pl

SEQUENCE_FIELDS = ["event_token","time_sin","time_cos","gap_log1p","gap_bucket","calendar_context","pc_context","run_count_log1p","run_span_log1p","file_extension_id","filename_length_log1p","extension_present","multi_dot","url_scheme_id","hostname_length_log1p","url_length_log1p","path_depth_log1p","query_present","recipient_count_log1p","external_recipient_ratio","bcc_present","attachment_count_log1p","email_size_log1p","sender_context"]
assert len(SEQUENCE_FIELDS)==24


def compress_runs(events: pd.DataFrame, gap_minutes: float = 5.0) -> pd.DataFrame:
    g=events.sort_values(["user","day","timestamp","event_id"],kind="stable").copy()
    prev_gap=g.groupby(["user","day"])["timestamp"].diff().dt.total_seconds().div(60)
    same=g["event_token"].eq(g.groupby(["user","day"])["event_token"].shift()) & g["pc"].fillna("").eq(g.groupby(["user","day"])["pc"].shift().fillna(""))
    g["run_id"]=(~(same & prev_gap.le(gap_minutes))).groupby([g.user,g.day]).cumsum()
    rows=[]
    for (_,_,_),part in g.groupby(["user","day","run_id"],sort=True):
        row=part.iloc[0].copy(); row["run_count"]=len(part); row["run_span_minutes"]=(part.timestamp.iloc[-1]-part.timestamp.iloc[0]).total_seconds()/60
        if "email_size" in part: row["email_size"]=part.email_size.fillna(0).sum()
        if "recipient_count" in part: row["recipient_count"]=part.recipient_count.fillna(0).sum()
        if "attachment_count" in part: row["attachment_count"]=part.attachment_count.fillna(0).sum()
        rows.append(row)
    return pd.DataFrame(rows).drop(columns=["run_id"],errors="ignore")


def build_sequence_fields(events: pd.DataFrame, gap_buckets=(0,1,5,15,60,240), run_gap_minutes: float=5.0) -> pd.DataFrame:
    g=compress_runs(events,run_gap_minutes).sort_values(["user","day","timestamp","event_id"],kind="stable").reset_index(drop=True)
    minute=g.timestamp.dt.hour*60+g.timestamp.dt.minute
    gap=g.groupby(["user","day"]).timestamp.diff().dt.total_seconds().div(60)
    out=g[["user","day"]].copy(); out["event_index"]=out.groupby(["user","day"]).cumcount()
    out["event_token"]=g.event_token; out["time_sin"]=np.sin(2*np.pi*minute/1440); out["time_cos"]=np.cos(2*np.pi*minute/1440)
    out["gap_log1p"]=np.log1p(gap.fillna(0).clip(lower=0)); out["gap_bucket"]=np.digitize(gap.fillna(0),gap_buckets,right=True)
    out["calendar_context"]=g.calendar_context; out["pc_context"]=g.pc_context
    out["run_count_log1p"]=np.log1p(g.run_count); out["run_span_log1p"]=np.log1p(g.run_span_minutes.clip(lower=0))
    is_file=g.source.eq("file"); is_http=g.source.eq("http"); is_email=g.source.eq("email")
    out["file_extension_id"]=g.get("file_extension","").fillna("") if isinstance(g.get("file_extension",""),pd.Series) else ""
    out["filename_length_log1p"]=np.where(is_file,np.log1p(pd.to_numeric(g.get("filename_length",0),errors="coerce").fillna(0)),0)
    out["extension_present"]=is_file & out.file_extension_id.ne(""); out["multi_dot"]=is_file & g.get("multi_dot",False).fillna(False)
    out["url_scheme_id"]=g.get("url_scheme","").fillna("") if isinstance(g.get("url_scheme",""),pd.Series) else ""
    for target,source in (("hostname_length_log1p","hostname_length"),("url_length_log1p","url_length"),("path_depth_log1p","path_depth")):
        out[target]=np.where(is_http,np.log1p(pd.to_numeric(g.get(source,0),errors="coerce").fillna(0)),0)
    out["query_present"]=is_http & g.get("query_present",False).fillna(False)
    rc=pd.to_numeric(g.get("recipient_count",0),errors="coerce").fillna(0); ec=pd.to_numeric(g.get("external_count",0),errors="coerce").fillna(0)
    out["recipient_count_log1p"]=np.where(is_email,np.log1p(rc),0); out["external_recipient_ratio"]=np.where(is_email & rc.gt(0),ec/rc.replace(0,np.nan),0)
    out["bcc_present"]=is_email & pd.to_numeric(g.get("bcc_count",0),errors="coerce").fillna(0).gt(0)
    out["attachment_count_log1p"]=np.where(is_email,np.log1p(pd.to_numeric(g.get("attachment_count",0),errors="coerce").fillna(0)),0)
    out["email_size_log1p"]=np.where(is_email,np.log1p(pd.to_numeric(g.get("email_size",0),errors="coerce").fillna(0)),0)
    out["sender_context"]=np.where(is_email,g.get("sender_context","MISSING"),"MISSING")
    masks=[]
    common=set(range(9)); file_idx=set(range(9,13)); http_idx=set(range(13,18)); email_idx=set(range(18,24))
    for source in g.source:
        active=common | ({"file":file_idx,"http":http_idx,"email":email_idx}.get(source,set()))
        masks.append(json.dumps([i in active for i in range(24)],separators=(",",":")))
    out["attribute_mask"]=masks
    return out[["user","day","event_index"]+SEQUENCE_FIELDS+["attribute_mask"]]


def build_sequence_fields_polars(events: pd.DataFrame, gap_buckets=(0,1,5,15,60,240), run_gap_minutes: float=5.0) -> pd.DataFrame:
    """Vectorized equivalent of sequence construction for the fast engine."""
    df=pl.from_pandas(events).sort(["user","day","timestamp","event_id"])
    keys=["user","day"]
    df=df.with_columns(
        ((pl.col("timestamp").diff().over(keys).dt.total_seconds()/60).fill_null(0)).alias("_gap"),
        pl.col("event_token").shift(1).over(keys).alias("_prev_token"),
        pl.col("pc").fill_null("").shift(1).over(keys).alias("_prev_pc"),
    ).with_columns(
        ((pl.col("event_token")!=pl.col("_prev_token")) | (pl.col("pc").fill_null("")!=pl.col("_prev_pc")) | (pl.col("_gap")>run_gap_minutes) | pl.col("_prev_token").is_null()).cast(pl.Int64).cum_sum().over(keys).alias("_run")
    )
    first_cols=[c for c in df.columns if c not in set(keys)|{"_gap","_prev_token","_prev_pc","_run","email_size","recipient_count","attachment_count"}]
    agg=[pl.col(c).first().alias(c) for c in first_cols]
    for c in ("email_size","recipient_count","attachment_count"):
        if c in df.columns: agg.append(pl.col(c).fill_null(0).sum().alias(c))
    runs=df.group_by(keys+["_run"],maintain_order=True).agg(agg+[pl.len().alias("run_count"),((pl.col("timestamp").max()-pl.col("timestamp").min()).dt.total_seconds()/60).alias("run_span_minutes")]).sort(keys+["timestamp"])
    # The final 24-field mapping is shared with the verified Pandas mapper;
    # only expensive run discovery/aggregation is delegated to Polars.
    compressed=runs.drop("_run").to_pandas()
    compressed["run_id"]=np.arange(len(compressed))
    # Mark rows as already compressed so the mapper does not merge them again.
    return _map_compressed_sequence(compressed,gap_buckets)


def _map_compressed_sequence(g: pd.DataFrame, gap_buckets) -> pd.DataFrame:
    g=g.sort_values(["user","day","timestamp","event_id"],kind="stable").reset_index(drop=True)
    minute=g.timestamp.dt.hour*60+g.timestamp.dt.minute; gap=g.groupby(["user","day"]).timestamp.diff().dt.total_seconds().div(60)
    out=g[["user","day"]].copy(); out["event_index"]=out.groupby(["user","day"]).cumcount()
    out["event_token"]=g.event_token; out["time_sin"]=np.sin(2*np.pi*minute/1440); out["time_cos"]=np.cos(2*np.pi*minute/1440); out["gap_log1p"]=np.log1p(gap.fillna(0).clip(lower=0)); out["gap_bucket"]=np.digitize(gap.fillna(0),gap_buckets,right=True)
    out["calendar_context"]=g.calendar_context; out["pc_context"]=g.pc_context; out["run_count_log1p"]=np.log1p(g.run_count); out["run_span_log1p"]=np.log1p(g.run_span_minutes.clip(lower=0))
    is_file=g.source.eq("file"); is_http=g.source.eq("http"); is_email=g.source.eq("email")
    out["file_extension_id"]=g.file_extension.fillna(""); out["filename_length_log1p"]=np.where(is_file,np.log1p(g.filename_length.fillna(0)),0); out["extension_present"]=is_file & out.file_extension_id.ne(""); out["multi_dot"]=is_file & g.multi_dot.fillna(False)
    out["url_scheme_id"]=g.url_scheme.fillna(""); out["hostname_length_log1p"]=np.where(is_http,np.log1p(g.hostname_length.fillna(0)),0); out["url_length_log1p"]=np.where(is_http,np.log1p(g.url_length.fillna(0)),0); out["path_depth_log1p"]=np.where(is_http,np.log1p(g.path_depth.fillna(0)),0); out["query_present"]=is_http & g.query_present.fillna(False)
    rc=g.recipient_count.fillna(0); ec=g.external_count.fillna(0); out["recipient_count_log1p"]=np.where(is_email,np.log1p(rc),0); out["external_recipient_ratio"]=np.where(is_email & rc.gt(0),ec/rc.replace(0,np.nan),0); out["bcc_present"]=is_email & g.bcc_count.fillna(0).gt(0); out["attachment_count_log1p"]=np.where(is_email,np.log1p(g.attachment_count.fillna(0)),0); out["email_size_log1p"]=np.where(is_email,np.log1p(g.email_size.fillna(0)),0); out["sender_context"]=np.where(is_email,g.sender_context,"MISSING")
    common=set(range(9)); groups={"file":set(range(9,13)),"http":set(range(13,18)),"email":set(range(18,24))}; out["attribute_mask"]=[json.dumps([i in common|groups.get(s,set()) for i in range(24)],separators=(",",":")) for s in g.source]
    return out[["user","day","event_index"]+SEQUENCE_FIELDS+["attribute_mask"]]


def sequence_length_stats(before: pd.DataFrame, after: pd.DataFrame) -> dict:
    quantiles=[.5,.75,.9,.95,.99,.995,1.0]
    result={}
    for name,frame in (("before",before),("after",after)):
        lengths=frame.groupby(["user","day"]).size()
        result[name]={str(q):float(lengths.quantile(q)) for q in quantiles} if len(lengths) else {}
    return result
