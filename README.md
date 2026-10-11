# SunPower (TCL EMEA) — integrazione Home Assistant

Integrazione **non ufficiale** per gli impianti fotovoltaici **SunPower EMEA** gestiti
dall'app "SunPower" (backend TCL `*.tcljd.com`, datalogger e-linter / Sunsynk-Inteless).
Porta in Home Assistant gli stessi dati dell'app (FV, carico, rete, batteria, energia,
guadagni) senza hardware aggiuntivo, solo con le credenziali dell'app.

> ⚠️ Non ufficiale. Non è un prodotto SunPower/TCL. Ricostruisce l'API privata dell'app
> (login cifrato + richieste firmate) e può smettere di funzionare se TCL cambia l'API.
> Usala a tuo rischio, nessuna garanzia.

## Requisiti
- Account dell'app **SunPower** EMEA (login su `multi-eu-prod.tcljd.com`).
- Endpoint configurati per la regione **EU** (per altre regioni apri una issue).

## Installazione (HACS)
1. HACS → Custom repositories → aggiungi `https://github.com/picotto86/ha-sunpower-tcl` come **Integration**.
2. Installa "SunPower (TCL EMEA)" e riavvia Home Assistant.
3. Impostazioni → Dispositivi e servizi → Aggiungi integrazione → **SunPower (TCL EMEA)**.
4. Inserisci email, password e codice paese (es. `IT`). Gli impianti vengono rilevati da soli.

## Entità (per impianto)
Potenza FV / carico / rete / batteria (W), Batteria (%), Energia e Guadagno oggi/mese/anno,
Stato impianto, Inverter online. I sensori di energia sono compatibili con la dashboard Energia.

## Privacy
Le credenziali restano in Home Assistant e vengono usate solo verso i server SunPower/TCL.

## Licenza
MIT — vedi LICENSE.
