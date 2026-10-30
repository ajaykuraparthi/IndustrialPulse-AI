import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.generator import generate_dataset

def digest(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--telemetry",type=int,default=1000)
    p.add_argument("--seed",type=int,default=20261022)
    a=p.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        one=Path(tmp)/"one"; two=Path(tmp)/"two"
        c1=generate_dataset(one,a.seed,a.telemetry); c2=generate_dataset(two,a.seed,a.telemetry)
        hashes1={x.name:digest(x) for x in sorted(one.iterdir()) if x.is_file()}
        hashes2={x.name:digest(x) for x in sorted(two.iterdir()) if x.is_file()}
        ok=c1==c2 and hashes1==hashes2
        print({"reproducible":ok,"counts_equal":c1==c2,"checksums_equal":hashes1==hashes2,"counts":c1})
        if not ok: raise SystemExit(1)
if __name__=="__main__": main()
