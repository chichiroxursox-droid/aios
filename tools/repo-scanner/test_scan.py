"""Self-check: every detector fires on control/, and the benign file stays quiet.
Run: python3 -I tools/repo-scanner/test_scan.py"""
import os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
out = subprocess.run([sys.executable, "-I", os.path.join(HERE, "scan.py"), os.path.join(HERE, "control")],
                     capture_output=True, text=True, check=True).stdout
counts = dict(re.findall(r"^\s+([\w-]+): (\d+)$", out, re.M))
for det in ("py-shape", "js-shape", "ipv4-url", "inject-api", "install-hook"):
    assert int(counts.get(det, 0)) >= 1, f"{det} did not fire on the positive control:\n{out}"
assert "benign.py" not in out, f"false positive on benign.py:\n{out}"
print("ok:", counts)
