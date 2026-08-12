# Binario Marketing & Growth IA — App13

Repositorio canónico de recuperación y continuidad de **MKTG-APP**.

## Baseline certificado

La fuente de partida obligatoria para Wave 22 es:

- Release: `BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip`
- Runtime: `0.5.5a1`
- SHA-256: `d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861`
- Estado de ingeniería: `472/472 PASS`, `115/115 módulos`, `UX 19/19 PASS`
- Integración: `APP13_INTERNAL_BOUND_R22_UNBOUND`

**No se debe reconstruir Wave 21 de memoria ni desde una wave anterior.** La importación de código se acepta solamente si el ZIP coincide byte-a-byte con el SHA-256 anterior.

## Wave 22 — ejecución en el Mac objetivo

Coloca el ZIP exacto en `Descargas`, `Escritorio`, `Documentos` o dentro de este repositorio y ejecuta:

```bash
bash RUN_WAVE22_MAC_UAT.command
```

El launcher:

1. localiza el ZIP exacto;
2. valida SHA-256 y CRC;
3. rechaza mezclas con otra fuente;
4. importa Wave 21 bajo `app/` con provenance;
5. valida macOS y los entrypoints canónicos del UAT kit;
6. crea/preserva `uat-evidence/WAVE22_UAT_STATUS.json` fuera de Git;
7. muestra el gate actual de forma machine-readable;
8. instala el kit aislado;
9. abre App13 para iniciar `CORE_UAT`.

La primera UAT usa datos aislados. No debe usar el data dir productivo.

## Orden de gates

1. `CORE-007` — Campaign → Content → CRM → Inbox.
2. `CORE-008` — navegación, diagnóstico, error seguro y recuperación.
3. `CORE-009` — approvals, budget limits, kill switches y controles no-bypassables.
4. Firma independiente de `CORE_UAT`.
5. `MAC-001` — instalación/startup/restart.
6. `MAC-002` — Security.framework/Keychain + credential recovery.
7. `MAC-003` — upgrade/crash recovery/rollback.
8. Firma independiente de `STANDALONE_MAC_UAT`.
9. Solo entonces queda habilitado el siguiente gate: `BINARIO_R22_UAT`.

Solo los defectos reproducibles encontrados en UAT justifican cambios de producto en esta wave.

## Consultar estado real

```bash
python3 scripts/evaluate_wave22_gate.py
```

Estados esperados, en orden:

- `IMPORT_EXACT_WAVE21`
- `CORE_UAT`
- `STANDALONE_MAC_UAT`
- `BINARIO_R22_UAT`

Si detecta drift del baseline, R22 enlazado prematuramente, provider live habilitado o estado inconsistente, devuelve `CONTROL_POLICY_REPAIR`.

## Evidencia

Antes de compartir evidencia fuera del Mac:

```bash
python3 scripts/wave22_evidence_guard.py /ruta/a/evidencia --manifest /tmp/wave22-evidence-manifest.json
```

Un resultado `BLOCKED` impide compartir el material hasta retirar credenciales o secretos. El guard no modifica la evidencia.

Para crear un bundle final ligado a hashes, baseline y estado UAT:

```bash
python3 scripts/package_wave22_evidence.py /ruta/a/evidencia \
  --status-json uat-evidence/WAVE22_UAT_STATUS.json
```

El resultado incluye:

- evidencia original;
- manifest de hashes por archivo;
- resultado del evidence guard;
- baseline Wave 21;
- catálogo Wave 22;
- estado UAT usado al empaquetar;
- ZIP CRC verificado;
- SHA-256 externo del bundle.

El bundle **no firma UAT automáticamente**. La autoridad continúa siendo humana e independiente.

## Lo que sigue bloqueado

- R22 permanece físicamente `UNBOUND`.
- Providers live permanecen bloqueados.
- Production Sign-Off permanece bloqueado hasta UAT humana.

Documentación detallada: `docs/WAVE22_TARGET_MAC_UAT.md`, `docs/WAVE22_UAT_SCENARIOS.json` y `docs/WAVE22_UAT_STATUS_TEMPLATE.json`.
