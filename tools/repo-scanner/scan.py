# Static malware-shape scan for /ai-news repo vetting. Never executes repo code.
# 2026-11-16: the XOR-loop alternative used an unanchored \w+ and went quadratic on long base64/minified runs (83 MB repo = 89 min); now word-anchored and bounded.
# Usage: python3 -I scan.py <dir> [<dir> ...]
import os, re, sys

DETECTORS = {
    'py-shape': re.compile(r'exec\s*\(\s*(?:__import__|base64|zlib|marshal|bytes|compile|codecs)|(?:b64decode|decompress)\([^)]*\)\s*\)\s*\)|chr\(\s*\w+\s*\^\s*\w+|(?<!\w)\w{1,64}\s*\^\s*\w{1,64}(?:\[[^\]]*\])?\s+for\s+\w+(?:\s*,\s*\w+)?\s+in\s|__import__\([^)]*\)\.\w+\('),
    'js-shape': re.compile(r'eval\s*\(\s*(?:atob|Buffer\.from|unescape|String\.fromCharCode)|new\s+Function\s*\(\s*(?:atob|Buffer\.from)|fromCharCode\([^)]*\^|charCodeAt\([^)]*\)\s*\^'),
    'ipv4-url': re.compile(r'(?:https?|wss?)://(?:\d{1,3}\.){3}\d{1,3}'),
    'inject-api': re.compile(r'VirtualAllocEx|WriteProcessMemory|CreateRemoteThread|NtUnmapViewOfSection|SetThreadContext|QueueUserAPC'),
    'install-hook': re.compile(r'"(?:preinstall|postinstall|install)"\s*:|cmdclass\s*=|"prepare"\s*:\s*"[^"]*(?:curl|wget|node -e|powershell)'),
}
BENIGN_IP = re.compile(r'://(?:127\.0\.0\.1|0\.0\.0\.0|10\.|192\.168\.|169\.254\.|100\.64\.|1\.2\.3\.4)')

for root in sys.argv[1:]:
    hits, files = {k: [] for k in DETECTORS}, 0
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d != '.git']
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                if os.path.getsize(p) > 3_000_000: continue
                txt = open(p, encoding='utf-8', errors='ignore').read()
            except OSError:
                continue
            files += 1
            for k, rx in DETECTORS.items():
                for m in rx.finditer(txt):
                    line = txt[max(0, m.start() - 60):m.end() + 60].replace('\n', ' ')
                    if k == 'ipv4-url' and BENIGN_IP.search(m.group(0) + '/'): continue
                    hits[k].append(f'{os.path.relpath(p, root)}: {line}')
    print(f'== {os.path.basename(root)}  files={files}')
    for k, v in hits.items():
        print(f'  {k}: {len(v)}')
        for h in v[:4]: print('     ', h[:220])
