#!/usr/bin/env python3
"""PaMCP E1 v0.3.1 conservative operation-evidence triage."""
import argparse, csv, hashlib, json, re
from collections import Counter
from pathlib import Path

NAME_ACTIONS = {
 "delete":{"delete","remove","drop","erase","purge","destroy","revoke","unsubscribe"},
 "write":{"create","add","write","update","edit","insert","save","upload","submit","commit","append","set","assign","move","copy","rename","replace","install","deploy","provision","grant","register","enable","disable","merge","apply","overwrite","protect","initialize","init"},
 "money":{"pay","charge","refund","purchase","buy","sell","transfer","withdraw","deposit"},
}
DESC_ACTIONS = {
 "delete":re.compile(r"^(?:delete|remove|drop|erase|purge|destroy|revoke|unsubscribe)\b",re.I),
 "write":re.compile(r"^(?:create|add|write|update|edit|insert|save|upload|submit|commit|append|set|assign|move|copy|rename|replace|install|deploy|provision|grant|register|enable|disable|merge|apply|overwrite|protect|initialize)\b",re.I),
 "money":re.compile(r"^(?:pay|charge|refund|purchase|buy|sell|transfer|withdraw|deposit)\b",re.I),
}
READ_PREFIX=re.compile(r"^(?:read|get|fetch|list|search|find|retrieve|retrieves|lookup|describe|show|shows|view|views|inspect|inspects|check|checks|count|counts|return|returns|obtain|obtains|extract|extracts)\b",re.I)
PURE_PREFIX=re.compile(r"^(?:calculate|compute|validate|format|render|parse|analy[sz]e|summari[sz]e|estimate|predict|forecast|rank|recommend|compare|classify)\b",re.I)
AMBIG_PREFIX=re.compile(r"^(?:click|fill|type|press|select|hover|navigate|switch|reset|checkout|download|export|import|generate|convert|record|interact|evaluate|open|load|manage|run|execute)\b",re.I)
MONEY_OBJECT=re.compile(r"\b(?:funds?|money|payment|payments|refund|order|purchase|subscription|product|item|shares?|stocks?|options?|assets?|crypto(?:currency)?|invoice|ticket|account|service)\b",re.I)
HTTP_METHOD=re.compile(r"\bHTTP\s+(GET|POST|PUT|PATCH|DELETE)\s+request\b",re.I)
EXEC_START=re.compile(r"^(?:start|launch)\s+(?:a\s+|the\s+)?(?:new\s+)?(?:terminal\s+)?(?:process|command|script|program|job|workflow)\b",re.I)
EGRESS_PREFIX=re.compile(r"^(?:send|notify|publish|post|email|message)\b",re.I)
SESSION_PREFIX=re.compile(r"^(?:switch|navigate|select|open|close|focus|activate)\b",re.I)

def clean_name(name):
 name=re.sub(r"(?<=[a-z0-9])(?=[A-Z])"," ",(name or "").strip())
 return re.sub(r"[_-]+"," ",name).strip().lower()

def first_sentence(description):
 text=(description or "").strip()
 if not text:return ""
 line=next((x.strip() for x in text.splitlines() if x.strip()),"")
 if re.match(r"^(returns?|args?|parameters?|example|output|response)\s*:",line,re.I):return ""
 m=re.search(r"[.!?](?:\s|$)",line)
 return line[:m.end()].strip() if m else line[:300]

def operation_evidence(row):
 name=clean_name(row.get("tool_name") or "")
 first=first_sentence(row.get("description") or "")
 return name,first

def classify(row):
 name,first=operation_evidence(row)
 name_first=name.split()[0] if name else ""
 method=HTTP_METHOD.search(first)
 if method:
  verb=method.group(1).upper()
  if verb=="DELETE":return ("true_candidate","true","delete","http_delete_method","Explicit HTTP DELETE; candidate only.")
  if verb in {"POST","PUT","PATCH"}:return ("true_candidate","true","write","http_mutation_method",f"Explicit HTTP {verb}; endpoint semantics/runtime not verified.")
  if verb=="GET":return ("false_candidate","false","read","http_get_method","Explicit HTTP GET; candidate only.")
 for effect,verbs in NAME_ACTIONS.items():
  if name_first in verbs:
   if effect=="money":
    if MONEY_OBJECT.search(name):return ("true_candidate","true","money","transaction_operation_name","Explicit transaction verb and object; candidate only.")
    return ("unresolved","","","ambiguous_money_operation","Financial action verb lacks explicit transaction object.")
   return ("true_candidate","true",effect,"operation_name_action",f"Operation name begins with explicit {effect} action; candidate only.")
 for effect,pattern in DESC_ACTIONS.items():
  if pattern.search(first):
   if effect=="money":
    if MONEY_OBJECT.search(first):return ("true_candidate","true","money","transaction_description","Explicit financial transaction; candidate only.")
    return ("unresolved","","","ambiguous_money_description","Financial action verb lacks explicit transaction object.")
   return ("true_candidate","true",effect,"leading_operation_description",f"Description begins with explicit {effect} action; candidate only.")
 if EXEC_START.search(first):
  return ("true_candidate","true","exec","process_execution_description","Explicitly starts/launches an executable process; candidate only.")
 if READ_PREFIX.search(first) or READ_PREFIX.search(name):
  return ("false_candidate","false","read","retrieval_operation","Retrieval wording; no qualifying state mutation documented. Candidate only.")
 if PURE_PREFIX.search(first) or PURE_PREFIX.search(name):
  return ("false_candidate","false","","pure_computation_operation","Computation/formatting wording; no qualifying state mutation documented.")
 if EGRESS_PREFIX.search(first):
  return ("false_candidate","false","egress","egress_only_operation","Egress alone is not state-modifying under approved E1 construct.")
 if SESSION_PREFIX.search(first) or SESSION_PREFIX.search(name) or AMBIG_PREFIX.search(first) or AMBIG_PREFIX.search(name):
  return ("unresolved","","","context_dependent_operation","Context-dependent operation; qualifying state effect is not established.")
 return ("unresolved","","","insufficient_operation_evidence","Insufficient operation-level evidence.")

def main():
 p=argparse.ArgumentParser();p.add_argument("input_csv");p.add_argument("output_csv");a=p.parse_args()
 with open(a.input_csv,newline="",encoding="utf-8-sig") as f:rows=list(csv.DictReader(f))
 if not rows:raise SystemExit("Input CSV is empty")
 counts=Counter()
 for r in rows:
  status,label,effects,etype,rationale=classify(r)
  r.update({"semantic_status_v0_3_1":status,"semantic_non_read_only_candidate_v0_3_1":label,"semantic_effect_classes_v0_3_1":effects,"semantic_evidence_type_v0_3_1":etype,"semantic_evidence_rationale_v0_3_1":rationale,"semantic_operation_evidence_v0_3_1":" | ".join(operation_evidence(r))[:600]})
  counts[status]+=1
 out=Path(a.output_csv);out.parent.mkdir(parents=True,exist_ok=True)
 with out.open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print(json.dumps({"rows":len(rows),"counts":dict(counts),"sha256":hashlib.sha256(out.read_bytes()).hexdigest()},sort_keys=True))
if __name__=="__main__":main()
