# Wave 22 — Target Mac UAT

## Objetivo

Certificar comportamiento humano y nativo sobre el **Mac objetivo**, usando primero la release Wave 21 exacta `0.5.5a1` (`d241696f…b441861`). Wave 22 no es una wave de features.

## Regla de baseline

La primera ejecución UAT debe hacerse sobre el ZIP certificado sin modificación. Si aparece un defecto reproducible:

1. registrar FAIL/BLOCKED + evidencia;
2. abrir defecto P0–P3;
3. hacer el cambio mínimo;
4. añadir prueba de regresión;
5. generar nuevo candidato y SHA;
6. repetir el escenario afectado con evidencia fresca y ejecutar regresión completa.

Nunca se sobrescribe ni se redefine la Wave 21 certificada.

## Fase A — recuperar fuente exacta

```bash
python3 scripts/import_wave21_release.py /ruta/BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip --dry-run
python3 scripts/import_wave21_release.py /ruta/BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip
```

Criterio: SHA-256 exacto + ZIP CRC PASS. La fuente queda bajo `app/`; la procedencia queda en `provenance/WAVE21_IMPORT.json`.

## Fase B — preflight del Mac

```bash
./scripts/wave22_mac_preflight.sh /ruta/BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip
```

Criterio: macOS real, Python disponible, headroom mínimo, SHA exacto e instalador UAT localizable.

## Fase C — CORE_UAT humano

Ejecutar el kit existente de Wave 21 y completar realmente:

- `CORE-007`: Campaign → Content → CRM → Inbox sin asistencia del desarrollador.
- `CORE-008`: navegación, diagnóstico, error seguro y recuperación.
- `CORE-009`: approvals, límites de presupuesto, kill switches y controles no-bypassables.

Usar el formulario integrado de evidencia. Preferir la CRM Task sintética `SAFE_CORE_UAT_ACTION` donde corresponda. No marcar PASS por inspección o memoria.

### Gate CORE

- CORE-007/008/009 = PASS con evidencia humana fresca.
- 0 defectos P0/P1 abiertos.
- P2/P3 solo pueden quedar aceptados con segundo actor + rationale.
- UAT firmado por actor independiente del operador principal.

## Fase D — STANDALONE_MAC_UAT

Completar:

- `MAC-001`: instalación exacta, startup y restart limpios.
- `MAC-002`: helper Security.framework/Keychain, escritura segura, rotación/revocación y recuperación guiada.
- `MAC-003`: upgrade guardado, fallback de launchd, crash recovery y rollback a release previamente verificada.

### Gate Target Mac

- MAC-001/002/003 = PASS con evidencia.
- Release instalada y evidencia ligadas al SHA exacto probado.
- 0 P0/P1 abiertos.
- UAT del target Mac firmado por actor independiente.
- Evidence bundle exportado e íntegro.

## Fuera de alcance de Wave 22

- binding físico R22;
- credenciales/provider live;
- gasto publicitario real;
- Production Sign-Off;
- features grandes no justificadas por defectos UAT.

## Siguiente gate

Solo después de cerrar Wave 22: **integración física R22 / BINARIO_R22_UAT**. El estado esperado al cerrar esta wave sigue siendo `R22 = PHYSICALLY_UNBOUND` y provider live bloqueado.
