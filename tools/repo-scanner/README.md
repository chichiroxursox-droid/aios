# repo-scanner

Static malware-shape scanner for GitHub repos, built to vet the "trending AI repos" table in a daily AI-news digest before any repo gets recommended. That table turned out to be where a star-farmed malware campaign lives (see [IOCS.md](IOCS.md)). The scanner never executes repo code.

## Why shape detectors, not an IOC list

The campaign changed its loader three times in two months. Each change killed the previous detector:

1. Plaintext C2 IP + signature strings. The IP rotated, so searching the old one gave a false clean.
2. The payload moved into XOR-encrypted int arrays, so no plaintext string survived.
3. The XOR loader was replaced with a plaintext Windows process-hollowing loader, so the XOR-shape detector went quiet.

So `scan.py` matches *shapes* and *behavior* together, and any known-dirty repo that suddenly scans clean is treated as a detector failure until its latest diff has been read.

| Detector | Catches |
|---|---|
| `py-shape` | `exec(` on `__import__`/`base64`/`zlib`/`marshal`/`compile`; nested decode-then-exec; `chr(a ^ b)`; one-line XOR loops (`x ^ k for v in a`); `__import__(...).attr(` |
| `js-shape` | `eval(atob(...))`, `new Function(Buffer.from(...))`, XOR inside `fromCharCode`/`charCodeAt` |
| `ipv4-url` | `http(s)://` / `ws(s)://` to a literal IPv4 address (private, loopback and link-local ranges excluded) |
| `inject-api` | `VirtualAllocEx`, `WriteProcessMemory`, `CreateRemoteThread`, `NtUnmapViewOfSection`, `SetThreadContext`, `QueueUserAPC` |
| `install-hook` | npm `preinstall`/`postinstall`/`install` scripts, setuptools `cmdclass`, `prepare` scripts that curl/wget/eval |

## Usage

```bash
# full scan of a repo, without cloning or installing anything
mkdir -p scan/repo && gh api repos/OWNER/REPO/tarball > scan/repo.tgz
tar -xzf scan/repo.tgz -C scan/repo --strip-components=1
python3 -I tools/repo-scanner/scan.py tools/repo-scanner/control scan/repo   # control first

# re-scan only what changed since the last scanned commit
printf 'OWNER/REPO\t<last_sha>\tmain\n' > diff-input.tsv
python3 -I tools/repo-scanner/diffscan.py diff diff-input.tsv diff-summary.tsv
python3 -I tools/repo-scanner/scan.py diff/REPO

# self-check: every detector fires on control/, benign.py stays quiet
python3 -I tools/repo-scanner/test_scan.py
```

Always include `control/` in a scan run. A finished scan prints `== <name>  files=N` first, so empty output means the process was killed, not that the repo is clean.

## Lessons that changed the code or the process

- **Regex performance is a correctness issue.** The XOR-loop pattern used an unanchored `\w+` and went quadratic on long base64/minified runs: an 83 MB repo took 89 minutes and a 1.7 MB one never finished. Anchoring it to `(?<!\w)\w{1,64}` brought the 1.7 MB repo to 0.7 s with the control still firing. Run one `scan.py` process per repo, in parallel, rather than one process over everything.
- **The compare API caps at 300 files.** A diff-scan row with exactly 300 files is truncated; tarball that repo instead. "No common ancestor" means a force-push, also a full rescan.
- **Some lures carry no code at all.** Exclude on shape before scanning, without cloning:
  - brand-new repo, hundreds of stars within days, owner with 0 followers, AI-coding-agent bait
  - near-empty "twin" repos from accounts registered the same month with identical fork counts (stars farmed first, payload pushed later)
  - README-only repos named after a real product, with the payload in a release asset (`gh api repos/O/R/releases`) or a README badge linking to a cloud-storage `.rar`
  - batches of clone-named repos with identical round star counts, created the same day and pushed minutes apart
- **Known false positives** (read the context before escalating): RFC 6455 WebSocket unmasking (`b ^ mask[i % 4]`), cloud metadata `169.254.169.254` in SSRF tests, TEST-NET documentation IPs (`192.0.2.x`, `198.51.100.x`, `203.0.113.x`), a project's own localhost server on a campaign port, and generated Go/Rust data tables that look like numeric blobs but have no decoder, exec or network code.
