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

## Estado actual

Wave 22 = **Target Mac UAT**. No abre features grandes. El orden de trabajo es:

1. importar/verificar la Wave 21 exacta;
2. ejecutar CORE_UAT humano en el Mac real;
3. corregir únicamente defectos reproducibles encontrados por UAT;
4. ejecutar STANDALONE_MAC_UAT;
5. mantener R22 físicamente `UNBOUND` y providers live bloqueados hasta sus gates propios;
6. preservar evidencia y trazabilidad para Production Sign-Off.

Los scripts y documentos de continuidad viven en la rama `wave22/target-mac-uat`.
