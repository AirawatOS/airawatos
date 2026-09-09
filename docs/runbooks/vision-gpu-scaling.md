# Runbook: GPU perception tier for crowd-counting (scale to ~1000+ cameras)

**Audience:** GPU/infra team. **Goal:** move the vision inference tier (YOLO detection + CSRNet density) off
single-CPU, per-frame execution onto a GPU with batched inference, so ~1000 cameras can be counted on a
1-minute cadence.

**Context — measured on the current CPU box (single worker, per-frame):**
| model | per frame | ×1000 |
|---|---|---|
| YOLOv8n detection | 2.2 s | ~37 min |
| CSRNet density | 3.2 s | ~54 min |

The **registry, decision loop, and operator UI already scale to 1000** (a 1000-cell map frame is a ~0.9 MB,
sub-second query). **The only thing that needs GPU is the per-frame inference.** Nothing below touches schemas,
the crush-risk engine, or the app.

Target after this work (single mid-range GPU, batched): **YOLOv8n ~5–10 ms/frame, CSRNet ~15–30 ms/frame** →
1000 frames in **~10–30 s**, comfortably inside a 60 s tick. One T4/L4/A10-class GPU is enough for ~1000
cameras at 1-min cadence; size up (or add GPUs) for higher camera counts or sub-minute cadence.

---

## 1. Host prerequisites (GPU node)

1. NVIDIA GPU with a recent **driver** (CUDA 12.x-capable; T4/L4/A10/A100 all fine — yolov8n + CSRNet are small).
2. **NVIDIA Container Toolkit** so Docker can expose the GPU:
   ```bash
   # (Amazon Linux / RHEL family)
   sudo dnf install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi   # must list the GPU
   ```
3. The runtime-manager places components with `docker run`, so the GPU node must be where the
   **runtime-manager runs** (or a GPU worker it dispatches to — see §4).

## 2. Build a GPU vision runtime image

Today `components/runtimes/vision` is built `FROM` the CPU modeling image (CPU torch). Add a GPU sibling.

`components/runtimes/vision-gpu/Dockerfile`:
```dockerfile
# CUDA PyTorch base (matches host driver's CUDA major). ultralytics + opencv-headless on top.
FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libxcb1 \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "ultralytics>=8.2" "opencv-python-headless>=4.9" pillow h3
WORKDIR /drivers
ENV PYTHONPATH=/drivers PYTHONUNBUFFERED=1 YOLO_CONFIG_DIR=/tmp/ultralytics
```
`components/runtimes/vision-gpu/meta.yaml` — mirror `runtimes/vision/meta.yaml` but:
- `runtime_id: vision-gpu`, `profile: vision-gpu`, `image: <org>/airawatos-runtime-vision-gpu:<tag>`,
- add a **`gpu: true`** flag (new field the launcher keys on — see §4),
- set `image_digest` to the pulled image's `docker image inspect --format '{{.Id}}'` on the GPU node.

Build for the GPU node's arch (usually `linux/amd64`), push, `docker pull` on the node, and **certify the
runtime** the same way the CPU one was: `recert.py runtimes` (mints the `ds:airawat:runtime/vision-gpu` cert
under the network authority; the launcher refuses an uncertified runtime).

## 3. Batch the inference (the real speedup)

Per-frame calls waste the GPU. Change `components/drivers/crowd-count/run.py` to **collect all frames first,
then run ONE batched forward pass** (this is where the 100–300× speedup comes from — GPU idle time between
single frames is the killer, not raw FLOPs):

- Detection (YOLO): `model.predict(list_of_images, ...)` accepts a list → one batched call. Count boxes per image.
- Density (CSRNet): stack the preprocessed tensors into `[N,3,H,W]` and call the model once; sum each map.
- Keep batch size bounded (e.g. 32–64) to fit GPU memory; loop batches. Model is loaded **once per run** (already true), which now amortises over the whole fleet in a single run.

The driver already processes all cameras in one run, so this is a local change to how `_count_people` is called
(batch, not per-frame). Everything downstream (`vision.detection`, `cell.crowd_density`) is unchanged.

## 4. Platform change: let the launcher request the GPU

`components/_common/launcher.py` builds the `docker run` command for placed components. It does **not** pass
`--gpus` today. Add: when the resolved runtime meta has `gpu: true`, append `--gpus all` (or
`--gpus '"device=0"'`) to the `docker run` args. That's the one-line enablement; without it the container runs
on CPU even on a GPU host.

If the GPU node is separate from the main stack, point `crowd-count`'s schedule/placement at the
runtime-manager instance running on the GPU node (it already reads `rt-components` and pulls the image).

## 5. Fix the two O(N)/O(N²) hotspots (needed at 1000, independent of GPU)

1. **Latest-frame index** — `crowd-count._latest_frame` scans *all* `media.frame` per camera → quadratic at
   1000 cams. Replace with a per-camera lookup: query `media.frame` filtered by `camera_ref` with a small
   limit sorted by `captured_at`, or maintain a `device.latest_frame` pointer per camera updated on write.
2. **Frame retention** — 1000 JPEGs/min ≈ 200 MB/min fills disk in hours. Add a retention sweep (delete/retract
   `media.frame` + filestore blobs older than N minutes) or wire the registry→filestore archival-tiering
   capability already on the backlog. Detections/density are kept; raw frames are transient.

## 6. Scheduler

One `crowd-count` run that batches the whole fleet is fine (single scheduled run per tick). If you split across
multiple GPU workers, shard by camera-id range (env `CAMERA_SHARD=k/of/n`) and run one schedule per shard.

## 7. Rollout + validation

1. Provision GPU node (§1); build+push+pull `vision-gpu` image; set its `image_digest`; `recert.py runtimes`.
2. Land the launcher `--gpus` change (§4) and the batched `crowd-count` + latest-frame-index change (§3, §5).
3. Point `crowd-count`'s `runtime.profile` at `vision-gpu`; re-certify + reinstall the driver (version bump).
4. Add the frame-retention sweep (§5.2).
5. **Validate**: seed N sim cameras (the `crowd-sim-vision` driver + `vision_govern.py` already do this — see
   `docs/decisions/vision-crowd-counting-slice.md`), watch one `crowd-count` run process the whole fleet, and
   confirm wall-clock < 60 s and `nvidia-smi` shows utilisation. Ramp N: 100 → 500 → 1000 → 5000.

## What does NOT change
Schemas (`device.camera`, `media.frame`, `vision.detection`, `cell.crowd_density`), the crush-risk engine, the
decision/alert spine, the viz layers, and Crowd Command — all already handle 1000 cells at sub-second/~1 MB.
The GPU work is confined to the perception tier: runtime image, batched inference, launcher GPU flag, a
latest-frame index, and frame retention.
