from __future__ import annotations

from collections import Counter, defaultdict, deque
import pandas as pd


def add_past_only_pc_context(events: pd.DataFrame, history_days: int = 30, own_min_days: int = 3) -> pd.DataFrame:
    """Assign OWN/SHARED/FOREIGN using an O(events) past-only rolling window."""
    out = events.sort_values(["day", "timestamp", "event_id"], kind="stable").copy()
    logon_pairs={day:list(g[["user","pc"]].drop_duplicates().itertuples(index=False,name=None)) for day,g in out[out.event_token.eq("LOGON")].groupby("day",sort=True)}
    window=deque(); user_pc=defaultdict(Counter); pc_user=defaultdict(Counter); assigned={}
    for day,group in out.groupby("day",sort=True):
        cutoff=pd.Timestamp(day)-pd.Timedelta(days=history_days)
        while window and window[0][0] < cutoff:
            _,pairs=window.popleft()
            for user,pc in pairs:
                user_pc[user][pc]-=1; pc_user[pc][user]-=1
                if user_pc[user][pc]<=0: del user_pc[user][pc]
                if pc_user[pc][user]<=0: del pc_user[pc][user]
        own={u:min(((-count,pc) for pc,count in counts.items()))[1] for u,counts in user_pc.items() if counts and max(counts.values())>=own_min_days}
        shared={pc for pc,users in pc_user.items() if sum(v>0 for v in users.values())>=2}
        for row in group.itertuples():
            assigned[row.Index]="MISSING" if not row.pc else "OWN" if own.get(row.user)==row.pc else "SHARED" if row.pc in shared else "FOREIGN"
        pairs=logon_pairs.get(day,[])
        window.append((pd.Timestamp(day),pairs))
        for user,pc in pairs: user_pc[user][pc]+=1; pc_user[pc][user]+=1
    out["pc_context"] = out.index.map(assigned).fillna("FOREIGN")
    return out.sort_index()
