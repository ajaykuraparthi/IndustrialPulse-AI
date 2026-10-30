import argparse, json
from app.generator import generate_dataset
from app.validation import validate_dataset

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--seed",type=int,default=20261022)
    parser.add_argument("--telemetry",type=int,default=100000)
    parser.add_argument("--output-dir",default="data/generated")
    args=parser.parse_args()
    counts=generate_dataset(args.output_dir,args.seed,args.telemetry)
    result=validate_dataset(args.output_dir)
    print(json.dumps({"counts":counts,"validation":result},indent=2))
    if not result["valid"]:
        raise SystemExit(1)
if __name__=="__main__": main()
