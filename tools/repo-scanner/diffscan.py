"""Diff-scan: fetch only the files a repo changed since the last scanned commit, for scan.py.

    python3 -I diffscan.py <out_dir> <input.tsv> <summary.tsv>

input.tsv: one `owner/repo<TAB>last_scanned_sha<TAB>branch` per line. Uses the GitHub compare
API (via `gh`) for the file list, then 12 threads of raw downloads into <out_dir>/<repo>/.
Appends one row per repo to summary.tsv: repo, old, new, status, ahead, files, downloaded,
removed, skipped-binary, skipped-big, errors, api-error. Then: python3 -I scan.py <out_dir>/<repo>

Limits learned the hard way:
- The compare API never returns more than 300 files, even with paging. A row with files=300
  is truncated: re-fetch that repo as a full tarball (`gh api repos/O/R/tarball`) instead.
- "No common ancestor" (404) means history was force-rewritten: full tarball rescan.
- Busy repos can 422 ("diff is taking too long"): full tarball rescan.
- Files over 3 MB are skipped (scan.py skips them too); binaries are skipped by extension.
"""
import json, os, subprocess, sys, urllib.request, concurrent.futures as cf
OUT, INP, SUM = sys.argv[1:4]
SKIP_EXT = {'.png','.jpg','.jpeg','.gif','.webp','.bmp','.ico','.mp4','.mov','.webm','.mp3','.wav','.ogg','.m4a','.zip','.gz','.tgz','.tar','.7z','.rar','.pdf','.woff','.woff2','.ttf','.otf','.eot','.bin','.pt','.pth','.safetensors','.gguf','.onnx','.dmg','.exe','.dll','.so','.dylib','.pyc','.class','.jar','.psd','.ai','.sketch','.fig','.blend','.glb','.gltf','.fbx','.obj','.stl','.icns','.car','.heic','.avif','.tiff','.tif','.aac','.flac','.wasm'}
summ = open(SUM, 'a')
def dl(args):
    f, dest = args
    try:
        with urllib.request.urlopen(f['raw_url'], timeout=60) as resp: data = resp.read(3_000_001)
    except Exception as e: return 'err', str(e)[:80]
    if len(data) > 3_000_000: return 'big', ''
    os.makedirs(os.path.dirname(dest), exist_ok=True); open(dest, 'wb').write(data); return 'ok', ''
for line in open(INP):
    if not line.strip(): continue
    repo, sha, branch = line.rstrip('\n').split('\t'); name = repo.split('/')[1]
    files, page, err, ahead, status = [], 1, '', None, ''
    while True:
        r = subprocess.run(['gh','api', f'repos/{repo}/compare/{sha}...{branch}?per_page=250&page={page}'], capture_output=True, text=True)
        if r.returncode != 0: err = ' '.join(r.stderr.split())[:160]; break
        d = json.loads(r.stdout); status, ahead = d.get('status',''), d.get('ahead_by'); fs = d.get('files', []); files += fs
        if len(fs) < 250: break
        page += 1
    head = subprocess.run(['gh','api', f'repos/{repo}/branches/{branch}', '--jq', '.commit.sha'], capture_output=True, text=True).stdout.strip()
    n_rm = n_bin = n_big = n_dl = n_err = 0; jobs = []
    if files:
        os.makedirs(os.path.join(OUT, name), exist_ok=True)
        with open(os.path.join(OUT, name + '.list'), 'w') as lf:
            lf.write(f'# {repo} {sha}...{head} status={status} ahead={ahead}\n')
            for f in files:
                lf.write(f"{f['status']}\t{f['filename']}\n")
                if f['status'] == 'removed': n_rm += 1; continue
                if os.path.splitext(f['filename'])[1].lower() in SKIP_EXT: n_bin += 1; continue
                jobs.append((f, os.path.join(OUT, name, f['filename'])))
        with cf.ThreadPoolExecutor(12) as ex:
            for st, _ in ex.map(dl, jobs):
                if st == 'ok': n_dl += 1
                elif st == 'big': n_big += 1
                else: n_err += 1
    summ.write('\t'.join(map(str, [repo, sha[:7], head[:7], status, ahead, len(files), n_dl, n_rm, n_bin, n_big, n_err, err])) + '\n'); summ.flush()
    print(repo, status, ahead, len(files), n_dl, err, flush=True)
