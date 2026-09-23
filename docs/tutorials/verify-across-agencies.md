# Verify a person across states with a credential (issue → carry → verify)

A common federation need: **one state's agency has to trust a fact another state's agency issued** — a
migrant worker registered by their home state, a degree from another state's university, a birth certificate
issued elsewhere. The wrong way is a live database-to-database integration between every pair of agencies. The
right way on AirawatOS is a **Verifiable Credential (VC)**: the home agency issues the person a *signed* claim,
the person carries it, and the destination agency **verifies the signature offline** against the issuer's
published key — no call between the two agencies at verify time.

Worked example: **Bihar's labour board issues a construction-worker registration; the worker migrates; Maharashtra's
board verifies it** before porting benefits. Three roles: the **issuer** (home state), the **holder** (the
migrant), the **verifier** (destination state).

> Reference URLs (local dev): app-host `http://localhost:8099` · network `http://localhost:8090` · identity `:8093`.
> The two agencies are two **tenants** on the same network. Set `HOME=bihar-labour` and `DEST=maharashtra-labour`
> (substitute your own tenant ids — each must be a network participant with a steward key).

---

## Part 1 — The ISSUER (home state) issues a signed credential

### 1a. Govern the credential *type* (once)

A credential's `type` must be a **governed `credential.*` noun** — the network only lets an agency issue a type
everyone has agreed on. Propose it, a steward approves it (the governed change-request loop):

```bash
DEV=$(curl -s -X POST http://localhost:8093/realms/bihar-labour/login \
  -H 'content-type: application/json' -d '{"username":"bihar-labour-admin"}' | jq -r .access_token)

# propose the type (its claims contract) …
curl -s -X POST http://localhost:8090/v1/schema-requests -H "Authorization: Bearer $DEV" \
  -H 'content-type: application/json' -d '{
    "schema_id":"credential.bocw_registration","version":"0.1.0","x_kind":"fragment",
    "definition":{"type":"object","x-kind":"fragment","properties":{
      "reg_no":{"type":"string"},"name":{"type":"string"},"trade":{"type":"string"}}},
    "justification":"Inter-state portability of BOCW worker registration"}'
# … then a network steward approves it (POST /v1/schema-requests/decide {decision:"approve"}).
```

### 1b. Issue the credential to the worker

Once the type is governed, the agency issues a VC to the **holder** (the worker's identity). It's signed with
the issuer tenant's **steward Ed25519 key, held in Vault** (born there, never exported):

```bash
curl -s -X POST http://localhost:8090/v1/credentials/issue -H "Authorization: Bearer $DEV" \
  -H 'content-type: application/json' -d '{
    "issuer_tenant":"bihar-labour",
    "holder":"user://bihar-labour/asha",
    "type":"credential.bocw_registration",
    "title":"BOCW Worker Registration",
    "claims":{"reg_no":"BR-2024-0091","name":"Asha Devi","trade":"mason"},
    "expires_at":"2027-03-31T00:00:00Z"
  }'
# → {"issued":"ds:bihar-labour:credential/credential.bocw_registration-…","credential":{…,"signature":{…}}}
```

- `holder` — *who* the credential is about (their platform identity). Getting this right is the hard part of
  cross-state work — see [What must be true](#what-must-be-true).
- `claims` — the facts, must match the governed type's contract.
- `expires_at` *(optional)* — a validity end. It goes **inside the signed core**, so it can't be tampered, and
  verification enforces it.
- The response `credential` is the full **signed VC** — the object the holder keeps and later presents.

> **You usually don't call issue directly.** In a real service, issuance is the *last step of a workflow*: a
> workflow step declares `issues: credential.bocw_registration`, and when the registration is approved the
> platform mints the VC into the worker's wallet automatically. Direct issue is shown here
> so you can see the shape.

---

## Part 2 — The HOLDER (the migrant) carries it in their wallet

The worker owns the credential — it lives in **their** wallet (the **My Documents** app), not on an agency
server. Issuance creates an **offer**; the holder **accepts** it, which deposits their own signed copy into
their own tenant (genuine holder-controlled storage). The app calls three app-host bridges:

| Bridge (POST) | Does |
|---|---|
| `/bridge/my-credentials` | the wallet: `offers` (awaiting accept) + `held` (accepted) |
| `/bridge/credential-accept` `{credential_id}` | accept an offer → deposit the signed VC into the holder's tenant |
| `/bridge/credential-verify` `{credential}` | verify any held VC (used to show a green tick) |

The worker never has to be online with Bihar again — the signed credential is theirs to present.

---

## Part 3 — The VERIFIER (destination state) verifies it

Maharashtra's board verifies the credential the worker presents. It resolves **Bihar's published steward
public key from the network directory** and checks the signature — **no call to Bihar**. Verification checks
both *authenticity* and *validity*:

```bash
curl -s -X POST http://localhost:8099/bridge/credential-verify \
  -H 'content-type: application/json' -d '{"credential": <the presented VC object>}'
```
```jsonc
{
  "verified": true,              // ← the one field to gate on: authentic AND currently valid
  "signature_valid": true,       // signature checks out against the issuer's published key
  "revoked": false,              // issuer has not revoked it
  "expired": false,              // within expires_at
  "revocation_checked": true,    // the network held an authoritative record for this id
  "key_source": "directory",     // issuer key came from the CA-signed directory (cross-tenant), not a local guess
  "issuer_tenant": "bihar-labour", "type": "credential.bocw_registration", "holder": "user://bihar-labour/asha"
}
```

**Gate on `verified`.** It is true only when the signature holds **and** the credential is not revoked **and**
not expired. A revoked or lapsed registration returns `verified:false` with a `reason`, even though its
signature is still genuine — *authenticity is not validity*, and for "verify a migrant" you need both.

### Verify as part of applying for a service (the common case)

Usually the worker isn't verified in the abstract — they **apply for a Maharashtra service** that *requires*
the credential. Declare it on the offering, and the platform verifies the presented VC for you and pins it to
the case as evidence:

```jsonc
// Maharashtra's service offering
{ "tenant":"maharashtra-labour", "service_id":"benefit-porting", …,
  "required_credentials":["credential.bocw_registration"] }
```
When the worker files, their app presents the held VC in `credential_refs`; the provider re-verifies it
(`verified && holder==applicant && type matches`) before the case proceeds. This is the stronger form of "upload
your certificate" — a tamper-evident credential re-checked against the issuer's key, not a PDF.

---

## Part 4 — Revocation: keeping verification honest over time

A registration can be cancelled. The **issuer** revokes it; from then on verification reports it invalid — the
signature is still genuine, but the credential is no longer valid:

```bash
# Bihar (the issuer) revokes — only the issuing tenant may:
curl -s -X POST http://localhost:8099/bridge/credential-revoke \
  -b bihar_cookies -H 'content-type: application/json' \
  -d '{"credential_id":"ds:bihar-labour:credential/…","reason":"registration cancelled"}'

# Maharashtra verifies again → now rejected:
# { "verified": false, "signature_valid": true, "revoked": true, "reason": "revoked", … }
```

This is what makes cross-state verification trustworthy: **a signature proves it was issued; revocation and
expiry prove whether it is *still* valid.**

---

## What must be true

For any cross-agency credential check to be sound:

1. **Same network.** Both agencies are participants of one network — one trust root, so the issuer's key is
   discoverable and verifiable.
2. **A governed credential type.** Both sides agree on what `credential.bocw_registration` *means* (a governed
   noun). You can only issue/require a governed type.
3. **The issuer has a steward key.** Signing uses the issuer tenant's Vault Ed25519 steward key; verifiers trust
   its **published** public key from the CA-signed directory.
4. **You can resolve the person.** The `holder` on the credential must be *the same person* applying in the
   destination state. Matching a migrant to their home-state identity is **the developer's responsibility** and
   the genuinely hard part — see limits below.
5. **Consent to present.** The holder presents their own credential (consent is the act of presenting); personal
   data crosses only by the person's action.
6. **Validity, not just authenticity.** Gate on `verified` (signature + not-revoked + not-expired), never on
   `signature_valid` alone.

---

## Current limits (reference-grade — read before you ship)

- **Cross-state identity resolution is not solved for you.** The platform verifies *a credential*; it does not
  match *a person* across two states' registries. You must resolve the migrant to the correct `holder`
  identity (e.g. via a national id) before issuing or requiring a credential. This is the main design work in a
  real deployment, not the transport.
- **Same-network / co-located today.** Issuer and verifier tenants must be on the same network deployment.
  Two states on **separate nodes** need the signed cross-node relay, which is not yet built.
- **The reference credential store is in-memory.** In the reference network, offers + revocation status live in
  memory and reset on a network restart (the holder's *accepted* copy in their own tenant is durable). A
  persistent store is a production step.
- **Revocation is a status lookup by id.** `verify` checks revocation against the network that holds the
  credential's record; if that network doesn't know the id, it returns `revocation_checked:false` and you get
  signature-only assurance. A published, portable status list (so any verifier can check offline) is a later
  step.
- **No selective disclosure.** The whole credential is presented; you can't reveal only `trade` while hiding
  `name` yet. Selective disclosure / ZK is not built.
- **Envelopes aren't sealed.** Presented credentials aren't encrypted in transit beyond transport TLS
  (X25519 sealing is pending). Fine for a pilot; not for sensitive personal data at scale.

> Related: [Interaction](/developer/deep-dives/interaction/) (how requests + receipts work),
> [Data Ownership & Consent](/developer/deep-dives/ownership-and-consent/) (who owns a record and how sharing is
> consented), and [Participants](/developer/deep-dives/participants/) (identity + roles on the network).
