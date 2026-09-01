# Docker Build Performance

Notes for anyone whose `docker compose up --build` seems to hang forever on
the `ai_service` image.

## The problem we hit

`ai_service/requirements.txt` listed `torch` with no version and no package
index. On Linux, the default PyPI `torch` wheel declares the entire NVIDIA
CUDA runtime as hard dependencies:

| Package                | Download |
| ---------------------- | -------- |
| `torch` (CUDA build)   | ~527 MB  |
| `nvidia-cudnn-cu13`    | ~366 MB  |
| `nvidia-nccl-cu13`     | ~206 MB  |
| `triton`               | ~198 MB  |
| `cuda-toolkit` (cublas, cufft, cusolver, cusparse, nvrtc, ...) | ~1.5 GB |
| `nvidia-cusparselt-cu13`, `nvidia-nvshmem-cu13`, `cuda-bindings` | ~400 MB |
| **Total**              | **~3.2 GB** |

None of it is used. `app/models/sentiment_model.py` pins inference to the CPU:

```python
DEVICE = torch.device("cpu")
```

On a home or campus connection, 3.2 GB is where the "two hours and still
going" came from. Two things then made it worse:

- `pip install --no-cache-dir` threw away every downloaded wheel, so a build
  that was cancelled or timed out restarted the whole 3.2 GB from zero.
- Docker Desktop on Windows runs the build inside a Linux VM whose default
  disk and network throughput is lower than the host's, and the CUDA wheels
  also have to be *unpacked* — roughly 8 GB written to the VM disk.

## The fix

**1. CPU-only PyTorch.** `requirements.txt` now pulls torch from PyTorch's own
CPU index:

```
--extra-index-url https://download.pytorch.org/whl/cpu

torch==2.13.0+cpu; sys_platform != "darwin"
torch==2.13.0; sys_platform == "darwin"
```

That wheel is **184 MB with zero NVIDIA dependencies** — about a 17x smaller
download, and identical behaviour for this service. (macOS wheels are already
CPU-only and have no `+cpu` variant, hence the second line.)

**2. Every dependency pinned.** `transformers`, `pandas`, `sentencepiece`,
`protobuf`, `tiktoken` and `cryptography` were unpinned. Unpinned packages let
pip's resolver backtrack — downloading candidate after candidate before
settling — and they mean two interns can end up on different versions. They
are now pinned to the versions the project already resolved to.

**3. A pip cache mount.** Both Dockerfiles replaced `--no-cache-dir` with a
BuildKit cache mount:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=600 --retries=10 -r requirements.txt
```

The cache lives in the builder, not in the image, so image size is unchanged.

> **How much this actually helps depends on your builder, and it may be
> nothing.** Measured on Docker 27.3.1 using the default `docker` driver
> (BuildKit embedded in the daemon), the mount is **discarded between
> builds** — a file written to it in one build is gone in the next, and a
> `--no-cache` rebuild re-downloaded all 118 packages including the 191.8 MB
> torch wheel (277s cold vs 215s, with `Using cached: 0`). Cache mounts
> persist reliably on the `docker-container` driver:
>
> ```bash
> docker buildx create --name resolveai --driver docker-container --use
> ```
>
> This does not affect the normal development loop. Docker's ordinary *layer*
> cache works regardless, so a plain `docker compose up -d --build` skips the
> pip step entirely unless `requirements.txt` changed. The mount only matters
> when you deliberately bust the layer cache with `--no-cache`.

**4. The Hugging Face model cache is a volume.** `ai_service` downloads
`cardiffnlp/twitter-xlm-roberta-base-sentiment` (~1.1 GB) the first time it
starts. `HF_HOME=/models` plus the `hf_cache` volume in `docker-compose.yml`
keeps it across container recreation, so only the very first start pays it.

## If a build is already stuck

Cancel it (Ctrl+C), then rebuild from the fixed files:

```bash
docker compose down
docker compose build --no-cache ai_service
docker compose up -d
```

`--no-cache` is needed only once, to drop any layer that was built from the
old requirements file. Expect it to re-download everything (~5 minutes); see
the note above on why the pip cache may not spare you that.

## Checking what actually got installed

```bash
docker compose exec ai_service pip list | grep -i -E "nvidia|torch|triton|cuda"
```

Expected output is a single `torch 2.13.0+cpu` line. If you see any `nvidia-*`
or `triton` package, the CUDA build slipped back in — check that the
`--extra-index-url` line and the `+cpu` pin are still in
`ai_service/requirements.txt`.

## Rules of thumb for this repo

- Never add an unpinned dependency to a `requirements.txt`.
- Any ML library that has a CPU and a GPU build: take the CPU build unless the
  service actually moves tensors to a GPU.
- Keep the heavy `pip install` layer above `COPY app ./app`, so editing
  application code never re-triggers a dependency download.
