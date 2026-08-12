# Wave 22 — Target Mac UAT

## Objective

Certify real human/native behavior on the target Mac using the exact Wave 21 baseline first. Wave 22 is not a feature wave.

Certified baseline:

- App13 version: `0.5.5a1`
- Exact source ZIP: `BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip`
- SHA-256: `d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861`
- Engineering: `472/472 PASS`, `115 modules`, `UX 19/19 PASS`
- R22 expected state: `PHYSICALLY_UNBOUND`

The first Mac execution must use the unmodified certified Wave 21 source. If a reproducible UAT defect appears:

1. record `FAIL` or `BLOCKED` with concrete evidence;
2. create a P0–P3 defect;
3. make the smallest justified fix;
4. add regression coverage;
5. create a new candidate and SHA-256;
6. retest with fresh evidence and full regression.

Never overwrite or redefine the certified Wave 21 baseline.

## One-command entry

Put the exact ZIP in Downloads, Desktop, Documents, or next to the repository and run:

```bash
bash RUN_WAVE22_MAC_UAT.command
```

The launcher verifies the archive, imports it strictly, creates/preserves local UAT status, displays the current gate, installs the isolated UAT kit, and opens App13.

## Manual import path

```bash
python3 scripts/import_wave21_release.py /path/to/BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip --dry-run
python3 scripts/import_wave21_release.py /path/to/BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip
./scripts/wave22_mac_preflight.sh /path/to/BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip
```

## CORE_UAT

Execute with a real operator and fresh evidence:

- `CORE-007` — Campaign → Content → CRM → Inbox without developer assistance.
- `CORE-008` — understand state, exercise a safe error, recover, and locate the next action.
- `CORE-009` — verify approvals, budget limits, kill switches, and non-bypassable Paid Media / Automation / Autopilot controls without live side effects.

The synthetic CRM task may be used where the certified guide allows it. Record `PASS`, `FAIL`, or `BLOCKED` in the integrated UAT form with a concrete operator note and evidence reference.

CORE gate requires:

- CORE-007/008/009 `PASS` with fresh evidence;
- zero open P0/P1 defects;
- any P2/P3 risk acceptance must have independent actor + rationale;
- independent human `CORE_UAT` signature.

## STANDALONE_MAC_UAT

After CORE_UAT passes:

- `MAC-001` — native install, startup, and restart on the target Mac.
- `MAC-002` — Security.framework helper, Keychain/vault write, credential rotation/revocation, and guided recovery; no secret may enter evidence.
- `MAC-003` — guarded upgrade, launchd fallback, crash-safe recovery, and rollback to a previously verified release.

Target Mac gate requires:

- MAC-001/002/003 `PASS` with fresh evidence;
- release/evidence tied to the exact candidate SHA;
- zero open P0/P1 defects;
- independent `STANDALONE_MAC_UAT` signature;
- evidence bundle exported and integrity checked.

## Machine-readable gate

The local state file is intentionally excluded from Git:

```text
uat-evidence/WAVE22_UAT_STATUS.json
```

Evaluate progress at any point:

```bash
python3 scripts/evaluate_wave22_gate.py
```

Expected progression:

1. `IMPORT_EXACT_WAVE21`
2. `CORE_UAT`
3. `STANDALONE_MAC_UAT`
4. `BINARIO_R22_UAT`

`CONTROL_POLICY_REPAIR` means the evaluator found drift or a Wave 22 policy violation.

## Evidence closeout

Guard evidence before sharing:

```bash
python3 scripts/wave22_evidence_guard.py /path/to/evidence
```

Then package it:

```bash
python3 scripts/package_wave22_evidence.py /path/to/evidence \
  --status-json uat-evidence/WAVE22_UAT_STATUS.json
```

The bundle contains the evidence, per-file hashes, guard output, certified baseline, scenario catalog, UAT status, CRC-checked ZIP, and an external SHA-256 sidecar. Packaging does not create or imply a human UAT signature.

## Out of scope for Wave 22

- physical R22 binding;
- production/live provider credentials;
- real ad spend;
- Production Sign-Off;
- large product features unrelated to a reproducible UAT defect.

Wave 22 closes with R22 still `PHYSICALLY_UNBOUND` and providers still blocked. Only then may the process advance to physical R22 / `BINARIO_R22_UAT`.
