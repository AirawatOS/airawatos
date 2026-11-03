# EC2 edge nginx — capture destination

The live EC2 edge nginx config is **not yet in source** (debt F-6 / incident 2026-11-03). This directory is
the destination for it. The live config lives on the box (`~/airawatos/` per `deploy/ec2/HOTPATCHES-2026-10-19.md`).

**Capture + commit (owner runs locally; the repo is on your machine):**
```
# 1. copy the live config(s) off the box
scp ec2-user@13.205.13.220:/home/ec2-user/airawatos/nginx*.conf deploy/ec2/nginx/
#    (also the mounted conf if nginx runs in a container, e.g.)
# ssh ec2-user@13.205.13.220 'docker exec <nginx-container> cat /etc/nginx/conf.d/default.conf' > deploy/ec2/nginx/default.conf

# 2. record the capture time in this README, then commit (force-add: docs/deploy paths may be gitignored)
git add -f deploy/ec2/nginx/*.conf deploy/ec2/nginx/README.md
git commit -m "docs(ec2): capture live edge nginx config (as of <YYYY-MM-DD HH:MM TZ>)"
git push origin HEAD   # no merge
```

**Captured:** _(pending — fill in the timestamp when the live config is added)_
