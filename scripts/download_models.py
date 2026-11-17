"""Pre-download the embedding model (avoids concurrent partial downloads)."""
import os
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
from huggingface_hub import snapshot_download
p = snapshot_download("neuralmind/bert-large-portuguese-cased",
                      allow_patterns=["*.json", "*.txt", "model.safetensors", "*.md"])
print("downloaded", p, flush=True)
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("neuralmind/bert-large-portuguese-cased", device="cuda")
print("EMB_DIM", m.get_sentence_embedding_dimension(), flush=True)
