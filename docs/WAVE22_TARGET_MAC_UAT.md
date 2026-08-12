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

## Preferred entry: self-verifying Mac Control Kit

The `Wave 22 Controls` workflow publishes `WAVE22_TARGET_MAC_CONTROL_KIT`. Its internal ZIP contains `CONTROL_KIT_MANIFEST.json`, which binds the exact control-plane revision and every shipped file to SHA-256, size and executable-bit expectations.

When the extracted kit has that manifest, `RUN_WAVE22_MAC_UAT.command` verifies the kit before importing or launching App13. A modified or incomplete kit is blocked.

Put the exact Wave 21 ZIP in Downloads, Desktop, Documents, or next to the kit and run:

```bash
bash RUN_WAVE22_MAC_UAT.command
```

The launcher then:

1. verifies the extracted control kit when a manifest is present;
2. verifies Wave 21 SHA-256 and ZIP CRC;
3. rejects mixed or unproven source state;
4. imports Wave 21 under `app/` with provenance;
5. initializes/preserves governed local UAT state;
6. displays the current machine-readable gate;
7. installs the isolated UAT kit;
8. opens App13.

## Manual import path

```bash
python3 scripts/import_wave21_release.py /path/to/BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip --dry-run
python3 scripts/import_wave21_release.py /path/to/BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip
./scripts/wave22_mac_preflight.sh /path/to/BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip
```

## Governed local state

Do not hand-edit the UAT JSON. Use:

```bash
python3 scripts/wave22_uat_operator.py init
python3 scripts/wave22_uat_operator.py show
```

The state file is local and intentionally excluded from Git:

```text
uat-evidence/WAVE22_UAT_STATUS.json
```

Every recorded scenario requires actor, evidence and operator note. A `FAIL` or `BLOCKED` also requires an existing OPEN defect for the same scenario.

Example PASS:

```bash
python3 scripts/wave22_uat_operator.py record CORE-007 PASS \
  --actor "OPERADOR" \
  --evidence "evidence/CORE-007.json" \
  --note "Primary operator workflow completed without developer assistance"
```

Example defect path:

```bash
python3 scripts/wave22_uat_operator.py defect-open W22-001 P1 CORE-007 \
  --actor "OPERADOR" \
  --summary "Reproducible failure summary"

python3 scripts/wave22_uat_operator.py record CORE-007 FAIL \
  --actor "OPERADOR" \
  --evidence "evidence/CORE-007-fail.json" \
  --note "Observed behavior and reproduction context" \
  --defect-id W22-001
```

After a fix and fresh retest:

```bash
python3 scripts/wave22_uat_operator.py defect-verify W22-001 \
  --actor "REVISOR" \
  --resolution "Fix verified" \
  --evidence "evidence/W22-001-retest.json"
```

Any scenario re-record or defect lifecycle change invalidates affected/downstream signatures so stale acceptance cannot survive new evidence.

## CORE_UAT

Execute with a real operator and fresh evidence:

- `CORE-007` — Campaign → Content → CRM → Inbox without developer assistance.
- `CORE-008` — understand state, exercise a safe error, recover, and locate the next action.
- `CORE-009` — verify approvals, budget limits, kill switches, and non-bypassable Paid Media / Automation / Autopilot controls without live side effects.

The synthetic CRM task may be used where the certified guide allows it.

CORE gate requires:

- CORE-007/008/009 `PASS` with fresh evidence;
- zero open P0/P1 defects;
- independent human signer distinct from scenario operator(s);
- any open P2/P3 requires explicit risk-acceptance rationale;
- a structured `CORE_UAT` signature whose evidence references still match the current scenario records.

Sign only after review:

```bash
python3 scripts/wave22_uat_operator.py sign core --actor "SEGUNDO_ACTOR"
```

With residual P2/P3:

```bash
python3 scripts/wave22_uat_operator.py sign core \
  --actor "SEGUNDO_ACTOR" \
  --rationale "Documented reason this residual risk does not block the gate"
```

## STANDALONE_MAC_UAT

Only after CORE_UAT is signed:

- `MAC-001` — native install, startup, and restart on the target Mac.
- `MAC-002` — Security.framework helper, Keychain/vault write, credential rotation/revocation, and guided recovery; no secret may enter evidence.
- `MAC-003` — guarded upgrade, launchd fallback, crash-safe recovery, and rollback to a previously verified release.

Target Mac gate requires:

- MAC-001/002/003 `PASS` with fresh evidence;
- release/evidence tied to the exact candidate SHA;
- zero open P0/P1 defects;
- independent structured `STANDALONE_MAC_UAT` signature;
- evidence bundle exported and integrity checked.

```bash
python3 scripts/wave22_uat_operator.py sign mac --actor "SEGUNDO_ACTOR_MAC"
```

## Machine-readable gate

Evaluate progress at any point:

```bash
python3 scripts/evaluate_wave22_gate.py
```

Expected progression:

1. `IMPORT_EXACT_WAVE21`
2. `CORE_UAT`
3. `STANDALONE_MAC_UAT`
4. `BINARIO_R22_UAT`

The evaluator does not trust a plain `SIGNED` flag. It validates baseline binding, scenario completeness, evidence metadata, defect-record/counter consistency, independent signer metadata, current signature-to-evidence binding, P2/P3 rationale, R22 state and provider state.

`CONTROL_POLICY_REPAIR` means drift or a Wave 22 policy violation was found.

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

The bundle contains evidence, per-file hashes, guard output, certified baseline, scenario catalog, UAT status, CRC-checked ZIP, and an external SHA-256 sidecar. Packaging does not create or imply a human UAT signature.

## Out of scope for Wave 22

- physical R22 binding;
- production/live provider credentials;
- real ad spend;
- Production Sign-Off;
- large product features unrelated to a reproducible UAT defect.

Wave 22 closes with R22 still `PHYSICALLY_UNBOUND` and providers still blocked. Only then may the process advance to physical R22 / `BINARIO_R22_UAT`.
