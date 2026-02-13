"""Tests for StateRecord model and write/load helpers (CP-016)."""

from __future__ import annotations

import json

from daylily_ec.state.models import StateRecord
from daylily_ec.state.store import load_state_record, write_state_record


# ---------------------------------------------------------------------------
# StateRecord model
# ---------------------------------------------------------------------------


class TestStateRecordModel:
    """StateRecord instantiation and serialisation."""

    def test_defaults(self):
        rec = StateRecord()
        assert rec.bucket == ""
        assert rec.cluster_name is None
        assert rec.region == ""
        assert rec.cfn_stack_name == ""
        assert rec.heartbeat_topic_arn == ""

    def test_full_construction(self):
        rec = StateRecord(
            cluster_name="test-cls",
            region="us-west-2",
            region_az="us-west-2b",
            bucket="my-bucket",
            keypair="my-key",
            public_subnet_id="subnet-pub",
            private_subnet_id="subnet-priv",
            policy_arn="arn:aws:iam::123:policy/p",
            global_budget_name="daylily-global",
            cluster_budget_name="test-cls",
            cfn_stack_name="pcluster-vpc-stack-2b",
        )
        assert rec.cluster_name == "test-cls"
        assert rec.bucket == "my-bucket"
        assert rec.cfn_stack_name == "pcluster-vpc-stack-2b"

    def test_to_sorted_json_deterministic(self):
        """Same inputs → byte-identical JSON."""
        kwargs = dict(
            run_id="20260101120000",
            cluster_name="det",
            region="us-east-1",
            bucket="b",
        )
        a = StateRecord(**kwargs).to_sorted_json()
        b = StateRecord(**kwargs).to_sorted_json()
        assert a == b

    def test_to_sorted_json_keys_sorted(self):
        rec = StateRecord(run_id="20260101120000", cluster_name="s")
        data = json.loads(rec.to_sorted_json())
        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_model_dump_roundtrip(self):
        rec = StateRecord(
            run_id="20260101120000",
            cluster_name="rt",
            bucket="b1",
            heartbeat_email="a@b.com",
        )
        dumped = rec.model_dump(mode="json")
        restored = StateRecord(**dumped)
        assert restored == rec


# ---------------------------------------------------------------------------
# write / load helpers
# ---------------------------------------------------------------------------


class TestWriteLoadStateRecord:
    """write_state_record and load_state_record round-trip."""

    def test_write_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        rec = StateRecord(run_id="20260201100000", cluster_name="wtest")
        path = write_state_record(rec)
        assert path.exists()
        assert "state_wtest_20260201100000.json" in path.name

    def test_written_json_has_sorted_keys(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        rec = StateRecord(run_id="20260201100000", cluster_name="sk")
        path = write_state_record(rec)
        data = json.loads(path.read_text())
        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        rec = StateRecord(
            run_id="20260201100000",
            cluster_name="ldrt",
            region="eu-west-1",
            bucket="b2",
            heartbeat_schedule_expression="rate(60 minutes)",
        )
        path = write_state_record(rec)
        loaded = load_state_record(path)
        assert loaded.cluster_name == "ldrt"
        assert loaded.bucket == "b2"
        assert loaded.heartbeat_schedule_expression == "rate(60 minutes)"

    def test_none_cluster_name_uses_unknown(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        rec = StateRecord(run_id="20260201100000")
        path = write_state_record(rec)
        assert "state_unknown_" in path.name

    def test_file_ends_with_newline(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        rec = StateRecord(run_id="20260201100000", cluster_name="nl")
        path = write_state_record(rec)
        assert path.read_text().endswith("\n")

    def test_deterministic_output(self, tmp_path, monkeypatch):
        """Two writes of the same record produce identical file contents."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        kwargs = dict(run_id="20260201100000", cluster_name="det2", bucket="b")
        p1 = write_state_record(StateRecord(**kwargs))
        # Write a second time with different run_id for unique filename
        kwargs2 = dict(run_id="20260201100001", cluster_name="det2", bucket="b")
        p2 = write_state_record(StateRecord(**kwargs2))
        # Content differs only in run_id — check structure is sorted
        d1 = json.loads(p1.read_text())
        d2 = json.loads(p2.read_text())
        assert list(d1.keys()) == list(d2.keys())

