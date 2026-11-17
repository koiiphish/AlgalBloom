# Decisions log

One short entry per non-obvious decision: context, choice, and the alternatives we rejected.

---

## D001 — Committed labels live in `labels/`, not `data/labels/` (2026-11-17)

**Context:** The brief says `data/` is git-ignored (raw caches). But the Phase 1 label archive (daily status snapshots) and `events.csv` must be committed, because the official status pages show only the current state and history is lost unless we record it.

**Choice:** Use a top-level `labels/` directory for every committed label file. `data/` stays purely for disposable, re-downloadable caches.

**Alternatives rejected:**
- *A `.gitignore` exception for `data/labels/`:* it works, but it mixes precious, irreplaceable data with throwaway caches in one tree. That makes an accidental `rm -rf data/` or a cache clean-up destructive.
