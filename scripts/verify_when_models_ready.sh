#!/usr/bin/env bash
# Waits for scripts/download_models.sh to finish both files, then runs the real-model tests and the end-to-end test.
cd "$(dirname "$0")/.."
until [ "$(grep -c '^done:' .models/download.log)" -ge 2 ]; do sleep 30; done
echo "== models downloaded: $(date)"; stat -c '%s %n' .models/bge-m3/pytorch_model.bin .models/bge-reranker-v2-m3/model.safetensors
export QB_TEST_DATABASE_URL="${QB_TEST_DATABASE_URL:-postgresql://quixotic:quixotic@localhost:5432/postgres}"
python -m pytest tests/integration/test_models.py tests/integration/test_e2e.py -v -p no:cacheprovider 2>&1 | tail -40
