# Local model assets

This directory is intentionally excluded from Git because the HuggingFace model
artifacts are several gigabytes in total.

The application can download the required models on first use when
`HF_MODEL_AUTO_DOWNLOAD=true`, or you can pre-download them from the backend:

```bash
cd career-agent/backend
python scripts/init_models.py
```

Default model locations:

- `career-agent/models/embedding`
- `career-agent/models/reranker`

Keep downloaded model files local, or store them in a model registry/object
storage service if you need to share a deployment bundle.
