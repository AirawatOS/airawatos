# Fresh-install test — local-dev reproduced from empty (Step 5, 4b slice)

**Date:** 2026-11-06 · **Goal:** prove `deploy/installer/install.sh` alone reproduces the stack from empty
volumes, in the documented split-role order (postgres+vault → keys → roles → migrator → services), with
conformance matching the pre-wipe baseline; and that `--profile production` stands up clean as non-superusers
with no data tenant and no test users. Reversible — all volumes backed up first.

## Step 1 — volume backup + restore command

Six local-dev volumes backed up (stack stopped for a consistent copy) to a durable location outside the repo:

    backup dir: ~/.airawat-localdev-backups/20261106-134653   (also recorded in …/LATEST)
    appbundles 820K · filestore 8.1M · identity 4K · netfiles 4K · pg 337M · vault 32K

**Exact restore command** (puts the dev stack back exactly as it was before the wipe):

```sh
BK="$(cat ~/.airawat-localdev-backups/LATEST)"        # = ~/.airawat-localdev-backups/20261106-134653
cd ~/Documents/Projects/Airawat
docker compose -p airawatos-localdev -f deploy/local-dev/docker-compose.dev.yml down          # keep volumes? no — recreate below
for v in appbundles filestore identity netfiles pg vault; do
  VOL="airawatos-localdev_localdev_$v"
  docker volume rm "$VOL" 2>/dev/null; docker volume create "$VOL" >/dev/null
  docker run --rm -v "$VOL":/data -v "$BK":/backup alpine \
    sh -c "rm -rf /data/* /data/..?* /data/.[!.]* 2>/dev/null; tar xzf /backup/$v.tar.gz -C /data"
done
docker compose -p airawatos-localdev -f deploy/local-dev/docker-compose.dev.yml up -d
```

(Each tarball is the full contents of one named volume; restore wipes the volume and untars back into it.)
