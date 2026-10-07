"""S3 raw storage (§46) and SQS queue (§47) adapters against mocked AWS (moto)."""
import json
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws

from backend.ingestion.storage import S3Storage, SQSQueue, raw_discord_key, raw_document_key
from tests.conftest import make_settings


@pytest.fixture
def aws(monkeypatch):
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "test")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="qb-test-bucket")
        url = boto3.client("sqs", region_name="us-east-1").create_queue(QueueName="q")["QueueUrl"]
        yield make_settings(s3_bucket="qb-test-bucket", sqs_queue_url=url, aws_region="us-east-1")


def test_s3_put_get_delete_and_prd_paths(aws):
    s3, fid = S3Storage(aws), uuid4()
    key = raw_document_key(fid, "sales_handbook.pdf")
    assert key == f"raw/documents/{fid}/sales_handbook.pdf" and raw_discord_key(fid, "x.json").startswith("raw/discord/")
    s3.put(key, b"%PDF-1.4 data")
    assert s3.get(key) == b"%PDF-1.4 data"
    s3.delete(key)
    with pytest.raises(Exception):
        s3.get(key)


def test_sqs_send_receive_delete(aws):
    q, jid = SQSQueue(aws), uuid4()
    assert q.receive(wait_seconds=0) is None
    q.send(jid, "document.process")
    body, receipt = q.receive(wait_seconds=1)
    assert body == {"job_id": str(jid), "type": "document.process"}
    q.delete(receipt)
    assert q.receive(wait_seconds=0) is None
