"""Exactly 100 interpretable user-day features (SPEC-001 §4.3)."""
from __future__ import annotations

import math
from collections import Counter, deque
from typing import Iterable

import numpy as np
import pandas as pd

LOGON = ["logon_count","logoff_count","distinct_logon_pc_count","own_pc_logon_count","shared_pc_logon_count","foreign_pc_logon_count","foreign_pc_logon_ratio","weekend_logon_count","first_logon_time_deviation","last_logoff_time_deviation","work_span_minutes","matched_session_count","total_session_minutes","max_session_minutes","unmatched_logon_count","unmatched_logoff_count"]
DEVICE = ["connect_count","disconnect_count","device_session_count","unmatched_connect_count","unmatched_disconnect_count","device_active_minutes_total","device_session_minutes_mean","device_session_minutes_max","device_distinct_pc_count","own_pc_connect_count","shared_pc_connect_count","foreign_pc_connect_count","foreign_pc_connect_ratio","weekend_connect_count","connect_time_deviation_mean","connect_time_deviation_max"]
FILE = ["file_event_count","distinct_filename_count","distinct_extension_count","extension_entropy","repeated_filename_count","repeated_extension_count","filename_length_mean","filename_length_std","filename_length_max","extension_present_ratio","extensionless_file_count","multi_dot_filename_count","distinct_file_pc_count","foreign_pc_file_ratio","file_time_deviation_mean","file_burst_count_5m"]
HTTP = ["http_request_count","distinct_url_count","distinct_hostname_count","distinct_path_count","distinct_scheme_count","https_request_ratio","query_present_ratio","distinct_query_key_count","repeated_url_count","repeated_hostname_count","hostname_length_mean","hostname_length_max","url_length_mean","url_length_max","path_depth_mean","new_hostname_count_30d"]
EMAIL = ["email_sent_count","recipient_total_count","unique_recipient_count","external_recipient_total","external_recipient_ratio","external_recipient_email_count","to_total","cc_total","bcc_total","bcc_email_count","attachment_email_count","attachment_total_count","email_size_mean","email_size_max","personal_from_email_count","new_external_recipient_count_30d"]
CROSS = ["total_event_count","active_source_count","weekend_event_ratio","own_pc_event_ratio","shared_pc_event_ratio","foreign_pc_event_ratio","distinct_all_pc_count","source_transition_count","source_transition_entropy","multi_source_burst_count_5m","inter_event_gap_mean_minutes","inter_event_gap_p95_minutes"]
HISTORY = ["active_days_last_7","active_days_last_30","total_events_mean_7d","total_events_mean_30d","total_events_std_30d","short_long_activity_ratio","days_since_last_active_day","days_in_current_role"]
FEATURE_NAMES = LOGON + DEVICE + FILE + HTTP + EMAIL + CROSS + HISTORY
assert len(FEATURE_NAMES) == 100 and len(set(FEATURE_NAMES)) == 100


def _ratio(a: float, b: float) -> float:
    return float(a / b) if b else 0.0


def _entropy(values: Iterable[str]) -> float:
    counts = Counter(v for v in values if str(v))
    n = sum(counts.values())
    return -sum((c/n) * math.log(c/n) for c in counts.values()) if n else 0.0


def _repeats(values: Iterable[str]) -> int:
    return sum(max(c - 1, 0) for c in Counter(v for v in values if str(v)).values())


def _minutes(ts: pd.Series) -> np.ndarray:
    return (ts.dt.hour * 60 + ts.dt.minute).to_numpy(dtype=float)


def _circular_distance(values: np.ndarray, baseline: float) -> np.ndarray:
    diff=np.abs(values-baseline)
    return np.minimum(diff,1440-diff)


def _burst_count(g: pd.DataFrame, require_multi_source: bool = False) -> int:
    if len(g) < 2: return 0
    g = g.sort_values("timestamp")
    gaps = g["timestamp"].diff().dt.total_seconds().div(60).fillna(np.inf).to_numpy()
    starts = np.where(gaps > 5)[0].tolist() + [len(g)]
    begin, total = 0, 0
    for end in starts:
        part = g.iloc[begin:end]
        if len(part) >= 2 and (not require_multi_source or part["source"].nunique() >= 2): total += 1
        begin = end
    return total


def _pair_sessions(g: pd.DataFrame, open_token: str, close_token: str) -> tuple[list[float], int, int]:
    queues: dict[str, list[pd.Timestamp]] = {}
    durations, unmatched_close = [], 0
    for row in g.sort_values("timestamp").itertuples():
        if row.event_token == open_token:
            queues.setdefault(row.pc, []).append(row.timestamp)
        elif row.event_token == close_token:
            q = queues.get(row.pc, [])
            if q: durations.append((row.timestamp - q.pop(0)).total_seconds()/60)
            else: unmatched_close += 1
    return durations, sum(map(len, queues.values())), unmatched_close


def _base_row(g: pd.DataFrame) -> dict[str, float]:
    r = {name: 0.0 for name in FEATURE_NAMES}
    lo, lf = g[g.event_token=="LOGON"], g[g.event_token=="LOGOFF"]
    ld = pd.concat([lo, lf])
    dur, uo, uc = _pair_sessions(ld, "LOGON", "LOGOFF")
    r.update(logon_count=len(lo), logoff_count=len(lf), distinct_logon_pc_count=lo.pc.nunique(), own_pc_logon_count=(lo.pc_context=="OWN").sum(), shared_pc_logon_count=(lo.pc_context=="SHARED").sum(), foreign_pc_logon_count=(lo.pc_context=="FOREIGN").sum(), foreign_pc_logon_ratio=_ratio((lo.pc_context=="FOREIGN").sum(),len(lo)), weekend_logon_count=(lo.calendar_context=="WEEKEND").sum(), work_span_minutes=((lf.timestamp.max()-lo.timestamp.min()).total_seconds()/60 if len(lo) and len(lf) else 0), matched_session_count=len(dur), total_session_minutes=sum(dur), max_session_minutes=max(dur,default=0), unmatched_logon_count=uo, unmatched_logoff_count=uc)
    dv = g[g.source=="device"]; con=dv[dv.event_token=="DEVICE_CONNECT"]
    dur,uo,uc=_pair_sessions(dv,"DEVICE_CONNECT","DEVICE_DISCONNECT")
    cm=_minutes(con.timestamp) if len(con) else np.array([])
    r.update(connect_count=len(con),disconnect_count=(dv.event_token=="DEVICE_DISCONNECT").sum(),device_session_count=len(dur),unmatched_connect_count=uo,unmatched_disconnect_count=uc,device_active_minutes_total=sum(dur),device_session_minutes_mean=np.mean(dur) if dur else 0,device_session_minutes_max=max(dur,default=0),device_distinct_pc_count=dv.pc.nunique(),own_pc_connect_count=(con.pc_context=="OWN").sum(),shared_pc_connect_count=(con.pc_context=="SHARED").sum(),foreign_pc_connect_count=(con.pc_context=="FOREIGN").sum(),foreign_pc_connect_ratio=_ratio((con.pc_context=="FOREIGN").sum(),len(con)),weekend_connect_count=(con.calendar_context=="WEEKEND").sum(),connect_time_deviation_mean=float(np.std(cm)) if len(cm) else 0,connect_time_deviation_max=float(np.max(abs(cm-np.median(cm)))) if len(cm) else 0)
    f=g[g.source=="file"]; ex=f.get("file_extension",pd.Series(dtype=str)).fillna(""); fl=pd.to_numeric(f.get("filename_length",pd.Series(dtype=float)),errors="coerce")
    r.update(file_event_count=len(f),distinct_filename_count=f.get("filename_hash",pd.Series(dtype=str)).nunique(),distinct_extension_count=ex[ex!=""].nunique(),extension_entropy=_entropy(ex),repeated_filename_count=_repeats(f.get("filename_hash",[])),repeated_extension_count=_repeats(ex),filename_length_mean=fl.mean() if len(fl) else 0,filename_length_std=fl.std(ddof=0) if len(fl) else 0,filename_length_max=fl.max() if len(fl) else 0,extension_present_ratio=_ratio((ex!="").sum(),len(f)),extensionless_file_count=(ex=="").sum(),multi_dot_filename_count=f.get("multi_dot",pd.Series(False,index=f.index)).sum(),distinct_file_pc_count=f.pc.nunique(),foreign_pc_file_ratio=_ratio((f.pc_context=="FOREIGN").sum(),len(f)),file_time_deviation_mean=np.std(_minutes(f.timestamp)) if len(f) else 0,file_burst_count_5m=_burst_count(f))
    h=g[g.source=="http"]; q=h.get("url_query_keys",pd.Series(dtype=str)).fillna("")
    r.update(http_request_count=len(h),distinct_url_count=h.get("url_hash",pd.Series(dtype=str)).nunique(),distinct_hostname_count=h.get("url_hostname",pd.Series(dtype=str)).nunique(),distinct_path_count=h.get("url_path_hash",pd.Series(dtype=str)).nunique(),distinct_scheme_count=h.get("url_scheme",pd.Series(dtype=str)).nunique(),https_request_ratio=_ratio(h.get("https",pd.Series(False,index=h.index)).sum(),len(h)),query_present_ratio=_ratio(h.get("query_present",pd.Series(False,index=h.index)).sum(),len(h)),distinct_query_key_count=len({x for s in q for x in str(s).split(";") if x}),repeated_url_count=_repeats(h.get("url_hash",[])),repeated_hostname_count=_repeats(h.get("url_hostname",[])),hostname_length_mean=h.get("hostname_length",pd.Series(dtype=float)).mean() if len(h) else 0,hostname_length_max=h.get("hostname_length",pd.Series(dtype=float)).max() if len(h) else 0,url_length_mean=h.get("url_length",pd.Series(dtype=float)).mean() if len(h) else 0,url_length_max=h.get("url_length",pd.Series(dtype=float)).max() if len(h) else 0,path_depth_mean=h.get("path_depth",pd.Series(dtype=float)).mean() if len(h) else 0)
    e=g[g.source=="email"]; rc=e.get("recipient_count",pd.Series(dtype=float)); ec=e.get("external_count",pd.Series(dtype=float)); hashes=e.get("recipient_hashes",pd.Series(dtype=str)).fillna("")
    r.update(email_sent_count=len(e),recipient_total_count=rc.sum(),unique_recipient_count=len({x for s in hashes for x in str(s).split(";") if x}),external_recipient_total=ec.sum(),external_recipient_ratio=_ratio(ec.sum(),rc.sum()),external_recipient_email_count=(ec>0).sum(),to_total=e.get("to_count",pd.Series(dtype=float)).sum(),cc_total=e.get("cc_count",pd.Series(dtype=float)).sum(),bcc_total=e.get("bcc_count",pd.Series(dtype=float)).sum(),bcc_email_count=(e.get("bcc_count",pd.Series(dtype=float))>0).sum(),attachment_email_count=(e.get("attachment_count",pd.Series(dtype=float))>0).sum(),attachment_total_count=e.get("attachment_count",pd.Series(dtype=float)).sum(),email_size_mean=e.get("email_size",pd.Series(dtype=float)).mean() if len(e) else 0,email_size_max=e.get("email_size",pd.Series(dtype=float)).max() if len(e) else 0,personal_from_email_count=(e.get("sender_context",pd.Series(dtype=str))!="INTERNAL").sum() if len(e) else 0)
    gaps=g.sort_values("timestamp").timestamp.diff().dt.total_seconds().div(60).dropna()
    transitions=g.sort_values("timestamp").source; changed=transitions[transitions.ne(transitions.shift())].iloc[1:]
    r.update(total_event_count=len(g),active_source_count=g.source.nunique(),weekend_event_ratio=_ratio((g.calendar_context=="WEEKEND").sum(),len(g)),own_pc_event_ratio=_ratio((g.pc_context=="OWN").sum(),len(g)),shared_pc_event_ratio=_ratio((g.pc_context=="SHARED").sum(),len(g)),foreign_pc_event_ratio=_ratio((g.pc_context=="FOREIGN").sum(),len(g)),distinct_all_pc_count=g.pc.replace("",np.nan).nunique(),source_transition_count=len(changed),source_transition_entropy=_entropy(changed),multi_source_burst_count_5m=_burst_count(g,True),inter_event_gap_mean_minutes=gaps.mean() if len(gaps) else 0,inter_event_gap_p95_minutes=gaps.quantile(.95) if len(gaps) else 0)
    return {k: float(0 if pd.isna(v) else v) for k,v in r.items()}


def build_behaviour_features(events: pd.DataFrame, role_days: pd.Series | None = None) -> pd.DataFrame:
    events=events.copy(); events["day"]=pd.to_datetime(events["day"])
    rows=[]; meta={}
    for (user,day),g in events.groupby(["user","day"],sort=True):
        row={"user":user,"day":day,**_base_row(g)}; rows.append(row)
        meta[(user,day)]={
          "hosts":set(g.loc[g.source.eq("http"),"url_hostname"].dropna())-{""},
          "external":{x for s in g.loc[g.source.eq("email"),"external_hashes"].dropna() for x in str(s).split(";") if x},
          "times":{token:_minutes(g.loc[g.event_token.eq(token),"timestamp"]) for token in ("DEVICE_CONNECT","FILE","LOGON","LOGOFF")},
        }
    out=pd.DataFrame(rows).sort_values(["user","day"]).reset_index(drop=True)
    for user,idx in out.groupby("user").groups.items():
        ids=list(idx); window=deque()
        for j in ids:
            day=out.at[j,"day"]
            while window and out.at[window[0],"day"] < day-pd.Timedelta(days=30): window.popleft()
            past_ids=list(window); p30=out.loc[past_ids] if past_ids else out.iloc[0:0]
            p7=p30[p30.day>=day-pd.Timedelta(days=7)]
            out.at[j,"active_days_last_7"]=len(p7); out.at[j,"active_days_last_30"]=len(p30)
            out.at[j,"total_events_mean_7d"]=p7.total_event_count.mean() if len(p7) else 0
            out.at[j,"total_events_mean_30d"]=p30.total_event_count.mean() if len(p30) else 0
            out.at[j,"total_events_std_30d"]=p30.total_event_count.std(ddof=0) if len(p30) else 0
            out.at[j,"short_long_activity_ratio"]=(out.at[j,"total_events_mean_7d"]+1)/(out.at[j,"total_events_mean_30d"]+1)
            out.at[j,"days_since_last_active_day"]=(day-p30.day.max()).days if len(p30) else 0
            current=meta[(user,day)]; history=[meta[(user,out.at[k,"day"])] for k in past_ids]
            old_hosts=set().union(*(m["hosts"] for m in history)) if history else set()
            old_external=set().union(*(m["external"] for m in history)) if history else set()
            out.at[j,"new_hostname_count_30d"]=len(current["hosts"]-old_hosts)
            out.at[j,"new_external_recipient_count_30d"]=len(current["external"]-old_external)
            # Time deviation uses only [D-30,D), never same-day or future events.
            for token,mean_name,max_name in (("DEVICE_CONNECT","connect_time_deviation_mean","connect_time_deviation_max"),("FILE","file_time_deviation_mean",None)):
                now=current["times"][token]; old=np.concatenate([m["times"][token] for m in history if len(m["times"][token])]) if any(len(m["times"][token]) for m in history) else np.array([])
                if len(now) and len(old):
                    dist=_circular_distance(now,float(np.median(old)))
                    out.at[j,mean_name]=float(np.mean(dist))
                    if max_name: out.at[j,max_name]=float(np.max(dist))
            for token,target,pick in (("LOGON","first_logon_time_deviation",np.min),("LOGOFF","last_logoff_time_deviation",np.max)):
                now=current["times"][token]; old=np.concatenate([m["times"][token] for m in history if len(m["times"][token])]) if any(len(m["times"][token]) for m in history) else np.array([])
                if len(now) and len(old): out.at[j,target]=float(_circular_distance(np.array([pick(now)]),float(np.median(old)))[0])
            window.append(j)
    out["days_in_current_role"] = role_days.to_numpy() if role_days is not None and len(role_days)==len(out) else 0.0
    values=out[["user","day"]+FEATURE_NAMES]
    mask_data={"user":out.user,"day":out.day}
    invalid_when_zero={
      "foreign_pc_logon_ratio":"logon_count","first_logon_time_deviation":"active_days_last_30","last_logoff_time_deviation":"active_days_last_30","work_span_minutes":"matched_session_count","total_session_minutes":"matched_session_count","max_session_minutes":"matched_session_count",
      "device_session_minutes_mean":"device_session_count","device_session_minutes_max":"device_session_count","foreign_pc_connect_ratio":"connect_count","connect_time_deviation_mean":"active_days_last_30","connect_time_deviation_max":"active_days_last_30",
      "extension_entropy":"file_event_count","filename_length_mean":"file_event_count","filename_length_std":"file_event_count","filename_length_max":"file_event_count","extension_present_ratio":"file_event_count","foreign_pc_file_ratio":"file_event_count","file_time_deviation_mean":"active_days_last_30",
      "https_request_ratio":"http_request_count","query_present_ratio":"http_request_count","hostname_length_mean":"http_request_count","hostname_length_max":"http_request_count","url_length_mean":"http_request_count","url_length_max":"http_request_count","path_depth_mean":"http_request_count","new_hostname_count_30d":"active_days_last_30",
      "external_recipient_ratio":"recipient_total_count","email_size_mean":"email_sent_count","email_size_max":"email_sent_count","new_external_recipient_count_30d":"active_days_last_30",
      "weekend_event_ratio":"total_event_count","own_pc_event_ratio":"total_event_count","shared_pc_event_ratio":"total_event_count","foreign_pc_event_ratio":"total_event_count","source_transition_entropy":"source_transition_count","inter_event_gap_mean_minutes":"total_event_count","inter_event_gap_p95_minutes":"total_event_count",
      "total_events_mean_7d":"active_days_last_7","total_events_mean_30d":"active_days_last_30","total_events_std_30d":"active_days_last_30","short_long_activity_ratio":"active_days_last_30","days_since_last_active_day":"active_days_last_30","days_in_current_role":"days_in_current_role",
    }
    for i,name in enumerate(FEATURE_NAMES,1):
        dep=invalid_when_zero.get(name)
        mask_data[f"m{i:03d}"]=out[dep].gt(0) if dep else pd.Series(True,index=out.index)
    masks=pd.DataFrame(mask_data)
    values=values.rename(columns={name:f"f{i:03d}" for i,name in enumerate(FEATURE_NAMES,1)})
    return values.merge(masks,on=["user","day"])
