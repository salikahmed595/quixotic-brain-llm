#!/usr/bin/env bash
# Resumable download of the two local models (BGE-M3 embeddings, multilingual BGE reranker). Safe to re-run.
# Weights land in .models/<name>/; config/tokenizer files are already there. ~2.3 GB each.
set -u
cd "$(dirname "$0")/.."
get() {  # url dest
  until curl -fL --retry 5 --retry-delay 5 -C - -o "$2" "$1"; do echo "retrying $2 ..."; sleep 10; done
  echo "done: $2"
}
get "https://huggingface.co/BAAI/bge-m3/resolve/main/pytorch_model.bin"                  .models/bge-m3/pytorch_model.bin &
get "https://huggingface.co/BAAI/bge-reranker-v2-m3/resolve/main/model.safetensors"      .models/bge-reranker-v2-m3/model.safetensors &
wait
