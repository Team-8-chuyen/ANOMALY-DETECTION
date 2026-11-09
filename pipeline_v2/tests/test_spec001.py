from pathlib import Path
import tempfile
import pandas as pd

from itd.features.contexts import add_past_only_pc_context
from itd.features.count_features import FEATURE_NAMES, build_behaviour_features
from itd.features.sequence_tokens import SEQUENCE_FIELDS, compress_runs, build_sequence_fields, build_sequence_fields_polars
from itd.utils.checkpoint import BucketCheckpoint, ProcessLock


def fixture_events():
    rows=[
      ("1","2010-01-01 08:00","U1","PC1","logon","LOGON"),
      ("2","2010-01-01 09:00","U1","PC1","http","HTTP"),
      ("3","2010-01-01 09:02","U1","PC1","http","HTTP"),
      ("4","2010-01-01 17:00","U1","PC1","logon","LOGOFF"),
      ("5","2010-01-02 08:00","U1","PC1","logon","LOGON"),
      ("6","2010-01-02 08:03","U1","PC1","file","FILE"),
      ("7","2010-01-02 08:05","U1","PC1","email","EMAIL"),
    ]
    df=pd.DataFrame(rows,columns=["event_id","timestamp","user","pc","source","event_token"])
    df.timestamp=pd.to_datetime(df.timestamp); df["day"]=df.timestamp.dt.normalize(); df["calendar_context"]="WORK_HOUR"
    df["url_hash"]=""; df["url_hostname"]=""; df["url_path_hash"]=""; df["url_scheme"]=""; df["url_query_keys"]=""; df["hostname_length"]=0; df["url_length"]=0; df["path_depth"]=0; df["query_present"]=False; df["https"]=False
    df["filename_hash"]=""; df["file_extension"]=""; df["filename_length"]=0; df["multi_dot"]=False
    df["recipient_count"]=0; df["external_count"]=0; df["recipient_hashes"]=""; df["external_hashes"]=""; df["to_count"]=0; df["cc_count"]=0; df["bcc_count"]=0; df["attachment_count"]=0; df["email_size"]=0; df["sender_context"]="MISSING"
    return df


def test_registry_counts():
    assert len(FEATURE_NAMES)==100 and len(set(FEATURE_NAMES))==100
    assert len(SEQUENCE_FIELDS)==24 and len(set(SEQUENCE_FIELDS))==24


def test_run_compression_preserves_events():
    df=add_past_only_pc_context(fixture_events(),30,1)
    out=compress_runs(df,5)
    assert int(out.run_count.sum())==len(df)
    assert len(out)==len(df)-1


def test_outputs_have_locked_shapes():
    df=add_past_only_pc_context(fixture_events(),30,1)
    features=build_behaviour_features(df)
    assert features.filter(regex=r"^f\d{3}$").shape[1]==100
    assert features.filter(regex=r"^m\d{3}$").shape[1]==100
    seq=build_sequence_fields(df)
    assert all(name in seq for name in SEQUENCE_FIELDS)
    assert seq.groupby(["user","day"]).event_index.min().eq(0).all()


def test_polars_sequence_matches_pandas_shape_and_tokens():
    df=add_past_only_pc_context(fixture_events(),30,1)
    old=build_sequence_fields(df); new=build_sequence_fields_polars(df)
    assert old[["user","day","event_token"]].reset_index(drop=True).equals(new[["user","day","event_token"]].reset_index(drop=True))
    assert old.shape==new.shape
    for column in old.columns:
        if pd.api.types.is_numeric_dtype(old[column]):
            assert pd.Series(old[column]).fillna(0).round(8).equals(pd.Series(new[column]).fillna(0).round(8))
        else:
            assert old[column].astype(str).tolist()==new[column].astype(str).tolist()


def test_future_data_does_not_change_past_context():
    base=fixture_events()
    before=add_past_only_pc_context(base,30,1).loc[lambda x:x.day==pd.Timestamp("2010-01-01"),"pc_context"].tolist()
    future=base.iloc[[0]].copy(); future["event_id"]="99"; future["timestamp"]=pd.Timestamp("2010-02-01"); future["day"]=future["timestamp"].dt.normalize()
    after=add_past_only_pc_context(pd.concat([base,future],ignore_index=True),30,1).loc[lambda x:x.day==pd.Timestamp("2010-01-01"),"pc_context"].tolist()
    assert before==after


def test_checkpoint_requires_all_outputs():
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); cp=BucketCheckpoint.load(root/"checkpoint.json")
        a,b=root/"a.parquet",root/"b.parquet"; a.write_bytes(b"ok"); cp.mark_complete(3)
        assert not cp.is_complete(3,[a,b])
        b.write_bytes(b"ok")
        assert BucketCheckpoint.load(root/"checkpoint.json").is_complete(3,[a,b])


def test_process_lock_blocks_second_owner_and_releases():
    with tempfile.TemporaryDirectory() as raw:
        path=Path(raw)/"prepare.lock"
        with ProcessLock(path):
            assert path.exists()
            try: ProcessLock(path).__enter__()
            except RuntimeError: pass
            else: raise AssertionError("second lock should fail")
        assert not path.exists()
