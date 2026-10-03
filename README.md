# Lyric-Driven Spotify Recommendations

A portfolio application that builds an ordered playlist from an activity, a genre, preferred artists, and a curated lyric excerpt. It ranks a cached, offline-enriched track catalog with a transparent weighted content-based score, previews the result without login, and optionally saves it to the user's Spotify account.

> **Status:** revamp in progress. This branch replaces the earlier clustering notebook project. No application code is published yet.

## Documents

- [`lyric_recommendation_specification.md`](lyric_recommendation_specification.md) — system specification: architecture, activity eligibility rules, progressive narrowing, ranking, MCP interface, Spotify integration, acceptance criteria.
- [`DEVELOPER_SEQUENCE_FLOW.md`](DEVELOPER_SEQUENCE_FLOW.md) — phased task plan and progress tracker.

## Tooling

Python 3.12, managed with [uv](https://docs.astral.sh/uv/).
