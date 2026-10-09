---
id: BUG-0241
title: guion_adopt cierra el nodo «ordenes» de un ARMA(0,0) como ARMA(1,0) — cuenta el relleno AR(1) fijo a cero del .inp
status: fixed
severity: medium
component: guion
found_in: 0.2.3.dev0 (+ arreglos sin commit de BUG-0225…0231)
fixed_in: 0.2.3.dev0 (sin commit)
reported: 2026-10-09
reporter: David / Claude — análisis guiado de IPC_DE (P02)
tags: [guion, ordenes, bug-0229]
references:
  - src/art/mcp_server.py guion_adopt
  - BUG-0216 (_orden_efectivo), BUG-0229
---

## Summary

Al adoptar el paseo aleatorio con deriva de IPC_DE (ARIMA(0,1,0) con μ), el nodo `ordenes`,
que estaba pendiente por empate, se cerró como «ARMA(1,0) — **corrige la propuesta**». Pero lo
adoptado ERA la propuesta, ARMA(0,0).

## Impact

El mapa del guion y su HTML registran un orden que no se estimó, y además marcan como
discrepancia con la propuesta una decisión que coincide con ella.

## Reproduction

`tests/test_bug_0241_adopt_arma00.py` (repro: `BUG-0241-repro/IPC_DE.inp`).

## Root cause

El `.inp` de un ARMA(0,0) lleva el relleno `1 1 / 0.0 0` (un AR(1) fijo a cero). El spec del
guion lo guarda como `p=1` con `ar_free=[[False]]`. `guion_adopt` leía `spec["p"]` sin mirar
las banderas.

## Fix

En `guion_adopt`, un factor con todas sus banderas fijas no cuenta como orden estimado
(p o q = 0). El guion de IPC_DE se corrigió a mano (n5).

## Validation

Pasa `tests/test_bug_0241_adopt_arma00.py`.
