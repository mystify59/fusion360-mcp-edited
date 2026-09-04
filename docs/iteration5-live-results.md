# Iteration 5 live Fusion results

Date: 2026-09-04  
Fusion: Autodesk Fusion Personal, active document units mm  
Bridge: 0.6.0, 115 operations  
Branch: `codex/iteration-5-bridge`  
Pre-live commit: `22a5422`  
Dispatcher SHA-256: `53AF197F08D156F834967D855879D55563C7DAADFFB9E995F6E031B10FB8FA9F`  
Query-op SHA-256: `9B18B28B5CEC6441EE19EC6B8BF76B7BFED612AFAC1A146B7D5CBDFA29041DC3`

## Preflight and recovery

The original active document was an unsaved, unmodified `Untitled` design with zero bodies. Each pass created a second unsaved scratch document and was intended to close it without saving. No cloud checkpoint was created because `document.save_as` does not return a reopenable version identifier or recovery path.

The first successful functional pass exposed an ambiguous-cleanup defect: both documents were named `Untitled`, so name-based close targeted the wrong document and left the owned scratch open. Post-pass state inspection caught the three residual bodies. The active scratch was then closed without saving, leaving one original empty, unmodified document. The harness now closes the active scratch and verifies the restored document has zero bodies and `is_modified=false`.

## Final bounded pass

Command:

```powershell
& ./.venv/Scripts/python.exe scripts/livetest.py --iteration5
```

Result: **19 passed, 0 failed**.

| Case | Evidence | Status |
|---|---|---|
| Construction-plane chain | Plane index `0` accepted by `sketch.circle`; downstream loft produced one body and timeline state | pass |
| Joined twin-eye link | Web plus two eyes joined; resulting design contained link plus loft body | pass |
| Repeated eye holes | Targeted `query.body_info` retained the link name and operative ID across both cuts; edge count became 16 | pass |
| Edge enumeration | 16 edges returned with topology snapshot, midpoint, length, curve type, and adjacency | pass |
| Selective transition fillet | Only edge `4` resolved and received a 2 mm radius; per-edge evidence reported `resolved` | pass |
| Deliberate invalid selection | Edge `9999` refused; wire response exposed rollback evidence after the bridge serialization fix | pass |
| Parametric proof | Extrusion model parameter `d13` changed from 10 mm to 18 mm; measured body height changed from 10.0 mm to 18.0 mm | pass |
| Material evidence | Effective material `Steel`, density 7.85 g/cm³, body assignment scope, verified mass 70.5407 g | pass |
| Cleanup | Active scratch closed without saving; original `Untitled` restored with zero bodies and unmodified state | pass |

## Conditional extensions

- Exact body deletion is exposed and its resulting state is now independently reported by the mutation envelope.
- Exact sketch, feature, and construction-entity cleanup is not exposed. No broader cleanup tool was added.
- Save and Save As remain usable manual recovery mechanisms, but the bridge does not return a reopenable version identifier. No checkpoint API was added.
- Edge indices are valid only for the returned topology snapshot. A topology-changing feature requires fresh enumeration before another selective operation.

The live pass proves tool execution and state reporting; it does not establish structural adequacy, fatigue life, manufacturability, or certification.
