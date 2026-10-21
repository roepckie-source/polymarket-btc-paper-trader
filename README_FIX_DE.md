OKX BTC SPOT PAPER BOT — SICHERHEITSFIX
======================================

Enthaltene Dateien:
- okx_spot_paper.py
- test_okx_spot_paper.py
- .github/workflows/okx-paper.yml

Einspielen ins Repository roepckie-source/polymarket-btc-paper-trader:
1. Dateien an genau diese Pfade kopieren/ersetzen.
2. NICHT okx_paper_state.json oder okx_paper_trades.csv löschen oder zurücksetzen.
3. Änderungen committen und pushen.
4. Erst den Workflow starten, wenn die Unit Tests grün sind. Der nächste Lauf bleibt PAPER ONLY.

Was korrigiert wurde:
- Sicherheitsstopp speichert Ursache und Zeitpunkt dauerhaft in State JSON.
- Alte State-Dateien werden weiter gelesen; bei alten halted=true-Dateien ohne Ursache wird ausdrücklich markiert, dass die ursprüngliche Ursache nicht mehr rekonstruierbar ist.
- Bei Lücken in Kerzenzeitstempeln wird der Cursor nicht vorgerückt; die genaue erwartete und empfangene Zeit wird protokolliert.
- Der Workflow bricht bei HALTED/RUNTIME-Fehler jetzt mit Fehlerstatus ab. Er kann nicht mehr durch ein einfaches `break` fälschlich als erfolgreicher Lauf enden.
- Die bestehende offene Paper-Position und bisherigen Trades werden nicht automatisch gelöscht oder zurückgesetzt.

Wichtig:
- Das Paket wurde gegen die vorhandene Unit-Test-Suite getestet (12 Tests bestanden; dafür wurden nur lokale Test-Stubs für die nicht mitgelieferten Konfigurations-/Marktdatenmodule verwendet).
- Das ist ein Patch-Paket, kein direkter Commit in GitHub. Es wurde kein Zugriff auf GitHub-Schreibfunktionen verwendet.
- Nach dem Einspielen muss zuerst ein grüner Unit-Test-Lauf bestätigt werden. Bei bestehendem halted=true bleibt der Bot absichtlich angehalten. Nicht manuell entsperren und keinen State zurücksetzen, bevor der gespeicherte Zustand geprüft wurde.
