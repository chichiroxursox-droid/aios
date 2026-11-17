# Indicators of compromise (defensive reference)

**This file lists known-malicious infrastructure and repositories on purpose.** It exists so the scanner's behavior detectors can be checked against real cases. Do not visit, clone, install or run anything named here. Observations are dated; repos get taken down and re-uploaded under new owners, so treat the list as a starting point, not a blocklist. An account named here may itself be a compromised account rather than the author.

Campaign: star-farmed GitHub repositories pitched at Claude Code / AI-coding-agent users (token-cost trackers, chat-history extractors, video generators) that carry a Windows loader. Tracked from late August to November 2026 while vetting the daily AI-news digest's trending-repo table.

## Command-and-control endpoints

| Endpoint | First seen | Notes |
|---|---|---|
| `91.92.47.134:8765` | 2026-08 | Original stager C2. Searching it alone returned a false clean after the rotation. |
| `172.233.51.81:8765` | 2026-09-11 | Rotated C2, same loader. |
| `85.121.179.7:8000` | 2026-10-10 | Plaintext process-hollowing loader (`/pe/hash/<sha256>`), no platform gate. |

## Loader signatures (by generation)

1. **Plaintext stager (Aug 2026):** `manual_mapper.py` second stage + port `8765` + `/api/v1/sync?asset=` + `exec(compile(...))` + a `sys.platform == "win32"` gate. `manual_mapper` alone is not enough (many benign hits); require the combination.
2. **XOR-obfuscated (from 2026-09-20):** a one-line decoder `lambda a,k: bytes(v^k for v in a)`; `__import__(<decoded bytes>.decode())` instead of a string literal; module names decode to `hashlib`, `zlib`, `hmac`, `builtins`, `exec`; a `.py` that is >90% digits/brackets/commas (encrypted int arrays), e.g. ~25-29 KB over ~43 lines. Every plaintext IOC above misses it.
3. **Plaintext process hollowing (from 2026-10-10):** `CreateProcessW` (CREATE_SUSPENDED) → `VirtualAllocEx` (RWX) → `WriteProcessMemory` → `SetThreadContext` → `ResumeThread`, fetching a PE from an IPv4 URL with a bearer token. The XOR-shape detector misses it.

Trigger placement moved over time: first on import (`__main__.py`), later on the first CLI run (`cli.py` does `import setup` then `setup.run_sync(...)`). The loader lives in a module named `setup.py` **inside the package directory**, so a clean root `pyproject.toml` proves nothing. An install-time sandbox sees nothing either.

## Repositories observed carrying a loader

Owner accounts are withheld on purpose: some were likely compromised rather than run by the attacker, and several were taken down. Repo names and loader paths are enough to match a re-upload.

| Repo name | Owners seen | Observed | Loader path |
|---|---|---|---|
| `tokentab` | 4 | 2026-08-24 to 10-14 | `tokentab/setup.py` |
| `my-free-code` | 1 | 2026-08-31 to 10-10 | `my_free_code/cli/point.py`, `core/point.py` |
| `short-video-generator-AI` | 1 | 2026-09-11 to 09-21 | `src/fs.py` |
| `ai-data-extractor` | 2 | 2026-09-15 to 10-10 | `extractors/extract.py` |
| `video-generator-client` | 1 | 2026-10-10 | `src/video_gen/seedance.py` |

Bait names that reappear under new owners after takedowns: `tokentab`, `ai-data-extractor`, `my-free-code`, `short-video-generator-AI`. A known bait name under a new owner is presumed dirty until a scan says otherwise.

Find siblings of a new C2 with one search: `gh api -X GET search/code -f q='<C2 IP>'`.
