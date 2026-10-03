# Lyric-Driven Spotify Recommendation System Specification

## 0. How to read this specification

This document separates two kinds of statement:

- **Agreed architecture**: structural decisions that implementation must follow (component boundaries, data flow, hard-versus-soft semantics, interaction order, interface contracts). Changing one requires revising this specification.
- **Provisional parameters**: numeric values and tunable settings (score weights, activity ranges, coverage thresholds, normalization bounds, diversity limits, playlist lengths). They are starting hypotheses. They are stored in versioned configuration, not hard-coded, and must be evaluated before being treated as reliable. Section 11 lists them.

Nothing here asserts external-provider capabilities, batch support, rate limits, pricing, or storage permissions that have not been verified. Where such facts matter, the specification says so and assigns verification to implementation step 1.

## 1. Objective and boundaries

Build a portfolio recommendation application that generates an ordered playlist from explicit user preferences: intended activity, favorite genre, preferred artists, and a curated lyric excerpt representing the user's current feeling. Each selection progressively narrows the available choices. Multiple songs may jointly seed a recommendation.

Use content-based weighted ranking. Do not use clustering. Begin with manually configured weights; a trained ranking model is outside the initial scope because labeled feedback is not yet available.

Rank a curated, cached candidate-track catalog locally. Spotify provides catalog identifiers and the playlist destination; it does not perform this application's ranking. Recommendation coverage is bounded by the curated catalog.

### 1.1 Architectural separation (agreed)

The system has three distinct layers. They must not be merged.

| Layer | Runs | Responsibility | Talks to external services? |
| --- | --- | --- | --- |
| **Offline enrichment** | Batch jobs, operator-triggered | Resolve Spotify identifiers, acquire audio features from the external provider, validate them, curate excerpts and descriptions, compute embeddings, persist everything to the catalog database. | Yes: external audio-feature provider (through its MCP client) and Spotify catalog endpoints. |
| **Shared backend (eligibility, choice retrieval, ranking)** | Per request | Read the catalog database; apply activity eligibility rules; compute available choices; rank and select candidates; produce previews with explanations. | **No.** Reads the database and versioned configuration only. |
| **Interfaces** | Per request | (a) Web application and (b) application-owned MCP server. Both validate inputs, call the shared backend functions, and format results. The web application also hosts the optional Spotify save flow. | Only the Spotify save flow, after user authorization. |

Consequences:

- Interactive narrowing and ranking never call the external audio-feature provider. If the provider is unavailable, previews still work for every enriched track.
- No live lyric retrieval, quote retrieval, audio-feature enrichment, or related-artist discovery occurs during generation.
- There are two unrelated MCP endpoints in the system. The **external provider's MCP server** is an upstream data source used only by offline enrichment (Section 5). The **application-owned MCP server** is a downstream, agent-facing interface over the shared backend (Section 8). Neither depends on the other.

## 2. User interaction order (agreed)

**activity → genre → preferred artists → lyric excerpt → ranking → preview → optional Spotify save**

1. **Activity.** Select the playlist purpose (for example work, workout, date, relaxation, or another configured activity). The activity's eligibility rules establish the initial eligible track pool (Section 6).
2. **Genre.** Select one genre from those the activity pool supports with sufficient coverage. Genre narrows the pool (hard filter in the MVP).
3. **Preferred artists.** Select one or more artists credited on tracks in the narrowed pool. Artists guide downstream choices and contribute an artist-affinity ranking signal; they **do not** restrict every recommended track to those artists.
4. **Lyric excerpt.** Choose one curated excerpt supported by the current eligible pool (Section 7.3). The MVP uses lyrics; poetry and quotations can be added later through a generalized text-source model.
5. **Ranking.** Generate the playlist from the eligible cached candidate pool (Section 9).
6. **Preview.** Show the ordered songs, short score-grounded explanations, evidence coverage, and any shortfall notice. No Spotify login is required.
7. **Optional Spotify save.** Only if the user clicks Save to Spotify: authenticate, authorize playlist creation, create and populate a private playlist, and return its link (Section 10).

## 3. Offline preparation order

1. Define supported activities, activity profiles (Section 6), genres, mood dimensions, and an initial curated track list.
2. Resolve tracks and artists to Spotify identifiers. Verify the recording/version, not merely its title.
3. Curate lyric excerpts and candidate-track semantic descriptions using sources permitted for the intended use; retain attribution and provenance.
4. Acquire audio features for seed and candidate tracks from the external provider through its MCP client (Section 5), subject to verified coverage and storage permissions.
5. Validate responses, store provider provenance, acquisition dates, and per-feature validation status, and flag missing or suspicious values.
6. Assign candidate-track mood scores and soft activity-suitability scores. Audio features alone do not supply lyrical meaning.
7. Precompute semantic embeddings using the same embedding model/version for excerpts and candidate-track descriptions.
8. Define audio normalization parameters, ranking weights, and diversity limits in versioned configuration.
9. Persist the catalog. Available choices are then computed from it at request time (Section 7); no static choice lists are published.

Provider freshness primarily affects catalog coverage and recording/version accuracy. Audio characteristics of an existing recording are generally stable. Do not assume a sample response proves provider availability or accuracy. Test representative tracks before depending on it.

## 4. Minimal relational data model

| Table | Core fields and purpose |
| --- | --- |
| genres | id, name, slug |
| artists | id, spotify_artist_id, name |
| artist_genres | artist_id, genre_id; many-to-many relationship |
| tracks | id, spotify_track_id, spotify_uri, title, release_year, recording_version, enabled |
| track_artists | track_id, artist_id, is_primary; supports collaborations and the primary-artist diversity rule |
| track_genres | track_id, genre_id; explicit track classification |
| lyric_excerpts | id, track_id, excerpt_text, attribution, source_reference, mood_scores, embedding, embedding_model_version, enabled |
| track_profiles | track_id, semantic_description, mood_scores, embedding, embedding_model_version, activity_scores |
| track_audio_features | track_id, one **nullable** column per stored feature (energy, danceability, acousticness, instrumentalness, speechiness, valence, tempo, loudness, duration_ms, key, mode, time_signature, liveness), feature_validation (per-feature status map), provider, provider_interface (e.g. the MCP tool name used), acquired_at, enrichment_run_id, record_status, raw_response (only if storage is permitted) |
| enrichment_runs | id, provider, started_at, finished_at, requested_count, succeeded_count, failed_count, notes |

Activity profiles, normalization parameters, ranking weights, and diversity limits live in versioned configuration (a file under version control or a configuration table). Every generated result records the configuration version(s) it used.

Store vectors and small score maps as JSON initially if the chosen database has no vector support. A vector database is unnecessary for a small curated catalog. Track lyric excerpts through track_id rather than assigning them only to artists. Use release_year instead of an ambiguous era_year.

Missing audio features are stored as NULL, never as 0 or any other sentinel number. A value that fails validation is treated as missing for eligibility and ranking, while the raw value and its failure reason remain available for inspection.

The selected excerpt's parent track is the default seed. Support an optional explicit seed-track selection with multiple track IDs. Do not silently turn every favorite artist's song into a seed. Artist preference and seed-track similarity are separate inputs.

## 5. Offline audio-feature enrichment (external provider)

Proposed provider: https://rapidapi.com/musicae-musicae-default/api/spotify-extended-audio-features-api, accessed through the provider's MCP client (the RapidAPI-hosted MCP server configured in `audio-feats-mcp.json`).

### 5.1 Scope and rules (agreed)

- Enrichment is an offline, operator-triggered job. It writes to the catalog database; request-time code only reads from it.
- Enrichment is resumable and idempotent per track: re-running a job skips tracks that already have a valid record unless a refresh is requested explicitly.
- Every stored record keeps the provider name, the interface used, the acquisition timestamp, the enrichment run ID, and per-feature validation status.
- Provider credentials are kept outside version control and are never exposed to the web client or the application-owned MCP server.
- The job's request pattern (one track per call or several per call), pacing, and retry policy are determined after step 1 verifies what the provider actually supports. Do not assume batch support, rate limits, or pricing.

### 5.2 Validation (agreed)

For each response, check at least:

- The returned track ID/URI matches the requested track.
- Each feature is present, numeric, and inside the range the provider documents or the validation step establishes (for example, a bounded feature outside its expected bounds, or a non-positive tempo, is flagged).
- Per-feature status is one of `valid`, `missing`, or `rejected` (with reason). Record-level status summarizes the result (for example `complete`, `partial`, `failed`).

Suspicious-but-plausible values (for example tempo values that may be half- or double-time) are flagged for review and are not silently corrected.

### 5.3 Fields

The supplied sample contains acousticness, danceability, energy, instrumentalness, speechiness, valence, tempo, loudness, duration_ms, key, mode, time_signature, liveness, id, and uri. Provider coverage, accuracy, pricing, and permitted caching remain unverified.

Start audio similarity and activity eligibility with energy, danceability, acousticness, instrumentalness, speechiness, valence, and tempo. Retain other fields for inspection without automatically giving them ranking weight or eligibility rules. Key is circular, so raw numeric distance between key IDs is inappropriate. Valence approximates musical positivity; it is not a label for nostalgia, grief, or longing.

### 5.4 Normalization

Normalize each ranked dimension onto a comparable [0, 1] scale. Use bounded values directly where they are already on [0, 1]; use a documented fixed tempo range with clipping for tempo (bounds are provisional). Save normalization parameters with a version in the ranking configuration. Do not recompute scaling per request or per catalog refresh without bumping the version.

## 6. Activity profiles and eligibility (agreed structure, provisional values)

### 6.1 Profile structure

Each supported activity has a configurable profile:

```yaml
activity_profiles_version: "<version>"
activities:
  workout:                        # example key; values below are placeholders
    label: "Workout"
    status: provisional           # provisional | evaluated
    rationale: "<hypothesis being tested>"
    constraints:                  # hard filters; only features listed here are filtered
      - feature: tempo
        scale: raw                # raw = provider units; tempo raw = BPM
        min: <number or omitted>
        max: <number or omitted>
        on_missing: exclude       # default; see 6.3
      - feature: energy
        scale: normalized         # value after the versioned normalization in 5.4
        min: <number or omitted>
        max: <number or omitted>
        on_missing: exclude
    min_genre_tracks: <integer>   # coverage threshold for offering a genre (provisional)
```

No numeric thresholds are defined by this specification. All ranges start as hypotheses with `status: provisional` and a written rationale, and they move to `evaluated` only after the scenario review in implementation step 6.

### 6.2 Constraint semantics

- **Only explicitly configured ranges are hard filters.** A feature not listed in an activity's `constraints` imposes no eligibility restriction for that activity, regardless of its value.
- **Supported constraint features** may include energy, danceability, acousticness, instrumentalness, speechiness, valence, and tempo. Adding other features requires an explicit configuration change and validation that the feature is meaningful as a hard filter.
- **Units are mandatory.** Each constraint declares `scale: raw` (provider-reported units; for tempo this means BPM) or `scale: normalized` (the value after the normalization configuration in Section 5.4, whose version is pinned alongside the profile). A configuration without a declared scale is invalid and must fail validation at load time.
- **Boundaries are inclusive**: a track is within range when `min <= value <= max`. Either bound may be omitted to form a one-sided range. A profile with `min > max` is invalid.
- A track is activity-eligible when it is enabled and satisfies every configured constraint for that activity.
- Ranges are hypotheses about what tends to suit an activity in this catalog, not universal musical rules. Explanations shown to users must not present them as facts about music.

### 6.3 Missing required features

- Missing or rejected values are never converted to zero, a midpoint, or any imputed number.
- By default (`on_missing: exclude`), a track missing a feature required by a hard constraint is **ineligible** for that activity.
- A different behavior is allowed only through an explicit, documented fallback on that specific constraint (for example `on_missing: ignore`, meaning the constraint is skipped for tracks lacking the feature). Any fallback must have a rationale in the profile, and results must report how many candidates passed via a fallback.
- Choice-retrieval responses report how many tracks were excluded for missing required features, so catalog gaps are visible.

### 6.4 Hard eligibility versus soft activity suitability

- **Hard eligibility** (this section) decides whether a track may appear at all for the activity.
- **Soft activity suitability** (`activity_scores` in `track_profiles`) is a separate ranking component (Section 9). It may draw on audio features and curated assessments, and it only orders eligible tracks.
- Changing the soft score never changes eligibility, and passing eligibility never implies a high soft score. The previous rule that a "minimum suitability score" controls option availability is replaced by the explicit constraint ranges above.

## 7. Progressive narrowing (agreed)

### 7.1 Pool definitions

| Pool | Definition |
| --- | --- |
| P_activity | Enabled tracks satisfying every hard constraint of the selected activity (Section 6). |
| P_genre | Tracks in P_activity classified with the selected genre (track_genres). |
| Candidate pool | P_genre. Preferred artists and the excerpt do not remove candidates from it. |

### 7.2 Available choices

All choices are computed at request time from the actual eligible tracks; no static lists are used.

- **Activities**: configured activities whose P_activity is non-empty.
- **Genres**: genres with at least `min_genre_tracks` (provisional) tracks in P_activity.
- **Artists**: artists credited on at least one track in P_genre.
- **Excerpts**: enabled excerpts whose parent track is in P_genre. Excerpts from tracks credited to the selected artists are listed first and flagged; this is how artists guide the excerpt step without restricting it.

Each option is returned with the eligible track count it supports.

### 7.3 Invalidating downstream selections

- Changing an earlier selection recomputes all downstream choices.
- Downstream selections that are still valid in the new pool are kept. Selections that are no longer valid (a genre below the threshold, an artist with no tracks in P_genre, an excerpt whose parent track left P_genre) are cleared, and the user is told which were cleared.
- The backend validates every selection again in `generate_playlist`. Stale selections produce a structured error; they are never dropped silently.

### 7.4 Small and empty pools

- If the candidate pool cannot fill the requested length after diversity limits, return a shorter playlist with an explicit shortfall notice (requested, returned, reason), or ask the user to broaden a named selection.
- If a pool is empty at any step, return a structured empty-pool result naming the step responsible.
- Never silently relax a hard constraint, widen a range, apply an undeclared fallback, or switch genre. Cross-genre discovery is an explicit later option, not a silent fallback.

## 8. Shared backend functions and the application-owned MCP interface (agreed)

### 8.1 Shared functions

All filtering, choice retrieval, and ranking live in one backend module of deterministic functions over the catalog database and versioned configuration. Conceptually:

| Function | Inputs | Returns |
| --- | --- | --- |
| `get_eligible_genres` | activity | genre IDs and names, eligible track count per genre, pool counts (including exclusions for missing features) |
| `get_eligible_artists` | activity, genre | artist IDs and names, eligible track count per artist |
| `get_eligible_excerpts` | activity, genre, artist_ids | excerpt IDs, text, attribution, parent track ID, whether the parent track is by a selected artist |
| `generate_playlist` | activity, genre, artist_ids, excerpt_id, optional seed_track_ids, requested_length | preview: ordered track IDs and URIs, component scores, explanations, evidence coverage, shortfall notice, eligible pool count, configuration versions |

The web application calls these functions directly. The application-owned MCP server exposes the same four operations as MCP tools, each of which validates its arguments and delegates to the corresponding shared function. No filtering or ranking logic is duplicated in either interface.

### 8.2 Contract rules

- MCP is an agent-facing interface, not the filtering or ranking algorithm. An LLM calling the tools is never required to evaluate numeric constraints or compute ranking scores; the backend does that.
- Responses use stable identifiers (activity keys, genre IDs, artist IDs, excerpt IDs, track IDs/URIs) and include eligible counts where applicable.
- Errors are structured, with a machine-readable code, a message, and the offending field. At minimum: unknown activity, genre not eligible, artist not eligible, excerpt not eligible, seed track unknown or disabled, invalid requested length, empty pool. A shortfall is a successful result with a notice, not an error.
- `generate_playlist` returns a preview only. It never writes to Spotify. Saving is a separate, user-authorized action in the web application (Section 10); exposing a save operation over MCP is out of scope for the initial version.
- The application-owned MCP server holds no external-provider or Spotify credentials.

## 9. Runtime ranking (preserved)

### 9.1 Order

1. Validate all selections against the current catalog and progressive choice constraints (Section 7).
2. Build the candidate pool from activity eligibility, genre, and enabled status.
3. Build the request profile from activity, artist preferences, excerpt embedding/mood scores, and seed-track features (the excerpt's parent track by default, or the explicit seed set).
4. Compute normalized relevance components for every candidate.
5. Combine components into a weighted score.
6. Sort by score with a stable track-ID tie-breaker.
7. Apply diversity limits and recording deduplication while selecting the requested length.
8. Return track URIs, ranking components, explanations, evidence coverage, and any shortfall notice for the preview.

### 9.2 Initial score configuration (provisional weights)

Score(t) = 0.30 * mood(t) + 0.25 * activity(t) + 0.20 * audio(t) + 0.15 * artist(t) + 0.10 * genre(t)

These weights are starting hypotheses, not validated optimal values. Every component must be on [0, 1]. Keep the configuration version with each generated result.

| Component | Initial definition |
| --- | --- |
| Mood | Cosine similarity between excerpt and candidate semantic embeddings, mapped from [-1, 1] to [0, 1]. Use curated mood tags as an explicitly identified fallback. |
| Activity | Cached soft suitability score for the selected activity (Section 6.4). Separate from hard eligibility. |
| Audio | One minus weighted mean absolute distance between normalized candidate features and the combined seed profile. |
| Artist | 1 for a selected artist credit; otherwise an optional curated artist-affinity score, defaulting to 0. |
| Genre | Genre overlap score; under the MVP's hard genre filter this is constant and does not change ordering. |

Because genre is constant under a strict filter, remove its weight and renormalize the remaining components in that mode. Activity and seed-audio similarity can conflict: keep them separate and inspect cases such as a melancholic seed requested for workouts. Do not treat the seed as a hard audio constraint.

Hard eligibility constraints and soft ranking preferences stay separate: no ranking weight can admit an ineligible track, and no eligibility rule is expressed as a score penalty.

### 9.3 Multiple seeds

Multiple seeds contribute a weighted average of their normalized feature vectors. Equal seed weights are the default. A mean is a simple baseline but can fall between contrasting seeds; inspect examples and consider maximum or average per-seed similarity later if necessary. Seeds must be known, enabled catalog tracks; they need not belong to the candidate pool. Seed tracks may influence ranking without being forced into the output.

### 9.4 Missing features in ranking

Missing features must not become fabricated zeros. For a candidate or seed profile, exclude unavailable dimensions and renormalize their weights; if no usable audio dimensions remain, omit the audio component and renormalize the overall score weights. Return the reduced evidence coverage with the result. (This applies to soft ranking only; hard eligibility follows Section 6.3.)

### 9.5 Exclusions and diversity

Do not use track popularity, related-artist endpoints, artist top-track endpoints, or inferred producer credits as required features. Do not substitute artist-level mood for track-level mood.

Initial diversity rule (provisional limit): at most two tracks credited to the same primary artist and no duplicate recording/version in a playlist. If these limits prevent the target length, return fewer songs and explain the constraint rather than silently overriding it.

## 10. Spotify integration

### 10.1 Catalog preparation (offline)

Use Search to resolve a known recording, for example:

GET /v1/search?q=track:Wonderwall%20artist:Oasis&type=track

Store verified track IDs and Spotify URIs so runtime ranking requires no catalog lookup. Spotify API requests still require an appropriate access token; anonymous use of the application does not mean unauthenticated Spotify API calls.

### 10.2 Saving after preview

1. Start Spotify user OAuth only when the user requests saving. Use Authorization Code with PKCE where appropriate and validate state.
2. Request playlist-modify-private for private playlists; request public modification scope only if that feature is supported.
3. Create the playlist with POST /v1/me/playlists and a body containing name, description, and public: false.
4. Add the ranked URIs with POST /v1/playlists/{playlist_id}/items and a body such as {"uris": ["spotify:track:TRACK_ID_1", "spotify:track:TRACK_ID_2"]}.
5. Return the playlist URL. Handle partial writes and prevent duplicate playlist creation from repeated submissions.

Generating and previewing recommendations (through the web application or the application-owned MCP server) does not require Spotify authentication. Writing into the user's Spotify account does. Store secrets server-side, and protect any retained user tokens.

A dynamic result initially means a new ranking generated from current selections. Maintaining the same Spotify playlist as selections change is a separate feature: retain its ID and explicitly replace its items after authorization rather than creating a new playlist each time.

### 10.3 Current API constraints to validate before implementation

Spotify's February 2026 Development Mode migration documents an app-owner Premium requirement, a five-user limit for new apps, removal of artist top-track calls, removal of track popularity, and playlist endpoint changes. Therefore a public portfolio can expose the unauthenticated recommendation preview broadly, but must not promise unrestricted Spotify saving to all visitors under Development Mode. Verify current access requirements before deployment.

References:
- https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide
- https://developer.spotify.com/documentation/web-api/reference/search
- https://developer.spotify.com/documentation/web-api/reference/create-playlist
- https://developer.spotify.com/documentation/web-api/reference/add-items-to-playlist

## 11. Provisional parameters register

| Parameter | Where defined | Current status |
| --- | --- | --- |
| Activity constraint ranges (per activity, per feature) | Activity profiles (6.1) | Not yet defined; must be proposed with rationale and evaluated |
| Constraint `on_missing` fallbacks | Activity profiles (6.3) | Default `exclude`; any other value needs documented rationale |
| `min_genre_tracks` coverage threshold | Activity profiles (6.1) | Not yet defined |
| Tempo normalization range | Normalization config (5.4) | Not yet defined |
| Score weights 0.30 / 0.25 / 0.20 / 0.15 / 0.10 | Ranking config (9.2) | Initial hypothesis |
| Per-feature audio weights | Ranking config (9.2) | Not yet defined; equal weights as baseline |
| Seed weights | Ranking config (9.3) | Equal by default |
| Primary-artist limit (2 per playlist) | Ranking config (9.5) | Initial hypothesis |
| Default and maximum requested playlist length | Ranking config | Not yet defined |
| Embedding model and version | Enrichment config (3) | Not yet chosen |

## 12. Implementation order and completion criteria

1. **Validate external provider coverage and Spotify access requirements.** Through the provider's MCP client, test audio-feature coverage and accuracy on representative recordings; record what the provider actually supports (request granularity, limits, storage terms). Verify current Spotify app/account permissions. Completion: a documented coverage sample and confirmed saving constraints.
2. **Define the catalog schema and configurable activity profiles.** Build the schema in Section 4 and the profile/normalization/ranking configuration format with load-time validation (declared scale, `min <= max`, known features). Completion: invalid configurations are rejected; profiles carry provisional status and rationale.
3. **Populate and enrich a small cached catalog.** Resolve Spotify IDs, run resumable enrichment with validation and provenance, curate excerpts and descriptions, compute embeddings. Completion: valid identifiers and provenance; missing features stored as NULL; enough candidates across the intended activity/genre paths, or documented gaps.
4. **Implement and validate shared eligibility functions.** Completion: activity-boundary, missing-feature, and fallback acceptance criteria pass.
5. **Implement progressive choice retrieval.** `get_eligible_genres`, `get_eligible_artists`, `get_eligible_excerpts` with counts and structured errors. Completion: choice and reset acceptance criteria pass.
6. **Implement and evaluate ranking.** `generate_playlist` with normalization, multiple seeds, missing-feature renormalization, diversity limits, and explanations. Evaluate work, workout, relaxation, conflicting mood/activity, multiple seeds, and sparse pools; revise provisional ranges and weights deliberately and record why. Completion: deterministic output, no invalid candidates, no silent constraint relaxation.
7. **Expose the shared functions through the application-owned MCP server.** Completion: MCP/direct-call consistency criteria pass; no Spotify writes are reachable over MCP.
8. **Build the web interface using the same backend functions.** Follow the interaction order, show counts, reset incompatible downstream choices, and display explanations and shortfalls. Completion: every selectable path produces a valid preview or a clear insufficient-catalog response, with external providers unavailable.
9. **Add Spotify authentication and playlist saving.** Completion: an authorized eligible test account can save and open the previewed playlist in the same order; partial failures and repeat submissions are handled.
10. **Deploy and document catalog coverage, constraints, and limitations.** Document catalog scope, activity profiles and their provisional status, ranking choices, access limits, and example results. Completion: public preview works; saving behavior accurately reflects permitted app access.

Do not start with OAuth or a large ingestion pipeline. Validate the data, eligibility, and ranking on a small catalog first, after checking that the integration dependencies support the intended demo.

## 13. Acceptance criteria

### Activity boundaries
- A track whose constrained feature equals a configured `min` or `max` exactly is eligible; a track just outside either bound is ineligible.
- One-sided ranges filter only on the declared side.
- A feature with no configured range for the activity never excludes a track, whatever its value.
- A `raw` tempo range is compared in BPM; a `normalized` range is compared against the pinned normalization version. A constraint without a declared scale, or with `min > max`, fails configuration loading.

### Missing required features
- A track with NULL or `rejected` for a feature required by a hard constraint is ineligible under the default `on_missing: exclude`.
- A track with a missing feature that no constraint requires stays eligible, and the missing dimension is excluded from audio similarity with renormalized weights and reported evidence coverage.
- With an explicit documented fallback, the affected track is eligible and the response reports the fallback count.
- No code path stores or computes a missing feature as 0.

### Empty and small pools
- An activity with no eligible tracks is not offered; calling the functions with it returns a structured empty-pool or not-eligible error.
- Genres below `min_genre_tracks` are not offered.
- When the pool (after diversity limits) is smaller than `requested_length`, `generate_playlist` returns fewer tracks with a shortfall notice and does not widen any range, add other genres, or relax diversity limits.

### Downstream selection resets
- Changing activity clears a selected genre, artists, and excerpt that are no longer eligible, keeps those still eligible, and reports what was cleared.
- Changing genre clears artists and excerpts with no remaining eligible tracks.
- Calling `generate_playlist` with a stale selection returns a structured error naming the field.
- Offered choices always match counts computed from the current eligible tracks.

### Preferred artists
- Selecting artists does not limit the playlist to those artists when other eligible tracks score higher.
- Selected-artist tracks receive the artist component; the primary-artist diversity limit still applies.

### Multiple seeds
- With no explicit seeds, the excerpt's parent track is the only seed.
- With several explicit seeds, the seed profile is the configured weighted (default equal) average of their normalized features, computed per dimension over seeds that have that dimension.
- Seeds outside the candidate pool influence ranking but are not added to the output unless they are eligible and selected by score.
- An unknown or disabled seed ID returns a structured error.

### Consistency between MCP and direct backend calls
- For identical inputs, catalog state, and configuration versions, each MCP tool returns the same IDs, order, counts, scores, and errors as the corresponding direct function call.
- Repeated calls with identical inputs return identical results (stable tie-breaking).
- `generate_playlist` over MCP or the web application performs no Spotify write and no external-provider call.

### Separation of enrichment and recommendation
- With the external audio-feature provider unreachable, every choice and preview call succeeds for enriched tracks.

## 14. Trade-offs

- Offline enrichment makes generation fast and reproducible, but limits coverage and requires explicit catalog maintenance.
- Hard activity ranges make eligibility transparent and testable, but ranges are hypotheses; tight ranges shrink pools and may encode questionable assumptions about music and activity.
- Excluding tracks with missing required features avoids fabricated data, but reduces coverage until enrichment improves.
- Progressive narrowing improves relevance, but risks small or empty pools; option availability must reflect actual cached coverage.
- Manual weights are transparent and easy to debug, but require evaluation and do not learn automatically.
- Multiple seeds broaden the target, but averaging can dilute contrasting musical characteristics.
- Semantic embeddings capture textual similarity, but similarity alone does not prove emotional resonance.
- Third-party audio features reduce enrichment effort, but create a provider dependency; retain provenance and a working fallback.
- A single shared backend behind both the web application and the MCP server avoids divergent logic, but couples both interfaces to the same release cadence.
- A curated preview supports a public portfolio demonstration, while Spotify saving remains constrained by app access and user authorization.
