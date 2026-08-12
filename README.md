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

Coloca el ZIP exacto en `Descargas`, `Escritorio`, `Documentos` o junto al kit de control y ejecuta:

```bash
bash RUN_WAVE22_MAC_UAT.command
```

El launcher verifica primero la integridad del Mac Control Kit cuando existe `CONTROL_KIT_MANIFEST.json`; después localiza y valida el ZIP Wave 21, rechaza mezclas de fuente, importa con provenance, inicializa el estado UAT gobernado, muestra el gate actual, instala el kit aislado y abre App13.

La primera UAT usa datos aislados. No debe usar el data dir productivo.

## Estado UAT: no editar JSON a mano

El estado humano vive fuera de Git en:

```text
uat-evidence/WAVE22_UAT_STATUS.json
```

Inicializar/consultar:

```bash
python3 scripts/wave22_uat_operator.py init
python3 scripts/wave22_uat_operator.py show
python3 scripts/evaluate_wave22_gate.py
```

Registrar un PASS real:

```bash
python3 scripts/wave22_uat_operator.py record CORE-007 PASS \
  --actor "OPERADOR" \
  --evidence "evidence/CORE-007.json" \
  --note "Campaign → Content → CRM → Inbox completado sin ayuda de desarrollo"
```

Registrar un fallo reproducible:

```bash
python3 scripts/wave22_uat_operator.py defect-open W22-001 P1 CORE-007 \
  --actor "OPERADOR" \
  --summary "Descripción reproducible del defecto"

python3 scripts/wave22_uat_operator.py record CORE-007 FAIL \
  --actor "OPERADOR" \
  --evidence "evidence/CORE-007-fail.json" \
  --note "Qué ocurrió y cómo reproducirlo" \
  --defect-id W22-001
```

Después de corregir y retestear:

```bash
python3 scripts/wave22_uat_operator.py defect-verify W22-001 \
  --actor "REVISOR" \
  --resolution "Corrección aplicada y verificada" \
  --evidence "evidence/W22-001-retest.json"
```

Firma independiente — el firmante debe ser distinto de los operadores del perfil:

```bash
python3 scripts/wave22_uat_operator.py sign core --actor "SEGUNDO_ACTOR"
python3 scripts/wave22_uat_operator.py sign mac --actor "SEGUNDO_ACTOR_MAC"
```

Con P2/P3 abiertos se exige además `--rationale "..."`. P0/P1 abiertos bloquean la firma. Cualquier re-test CORE o cambio de defectos invalida las firmas downstream para evitar aceptación obsoleta.

## Orden de gates

1. `CORE-007` — Campaign → Content → CRM → Inbox.
2. `CORE-008` — navegación, diagnóstico, error seguro y recuperación.
3. `CORE-009` — approvals, budget limits, kill switches y controles no-bypassables.
4. Firma independiente de `CORE_UAT`.
5. `MAC-001` — instalación/startup/restart.
6. `MAC-002` — Security.framework/Keychain + credential recovery.
7. `MAC-003` — upgrade/crash recovery/rollback.
8. Firma independiente de `STANDALONE_MAC_UAT`.
9. Solo entonces queda habilitado `BINARIO_R22_UAT`.

Progresión machine-readable:

```text
IMPORT_EXACT_WAVE21 → CORE_UAT → STANDALONE_MAC_UAT → BINARIO_R22_UAT
```

El evaluador no confía en una cadena `SIGNED`: valida firma estructurada, evidencia actual, independencia del actor, inventario de defectos y aceptación de riesgo residual.

## Evidencia

Antes de compartir evidencia fuera del Mac:

```bash
python3 scripts/wave22_evidence_guard.py /ruta/a/evidencia --manifest /tmp/wave22-evidence-manifest.json
```

Para crear un bundle final ligado a hashes, baseline y estado UAT:

```bash
python3 scripts/package_wave22_evidence.py /ruta/a/evidencia \
  --status-json uat-evidence/WAVE22_UAT_STATUS.json
```

El bundle incluye evidencia, hashes por archivo, resultado del guard, baseline Wave 21, catálogo de escenarios, estado UAT, CRC y SHA-256 externo. **No firma UAT automáticamente.**

## Mac Control Kit

El workflow `Wave 22 Controls` publica `WAVE22_TARGET_MAC_CONTROL_KIT` con launcher, scripts y contratos necesarios para el Mac objetivo. El artifact no contiene App13: debe acompañarse del ZIP Wave 21 exacto.

El ZIP generado incluye `CONTROL_KIT_MANIFEST.json` y el launcher ejecuta `verify_wave22_control_kit.py` antes de hacer cualquier importación. La revisión de control-plane queda incluida en el manifest y cada archivo del kit queda ligado a SHA-256, tamaño y bit ejecutable.

Última revisión autocertificada de esta rama al escribir este README: `ce573d096358b02ee1991d53e6920b64d3a94b35`.

## Lo que sigue bloqueado

- R22 permanece físicamente `UNBOUND`.
- Providers live permanecen bloqueados.
- Production Sign-Off permanece bloqueado hasta UAT humana válida.
- Solo defectos reproducibles encontrados en UAT justifican cambios de producto en esta wave.

Documentación detallada: `docs/WAVE22_TARGET_MAC_UAT.md`, `docs/WAVE22_UAT_SCENARIOS.json` y `docs/WAVE22_UAT_STATUS_TEMPLATE.json`.
