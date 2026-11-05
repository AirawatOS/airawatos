# Operator guide — AWS appendix

Exact AWS console + CLI steps for each prerequisite in `OPERATOR-GUIDE.md` §1, plus the IAM permissions the
operator's **admin principal** (the human/role doing the setup — *not* the instance role) needs. Region in
examples: `ap-south-1`. The production instance's own role stays **least-privilege** (secrets read only); it
must **not** hold the describe/modify permissions below.

> The production EC2 instance role (e.g. `AirOS-Jenkins-SecretsReader`) deliberately **cannot** read volume or
> security-group state (`ec2:DescribeVolumes` returns `UnauthorizedOperation`). That is correct — these are
> operator-admin / control-plane actions, run from an admin workstation, not from the box.

---

## IAM — permissions the operator's admin principal needs

Read-only verification (most checks):
```
ec2:DescribeInstances, ec2:DescribeVolumes, ec2:DescribeSnapshots,
ec2:DescribeSecurityGroups, ec2:DescribeSecurityGroupRules, ec2:DescribeNetworkInterfaces,
kms:DescribeKey, kms:ListAliases,
ec2:GetEbsEncryptionByDefault, ec2:GetEbsDefaultKmsKeyId
```
Changes made during setup/remediation (grant deliberately, ideally time-boxed):
```
ec2:AuthorizeSecurityGroupIngress, ec2:RevokeSecurityGroupIngress, ec2:ModifySecurityGroupRules,
ec2:ModifyInstanceAttribute, ec2:CreateSnapshot, ec2:CopySnapshot, ec2:ModifySnapshotAttribute,
ec2:EnableEbsEncryptionByDefault, ec2:ModifyEbsDefaultKmsKeyId,
kms:CreateKey, kms:CreateAlias, kms:PutKeyPolicy, kms:CreateGrant, kms:ScheduleKeyDeletion,
iam:PutRolePolicy (for the instance-role Vault-auth policy)
```
Grant these to a named admin role assumed via SSO/MFA, not to the instance. Keep the instance role to
`secretsmanager:GetSecretValue` / its Vault-auth login only.

---

## 1. Encrypted disks, snapshots and backups with a customer-managed key

**Create/confirm a customer-managed KMS key (CMK).**
- Console: KMS → Customer managed keys → the key, or **Create key** (symmetric, encrypt/decrypt). Note its
  alias (e.g. `alias/airawatos-ebs`) and ARN; set a key policy limiting admin + usage to the operator roles.
- CLI: `aws kms list-aliases --region ap-south-1` ; `aws kms describe-key --key-id alias/airawatos-ebs`.

**Verify the instance's volumes are encrypted with the CMK (not an AWS-managed key).**
```
aws ec2 describe-volumes --region ap-south-1 \
  --filters Name=attachment.instance-id,Values=<i-id> \
  --query 'Volumes[].{id:VolumeId,enc:Encrypted,kms:KmsKeyId,size:Size}'
```
- `Encrypted:true` **and** `KmsKeyId` = your CMK ARN ⇒ OK. `alias/aws/ebs` (or the account default) ⇒
  AWS-managed, **not** customer-managed → remediate. `Encrypted:false` ⇒ unencrypted → remediate.
- Console: EC2 → Instances → `<i-id>` → **Storage** → each volume → Encryption + KMS key ID.

**Remediate an unencrypted / wrong-key volume (there is no in-place re-encrypt):** snapshot → copy the
snapshot with the CMK (`--encrypted --kms-key-id`) → create a new volume from the encrypted copy → stop the
instance, detach the old volume, attach the new one at the same device. Rehearse in the rehearsal env first.
```
aws ec2 create-snapshot --region ap-south-1 --volume-id <vol> --description airawatos-reencrypt
aws ec2 copy-snapshot --region ap-south-1 --source-region ap-south-1 --source-snapshot-id <snap> \
  --encrypted --kms-key-id alias/airawatos-ebs
aws ec2 create-volume --region ap-south-1 --availability-zone <az> --snapshot-id <enc-snap> --volume-type gp3
```

**Snapshots + backups encrypted with the CMK.**
```
aws ec2 describe-snapshots --region ap-south-1 --owner-ids self \
  --query 'Snapshots[].{id:SnapshotId,vol:VolumeId,enc:Encrypted,kms:KmsKeyId}'
```
All `Encrypted:true` with your CMK ARN. Off-host logical DB backups (S3) → the bucket has **SSE-KMS** with the
CMK as default: Console S3 → bucket → Properties → Default encryption = SSE-KMS (your CMK); or
`aws s3api get-bucket-encryption --bucket <b>`. Turn on **account-default EBS encryption** with the CMK so new
volumes are encrypted by default: `aws ec2 enable-ebs-encryption-by-default` +
`aws ec2 modify-ebs-default-kms-key-id --kms-key-id alias/airawatos-ebs`.

## 2. Perimeter — only 80/443 public, SSH from admin addresses

**Inspect the instance's security groups.**
```
aws ec2 describe-instances --region ap-south-1 --instance-ids <i-id> \
  --query 'Reservations[].Instances[].SecurityGroups'
aws ec2 describe-security-group-rules --region ap-south-1 \
  --filters Name=group-id,Values=<sg-id> \
  --query 'SecurityGroupRules[?IsEgress==`false`].{proto:IpProtocol,from:FromPort,to:ToPort,cidr:CidrIpv4}'
```
**Expected inbound (and nothing else):** 443 from `0.0.0.0/0`, 80 from `0.0.0.0/0` (redirect to 443), 22 from
the named admin CIDR(s) only. **No** 8080/8090/8093/8200/5432/etc. — those bind to 127.0.0.1 in compose.
- Console: EC2 → Security Groups → the SG → Inbound rules.

**Fix drift (control-plane only — never a host firewall, OPERATOR-GUIDE §5):**
```
# remove a stray/world-open service port
aws ec2 revoke-security-group-ingress --region ap-south-1 --group-id <sg> --protocol tcp --port 8080 --cidr 0.0.0.0/0
# restrict SSH to an admin CIDR
aws ec2 revoke-security-group-ingress --region ap-south-1 --group-id <sg> --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --region ap-south-1 --group-id <sg> --protocol tcp --port 22 --cidr <admin-cidr>/32
```

## 3. Vault unlocked via instance identity, never a root token

**Option A — KMS auto-unseal.** Vault `seal "awskms" { kms_key_id = "<CMK>" }`; the instance role gets a policy
allowing `kms:Encrypt`/`Decrypt`/`DescribeKey` **on that key only**. Confirm `vault status` shows
`Sealed:false` after a reboot (test in rehearsal).

**Option B — AWS IAM auth (per-service tokens).** Enable Vault `auth/aws`; map the instance role to a Vault
role whose policy is limited to the service's own secret paths; the service logs in via the instance identity
document to get a short-lived token. No root token anywhere.
```
# instance-role policy fragment for KMS auto-unseal (attach via iam:PutRolePolicy):
# { "Effect":"Allow","Action":["kms:Encrypt","kms:Decrypt","kms:DescribeKey"],
#   "Resource":"arn:aws:kms:ap-south-1:<acct>:key/<cmk-id>" }
```
**Verify no root token is in use:** grep the compose/env for `VAULT_TOKEN` set to a root token (should be
absent or a scoped token); confirm Vault audit shows service logins via `auth/aws`, not root. Reboot the
instance in rehearsal and confirm the stack comes back without a human unsealing.

## 4. Dedicated host — no unrelated projects

- Confirm the instance runs only this stack: `ssh <host> 'docker ps --format "{{.Names}} {{.Image}}"'` — every
  container is an AirawatOS image pinned by digest; remove stray `dev-*`/`buildx`/`vms-fixture`/`demo-connector`
  images (`docker image ls | grep -E 'dev-|buildx|vms-fixture|demo-connector'` → `docker image rm`).
- No second project's compose, cron, or data on the box. Tag the instance (`Project=airawatos`) and keep it out
  of shared ASGs.

## 5. Native amd64 build pipeline

- Build on a native **amd64** runner (CI) or an amd64 EC2 instance; never `--platform linux/amd64` under QEMU
  on an arm64 Mac (the reference image segfaults). Push **by digest**; record the digest in the prod compose.
- Verify an image's arch before deploy: `docker buildx imagetools inspect <image@digest> | grep -i platform`
  shows `linux/amd64`.

## 6. Separate rehearsal environment

- A short-lived amd64 EC2 instance of the **same family/region**, seeded from a restored prod backup
  (OPERATOR-GUIDE §3). Attach copies of the encrypted snapshots (CMK), run the full upgrade + rollback, then
  terminate. Keep it on the same perimeter rules so enforcement behaves as on prod.

---

## Quick verification matrix

| Prerequisite | Console | CLI |
|---|---|---|
| Volumes encrypted w/ CMK | EC2 → Instance → Storage | `ec2 describe-volumes … KmsKeyId` |
| Snapshots/backups encrypted w/ CMK | EC2 → Snapshots; S3 → Default encryption | `ec2 describe-snapshots`; `s3api get-bucket-encryption` |
| Perimeter 80/443 + SSH admin-only | EC2 → Security Groups → Inbound | `ec2 describe-security-group-rules` |
| Vault instance-identity unseal, no root | — | `vault status`; audit shows `auth/aws`; grep compose for root token |
| Dedicated host | — | `docker ps` / image inventory |
| amd64 provenance | — | `docker buildx imagetools inspect … platform` |

_Docs only. Nothing here changes code or deployed state._
