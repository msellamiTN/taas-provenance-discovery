"""PaMCP protocol run-control CLI; never invokes the legacy E0-E7 runner."""
import argparse, json
from taas.experiments.catalog import load_catalog
from taas.experiments.run_control import load_dependency_manifest, read_ledger

def main():
    p=argparse.ArgumentParser(description="PaMCP E1-E22 run control")
    p.add_argument("command",choices=["status","validate-dependencies","ledger"])
    a=p.parse_args()
    if a.command=="status":
        c=load_catalog(); records=read_ledger(); d=load_dependency_manifest()
        gate_count=sum(len(gates) for gates in d["external_prerequisites"].values())
        out={"protocol":"PaMCP","version":"1.0.0","catalog_experiments":len(c["experiments"]),
             "catalog_statuses":{e["id"]:e["status"] for e in c["experiments"]},
             "dependency_manifest_valid":True,"external_gate_count":gate_count,
             "recorded_attempts":len(records),"execution_enabled":False,
             "reason":"Dependency manifest is validated; experiment-specific validated handlers are not installed."}
    elif a.command=="validate-dependencies":
        d=load_dependency_manifest()
        out={"valid":True,"experiments":len(d["depends_on"]),
             "external_gate_count":sum(len(gates) for gates in d["external_prerequisites"].values())}
    else: out=read_ledger()
    print(json.dumps(out,indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())
