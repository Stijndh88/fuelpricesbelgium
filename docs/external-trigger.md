# Externe trigger voor de dagelijkse update

GitHub start geplande runs soms uren te laat of helemaal niet. Een gratis externe planner kan
de update daarom elke dag rond 10:00 Belgische tijd zelf starten. De bestaande :17/:47-schema's
blijven als reserve.

De planner roept `workflow_dispatch` aan met `only_if_missing: true`. De poort slaat de run over
als het nog geen 10:00 in Brussel is of als `data/advice.json` al van vandaag is, dus dubbel
aanroepen kost niets.

## Instellen met cron-job.org (gratis)

1. GitHub, Settings, Developer settings, Fine-grained personal access tokens, Generate new token.
   Resource owner: Stijndh88. Repository access: Only select repositories, alleen
   `fuelpricesbelgium`. Permissions, Repository: Actions = Read and write (Metadata blijft
   Read-only). Looptijd: 1 jaar. Kopieer het token (begint met `github_pat_`).
2. Maak een gratis account op https://cron-job.org en kies Create cronjob.
3. URL: `https://api.github.com/repos/Stijndh88/fuelpricesbelgium/actions/workflows/daily-update.yml/dispatches`
4. Schedule: Custom, dagelijks om 10:05, tijdzone Europe/Brussels (zo klopt het ook in de winter).
   Voeg gerust een tweede entry toe om 11:05 als reserve.
5. Advanced: Request method POST. Headers:
   - `Authorization: Bearer <je token>`
   - `Accept: application/vnd.github+json`
   - `X-GitHub-Api-Version: 2022-11-28`
   - `User-Agent: cron-job.org`
   Body: `{"ref":"main","inputs":{"only_if_missing":"true"}}`
6. Sla op en kies "Test run". Antwoord 204 is goed. Controleer in de Actions-tab dat er een run
   "Daily price update" (workflow_dispatch) staat.

Het token staat alleen bij cron-job.org en geeft alleen Actions-rechten op deze ene repo.
