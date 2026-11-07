#!/usr/bin/env python3
"""Reproduce PaMCP E1 schema-aware AI-assisted triage v0.2.

This deterministic evidence triage is NOT human annotation, semantic ground truth,
runtime verification, or E1 completion. It uses only tool name, description,
and documented JSON-schema text.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

MUTATING = [
    ("money", r"\b(refund|purchase|pay(?:ment)?|transfer funds|charge (?:a|the)|place an order|buy|sell|trade|withdraw|deposit)\b|支付|付款|购买|下单|退款|转账|提现|充值"),
    ("delete", r"\b(delete|remove|drop|erase|purge|clear|cancel|revoke|unsubscribe)\b|删除|移除|清空|取消|撤销|卸载"),
    ("exec", r"\b(execute|run)\s+(?:a |the |an )?(?:command|script|code|query|process|program|shell|workflow|job)\b|执行(?:命令|脚本|代码|程序|任务)"),
    ("write", r"\b(create|write|update|edit|modify|insert|add|save|upload|download|send|submit|publish|commit|append|set|assign|move|copy|rename|replace|install|deploy|provision|grant|register|enable|disable|start|stop|restart|merge|export|import|initialize|init)\b|创建|写入|更新|修改|插入|添加|保存|上传|下载|发送|提交|发布|追加|设置|分配|移动|复制|重命名|替换|安装|部署|授权|注册|启用|禁用|启动|停止|重启|合并|导出|导入|初始化"),
]
READ = r"\b(read|reads|reading|get|gets|fetch|fetches|list|lists|search|searches|find|finds|query|queries|retrieve|retrieves|lookup|lookups|describe|describes|show|shows|view|views|inspect|inspects|check|checks|count|counts|return|returns|obtain|obtains|extract|extracts|whois)\b|读取|获取|查询|搜索|检索|查找|查看|返回|列出|获取"
PURE = r"\b(calculate|calculates|compute|computes|convert|converts|validate|validates|format|formats|render|renders|parse|parses|analy[sz]e|analy[sz]es|summari[sz]e|summari[sz]es|estimate|estimates|predict|predicts|forecast|forecasts|rank|ranks|recommend|recommends|compare|compares|classify|classifies|generate|generates)\b|计算|转换|验证|格式化|渲染|解析|分析|总结|估算|预测|推荐|比较|分类|生成"

def schema_evidence(node):
    """Collect documented descriptions/titles and property names recursively."""
    values = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"description", "title", "operationId", "summary"} and isinstance(value, str):
                values.append(value)
            if key == "properties" and isinstance(value, dict):
                values.extend(value.keys())
            values.extend(schema_evidence(value))
    elif isinstance(node, list):
        for value in node:
            values.extend(schema_evidence(value))
    return values

def classify(row):
    name = (row.get("tool_name") or "").strip()
    description = (row.get("description") or "").strip()
    try:
        schema = json.loads(row.get("input_schema_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        schema = {}
    schema_text = " ".join(schema_evidence(schema))
    primary = name + " " + description
    evidence = primary + " " + schema_text

    effects = [effect for effect, pattern in MUTATING if re.search(pattern, evidence, re.I)]
    http = re.search(r"\b(POST|PUT|PATCH|DELETE)\s+(?:request|operation|method)\b", evidence, re.I)
    if http:
        effect = {"POST": "write", "PUT": "write", "PATCH": "write", "DELETE": "delete"}[http.group(1).upper()]
        if effect not in effects:
            effects.append(effect)

    if effects:
        primary_mutation = any(re.search(pattern, primary, re.I) for effect, pattern in MUTATING if effect in {"money", "delete", "exec"})
        confidence = "0.70" if primary_mutation else "0.58"
        return ("true_candidate", "true", "|".join(effects), confidence,
                "Documented operation wording/schema contains explicit state-changing or execution semantics (" +
                ", ".join(effects) + "). Candidate only; no runtime observation.", schema_text)

    read_signal = bool(re.search(READ, primary, re.I))
    if (read_signal and description) or name.lower() in {"fetch-content", "search"}:
        return ("false_candidate", "false", "read", "0.52",
                "Documented name/description indicates retrieval/query/inspection; schema inspected for explicit mutation cues, none found. Candidate only; indirect effects not excluded.",
                schema_text)

    pure_signal = bool(re.search(PURE, primary, re.I))
    if pure_signal and description:
        return ("false_candidate", "false", "read", "0.48",
                "Documented name/description indicates computation/transformation; no explicit state-changing cue found in name, description, or schema. Candidate only; runtime effects not observed.",
                schema_text)

    return ("unresolved", "", "", "0.00",
            "UNRESOLVED: name, description, and schema do not provide sufficiently explicit effect evidence for a conservative binary candidate.",
            schema_text)

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
        status, label, effects, confidence, rationale, schema_excerpt = classify(row)
        row["semantic_status_v0_2"] = status
        row["semantic_non_read_only_candidate_v0_2"] = label
        row["semantic_effect_classes_v0_2"] = effects
        row["semantic_confidence_heuristic_v0_2"] = confidence
        row["semantic_evidence_rationale_v0_2"] = rationale
        row["schema_signal_excerpt_v0_2"] = " ".join(schema_excerpt.split())[:500]
        counts[status] += 1
    output = Path(args.output_csv)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(json.dumps({"rows": len(rows), "counts": dict(counts), "sha256": digest}, sort_keys=True))

if __name__ == "__main__":
    main()
