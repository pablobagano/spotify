# Lyric-Driven Spotify Recommendations

A portfolio application that builds an ordered playlist from an activity, a genre, preferred artists, and a curated lyric excerpt. It ranks a cached, offline-enriched track catalog locally, previews the result without login, and optionally saves it to the user's Spotify account.

## Status

The project is currently in the offline catalog-acquisition phase.

Completed:

- Retrieved and saved the provider's available genre-seed payload.
- Selected SQLite as the development database.
- Added a shared SQLite database helper.
- Added repeatable schema initialization.
- Created the `genres` table.
- Imported 768 genre seeds idempotently.

Next milestone:

- Define the ten recommendation request payloads.
- Download and inspect their raw responses.
- Create and populate the recommendation catalog tables.

## Acquisition workflow

Raw provider responses are saved under `data/payload/` before their structures are interpreted or imported.

Initialize the database:

```bash
uv run python -m spotify_app.init_database
```

Retrieve the genre-seed payload:

```bash
uv run python -m spotify_app.get_genres
```

Import genres:

```bash
uv run import-genres
```

## Documents

- `lyric_recommendation_specification.md` — system architecture, progressive narrowing, ranking, interfaces, and acceptance criteria.
- `DEVELOPER_SEQUENCE_FLOW.md` — phased implementation plan and progress tracker.
- `src/spotify_app/recommendation_params.md` — recommendation endpoint parameters and supported ranges.
- `ADDITIONAL_APIs_FUNCTIONAL_FLOW.md` — exploratory alternative architecture; not part of the approved MVP.

## Tooling

- Python 3.12
- uv
- SQLite
- Requests
