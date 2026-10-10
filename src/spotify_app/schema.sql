CREATE TABLE IF NOT EXISTS genres(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'spotify_extended_audio_features',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS acquisition_runs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_key TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    requested_count INTEGER NOT NULL DEFAULT 0,
    succeeded_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS acquisition_requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    acquisition_run_id INTEGER NOT NULL
        REFERENCES acquisition_runs(id) ON DELETE CASCADE,
    mood TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_parameters TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    finished_at TEXT,
    response_status TEXT NOT NULL
        CHECK (response_status IN ('succeeded','http_error','request_failed')),
    status_code INTEGER,
    content_type TEXT,
    response_file TEXT,
    error_type TEXT,
    error TEXT,
    UNIQUE (acquisition_run_id, mood)
);

CREATE TABLE IF NOT EXISTS acquisition_request_genres(
    acquisition_request_id INTEGER NOT NULL
        REFERENCES acquisition_requests(id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(id),
    PRIMARY KEY (acquisition_request_id, genre_id)
);

CREATE TABLE IF NOT EXISTS artists(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_artist_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tracks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_track_id TEXT NOT NULL UNIQUE,
    spotify_uri TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    release_year INTEGER,
    recording_version TEXT,
    isrc TEXT,
    album_name TEXT,
    spotify_album_id TEXT,
    explicit INTEGER CHECK (explicit IN (0,1)),
    popularity INTEGER,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS track_artists(
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    artist_id INTEGER NOT NULL REFERENCES artists(id),
    position INTEGER NOT NULL,
    is_primary INTEGER NOT NULL CHECK (is_primary IN (0,1)),
    PRIMARY KEY (track_id, artist_id)
);

CREATE TABLE IF NOT EXISTS acquisition_request_tracks(
    acquisition_request_id INTEGER NOT NULL
        REFERENCES acquisition_requests(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(id),
    position INTEGER NOT NULL,
    PRIMARY KEY (acquisition_request_id, track_id)
);
