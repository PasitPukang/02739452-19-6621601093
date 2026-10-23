# Pokémon data dictionary

Grain: **one base species per National Pokédex ID, 1–151**. `pokemon` is the current merged view, not a history of game balance changes. SQLite is used only in unit tests; Docker dashboard queries PostgreSQL directly.

| Field | SQL type | Meaning / validation |
| --- | --- | --- |
| dex_id | integer PK | National Pokédex number, 1–151 |
| name | varchar(80) | Nonempty display name; never the dedup key |
| types | JSON array | 1–2 distinct current types from the 18-type vocabulary |
| hp, attack, defense, sp_attack, sp_defense, speed | integer | Base stat, 1–255; not EV/IV/level-dependent values |
| total | integer | Exact sum of the six base stats |
| source_names | JSON array | Sources that contributed to this successful load |
| source_urls | JSON object | Public evidence URLs, keyed by source |
| conflicts | JSON object | Different stat/type values retained per source; empty if all agree |
| updated_at | varchar(40) | UTC ISO-8601 timestamp of normalization |

`pokemon_observations`: composite key `(source, dex_id)`, JSON normalized payload and UTC `fetched_at`. Each source retains its last successfully loaded observation; a failed source's older observation is not falsely labelled as fetched in the new run.

`pokemon_runs`: primary key `run_id`, UTC start/end, `RUNNING/SUCCESS/PARTIAL/REJECTED/FAILED`, explicit demo parameters and quality summary.

`pokemon_source_runs`: key `(run_id, source)`, source status, count, start/end and diagnostic message. Errors contain source/technical messages, never credentials.

Normalization: PokéAPI `special-attack/defense` and Showdown `spa/spd` become `sp_attack/sp_defense`; type names become lower-case; HTML special forms and Showdown `forme` records are excluded. All three sources use the same canonical ID. A duplicate within one source is invalid, while the same ID across sources is merged with provenance.

Conflict policy: prefer PokéAPI, then Pokémon Database, then Showdown for stats/types. Prefer the Database display name where available. Preserve conflicts rather than average incomparable source values. Quality must pass for every observation and merged row, and there must be at least 100 distinct species before loading.
