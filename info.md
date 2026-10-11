# SunPower (TCL EMEA)

Integrazione **non ufficiale** per il fotovoltaico **SunPower EMEA** (backend TCL).
Porta in Home Assistant gli stessi dati dell'app mobile — produzione, consumo, rete,
batteria, energia e guadagni — **senza hardware aggiuntivo**, solo con le credenziali dell'app.

## Configurazione
Dopo l'installazione: **Impostazioni → Dispositivi e servizi → Aggiungi integrazione →
SunPower (TCL EMEA)**. Inserisci email, password e codice paese (es. `IT`).
Gli impianti collegati all'account vengono rilevati automaticamente.

## Entità (per impianto)
- Potenza FV / carico / rete / batteria (W)
- Stato di carica batteria (%)
- Energia e guadagno di oggi / mese / anno
- Stato impianto, Inverter online

I sensori di energia sono compatibili con la **dashboard Energia** di Home Assistant.

## Note
- Integrazione **non ufficiale**, non supportata da SunPower/TCL: può interrompersi se il
  produttore cambia l'API.
- Al momento è configurata la regione **EU**. Per altre regioni apri una issue.
