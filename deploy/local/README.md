# ⚠️ LEGACY — do not install from this directory

`deploy/local/` is the **old** prebuilt-image stack. It includes `airawatos-install.sh`, `airawatos-bootstrap.sh`,
`docker-compose.yml` and `INSTALL.md`. It pulls images from Docker Hub that are **not** what `main` runs, and it skips
the Layer 1 guarantees:
- the production guard;
- per-service Vault AppRoles;
- the installer write guard;
- verified backup and restore.

**To install AirawatOS locally, follow [`docs/operator/INSTALL-LOCAL.md`](../../docs/operator/INSTALL-LOCAL.md):** it
covers building the images from `main` with `deploy/build-images.sh` and running `deploy/installer/install.sh --profile dev`.

The scripts here refuse to run unless `AIRAWATOS_LEGACY=1` is set. The directory is kept only because older EC2 notes
(`deploy/ec2/HOTPATCHES-2026-10-19.md`) refer to its compose file. It will be removed with the repository restructure.
