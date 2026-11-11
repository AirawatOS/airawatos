# Operating rules — production changes (standing)

These are standing rules for any change to a **production** AirawatOS deployment (currently the EC2 host
`airos.airawat.org` / `13.205.13.220`). They bind the operator and any automated agent.

## 1. Approved-list only; otherwise stop for approval
A production change is made **only** if it is on an **explicitly approved list** for the task at hand. **Any
production change outside that approved list stops for approval** — the agent reports what it intended and
why, and waits. Approval for one change never generalizes to another; approval in one session does not carry
to the next.

## 2. Host-level changes always require approval + a rollback plan
Changes **below the application** — host **firewall** (iptables/nftables, `iptables-services`, security
groups), **systemd** units/enable/disable, **kernel parameters** (`sysctl`), network interfaces, disk/mount,
Docker daemon config — **always require explicit approval** and a **written rollback plan** (the exact
command to undo, and how to verify) *before* the change is made. This holds even when the change looks
read-only or trivial.

### Why (incident 2026-11-03)
`sudo systemctl enable --now iptables`, run to persist a port-containment drop, loaded Amazon Linux's stock
`/etc/sysconfig/iptables` whose `-A FORWARD -j REJECT --reject-with icmp-host-prohibited` rejected **all**
Docker inter-container forwarding — `airos.airawat.org` served 502 to everyone until the rule was removed.
A host-level change with no rollback plan took production down. See
`docs/incident-2026-11-03-ec2-exposure-hardening.md`.

### Corollary — this box specifically
On the EC2 Docker host, **never** firewall ports with host `iptables`/`iptables-services` (it collides with
Docker's nft-managed rules). Perimeter = the **AWS security group**; local scoping = **container
port-binding** (`127.0.0.1:PORT`). (Also recorded in agent memory.)
