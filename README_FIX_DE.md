# Fix für `test stub only`

Der Workflow bricht ab, weil im Repository `okx_market_data.py` noch die lokale Test-Stub-Datei steht. Diese Datei ersetzt sie durch einen echten **öffentlichen, nur lesenden** OKX-Kerzendatenabruf. Es werden keine API-Schlüssel, Wallets oder Order-Endpunkte verwendet.

## Einbau
1. Öffne `roepckie-source/polymarket-btc-paper-trader` auf GitHub.
2. Öffne die Datei `okx_market_data.py` im Repository.
3. Ersetze den vollständigen Dateiinhalt durch die Datei `okx_market_data.py` aus diesem Paket und committe die Änderung auf `main`.
4. Prüfe `okx_paper_config.py`: `INSTRUMENT` sollte `BTC-USDT` oder `BTC/USDT`, `BAR` sollte `5m` und `CANDLE_LIMIT` eine ganze Zahl zwischen 1 und 300 sein. Die Funktion nimmt diese vorhandenen Konfigurationswerte entgegen.
5. Starte zuerst die Unit Tests. Danach den Workflow `OKX BTC Spot Paper Check - 2 Hours` manuell.

**Wichtig:** Keine State-/Trade-Dateien löschen oder zurücksetzen. Wenn `okx_paper_state.json` bereits `halted: true` enthält, bleibt der Bot aus Sicherheitsgründen angehalten; diesen Halt nicht automatisch löschen. Zuerst Zustand und Ursache manuell prüfen.

Die Datei verwendet ausschließlich den öffentlichen OKX-Market-Candles-Endpunkt und filtert nicht abgeschlossene Kerzen heraus. Ein echter 2-Stunden-Lauf ist erst bestätigt, wenn der GitHub-Workflow nach dieser Änderung tatsächlich durchläuft.
