#!/usr/bin/env python3
"""PaMCP E1 v0.3 conservative operation-evidence triage.

Exploratory candidate generator only. It does not create ground truth, infer
undocumented runtime behavior, or alter the approved E1 annotation construct.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

DIRECT = {
    "money": re.compile(r"\b(?:pay|make a payment|charge|refund|purchase|buy|sell)\s+(?:a\s+|an\s+|the\s+)?(?:product|item|share|stock|asset|subscription|order|service|ticket|invoice|funds|account)\b|\b(?:transfer|withdraw|deposit)\s+funds\b|\bplace\s+an\s+order\b|支付|付款|购买|下单|退款|转账|提现|充值", re.I),
    "delete": re.compile(r"\b(?:delete|remove|drop|erase|purge|revoke|unsubscribe|destroy|terminate resource)\b|删除|移除|清空|撤销|卸载", re.I),
    "exec": re.compile(r"\b(?:execute|run)\s+(?:a\s+|the\s+|an\s+)?(?:command|script|code|process|program|shell|workflow|job)\b|\b(?:execute|run)\s+(?:command|script|code|workflow|job)\b|执行(?:命令|脚本|代码|程序|任务)", re.I),
    "write": re.compile(r"\b(?:create|write|update|edit|modify|insert|save|upload|submit|commit|append|set|assign|move|copy|rename|replace|install|deploy|provision|grant|register|enable|disable|start|stop|restart|merge|apply|persist|overwrite)\b|创建|写入|更新|修改|插入|保存|上传|提交|追加|设置|分配|移动|复制|重命名|替换|安装|部署|授权|注册|启用|禁用|启动|停止|重启|合并", re.I),
}
AMBIGUOUS = re.compile(r"\b(?:click|fill|type|press|select|hover|navigate|switch|reset|checkout|download|export|import|generate|convert|record|interact|evaluate)\b|\brun\s+(?:a\s+)?query\b", re.I)
READ = re.compile(r"\b(?:read|reads|reading|get|gets|fetch|fetches|list|lists|search|searches|find|finds|query|queries|retrieve|retrieves|lookup|lookups|describe|describes|show|shows|view|views|inspect|inspects|check|checks|count|counts|return|returns|obtain|obtains|extract|extracts)\b|读取|获取|查询|搜索|检索|查找|查看|返回|列出", re.I)
PURE = re.compile(r"\b(?:calculate|calculates|compute|computes|validate|validates|format|formats|render|renders|parse|parses|analyze|analyses|analyse|summarize|summarises|estimate|estimates|predict|predicts|forecast|forecasts|rank|ranks|recommend|recommends|compare|compares|classify|classifies)\b|计算|转换|验证|格式化|渲染|解析|分析|总结|估算|预测|推荐|比较|分类", re.I)


def first_sentence(description):
    text = (description or "").strip()
    if not text:
        return ""
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if re.match(r"^(returns?|args?|parameters?|example|output|response)\s*:", first_line, re.I):
        return ""
    match = re.search(r"[.!?](?:\s|$)", first_line)
    return first_line[:match.end()].strip() if match else first_line[:300]


def operation_evidence(row):
    name = (row.get("tool_name") or "").strip()
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " ").replace("-", " ")
    first = first_sentence(row.get("description") or "")
    return name, first, (name + " " + first).strip()


def classify(row):
    name, first, evidence = operation_evidence(row)
    matched = [effect for effect, pattern in DIRECT.items() if pattern.search(evidence)]
    if matched:
        return ("true_candidate", "true", "|".join(matched), "direct_operation_wording",
                "Operation name/first meaningful description sentence contains explicit qualifying state-changing wording; candidate only, not runtime-verified.")
    if READ.search(name) or READ.search(first) or PURE.search(name) or PURE.search(first):
        if AMBIGUOUS.search(name) or AMBIGUOUS.search(first):
            return ("unresolved", "", "", "ambiguous_interaction",
                    "Retrieval/computation wording coexists with a context-dependent interaction; documentation alone does not establish qualifying state mutation.")
        return ("false_candidate", "false", "read", "retrieval_or_computation",
                "Operation wording indicates retrieval or computation; no qualifying write/delete/exec/money effect is explicit. Candidate only.")
    if AMBIGUOUS.search(evidence):
        return ("unresolved", "", "", "ambiguous_operation",
                "Operation wording is too generic or context-dependent to establish a qualifying state-modifying effect.")
    return ("unresolved", "", "", "insufficient_documentation",
            "Insufficient explicit operation-level evidence for a conservative binary candidate.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv")
    parser.add_argument("output_csv")
    args = parser.parse_args()
    with open(args.input_csv, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("Input CSV is empty")
    counts = Counter()
    for row in rows:
        status, label, effects, evidence_type, rationale = classify(row)
        row["semantic_status_v0_3"] = status
        row["semantic_non_read_only_candidate_v0_3"] = label
        row["semantic_effect_classes_v0_3"] = effects
        row["semantic_evidence_type_v0_3"] = evidence_type
        row["semantic_evidence_rationale_v0_3"] = rationale
        row["semantic_operation_evidence_v0_3"] = " | ".join(operation_evidence(row)[:2])[:600]
        counts[status] += 1
    output = Path(args.output_csv)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "counts": dict(counts),
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
