"""Explicitly invoked, reversible Kubernetes failure scenarios; no automatic destructive action."""
import argparse, subprocess, sys
NS="fault-tolerance"
def run(*args): print("+",*args); return subprocess.run(args,check=True,text=True)
def main():
 p=argparse.ArgumentParser(); p.add_argument("scenario",choices=["delete-pod","scale-zero","restore","latency","errors","node-drain"]); p.add_argument("--service",default="marks"); p.add_argument("--value",default="500"); p.add_argument("--confirm",action="store_true"); a=p.parse_args()
 if not a.confirm: sys.exit("Safety gate: rerun with --confirm after reviewing the operation.")
 if a.scenario=="delete-pod":
  pod=subprocess.check_output(["kubectl","-n",NS,"get","pod","-l",f"app={a.service}","-o","jsonpath={.items[0].metadata.name}"],text=True); run("kubectl","-n",NS,"delete","pod",pod)
 elif a.scenario=="scale-zero": run("kubectl","-n",NS,"scale",f"deployment/{a.service}","--replicas=0")
 elif a.scenario=="restore": run("kubectl","-n",NS,"scale",f"deployment/{a.service}","--replicas=2")
 elif a.scenario in ("latency","errors"):
  key="latency_ms" if a.scenario=="latency" else "error_rate"; payload='{"%s":%s}'%(key,a.value)
  run("kubectl","-n",NS,"exec",f"deploy/{a.service}","--","sh","-c",f"wget -qO- --post-data='{payload}' --header='Content-Type: application/json' http://127.0.0.1:8000/admin/fault")
 elif a.scenario=="node-drain": run("kubectl","drain",a.service,"--ignore-daemonsets","--delete-emptydir-data")
if __name__=="__main__": main()
