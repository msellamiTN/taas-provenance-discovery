"""Revision 2, model-profile calibration suite (review Major 11): deterministic item generator with gold answers.

Classes: classify (count of negative reviews), extract (ids of records with a given status), aggregate_sum (exact or
approximate sum), count (occurrences of a word), compute_exactly (maximum value and its id), join (ids of list A that
appear in list B). Translation and free-text synthesis are not included: they have no exact gold answer without human
judges. Dimensions: n in {10, 40, 160, 640}; language en/fr; input clean/noisy (typos, missing or malformed fields);
context isolated/embedded (the question is step 2 of a three-step instruction). Exactness: sums are asked exactly or
within 5% (alternating). Items per cell: 3, 3, 2, 1 for the four sizes -> 432 items. Split: calibration/test,
alternating within each cell (n = 640 alternates across the cells of a class).
Writes data/llm_inputs/r2_calibration/{items.json, gold.json, batch_<k>.md, self_assessment.md}.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "llm_inputs" / "r2_calibration"
SIZES = (10, 40, 160, 640)
PER = {10: 3, 40: 3, 160: 2, 640: 1}
CLASSES = ("classify", "extract", "aggregate_sum", "count", "compute_exactly", "join")
CITIES = ["Tunis", "Sfax", "Lyon", "Porto", "Oslo", "Lima", "Cairo", "Quito", "Pune", "Graz"]
POS = {"en": ["great product, works perfectly", "very happy with it", "excellent quality and fast delivery",
              "love it, would buy again", "does exactly what it says"],
       "fr": ["excellent produit, fonctionne parfaitement", "très satisfait", "qualité excellente et livraison rapide",
              "j'adore, je rachèterai", "fait exactement ce qui est annoncé"]}
NEG = {"en": ["broke after two days", "very disappointed", "poor quality, returned it", "does not work at all",
              "waste of money"],
       "fr": ["cassé après deux jours", "très déçu", "mauvaise qualité, renvoyé", "ne fonctionne pas du tout",
              "argent gaspillé"]}
HARD_NEG = {"en": ["not bad at first, then it stopped working", "I wanted to love it, but it failed"],
            "fr": ["pas mal au début, puis il a cessé de fonctionner", "je voulais l'aimer, mais il a échoué"]}
STATUS = {"en": ["shipped", "refunded", "pending"], "fr": ["expédié", "remboursé", "en attente"]}
WORDS = {"en": ["noise", "signal", "echo", "pulse"], "fr": ["bruit", "signal", "écho", "pouls"]}
Q = {
    "classify": {"en": "How many of the reviews below are negative? Answer with one integer.",
                 "fr": "Combien des avis ci-dessous sont négatifs ? Répondez par un entier."},
    "extract": {"en": "List the ids of all records whose status is '{s}'. Answer with the ids separated by commas.",
                "fr": "Donnez les identifiants de tous les enregistrements dont le statut est '{s}'. Séparez-les par des virgules."},
    "aggregate_sum": {"en": "What is the {m} sum of all the numbers below? Answer with one number.",
                      "fr": "Quelle est la somme {m} de tous les nombres ci-dessous ? Répondez par un nombre."},
    "count": {"en": "How many times does the word '{w}' appear in the list below? Answer with one integer.",
              "fr": "Combien de fois le mot '{w}' apparaît-il dans la liste ci-dessous ? Répondez par un entier."},
    "compute_exactly": {"en": "Which record has the largest value? Answer as 'id,value'.",
                        "fr": "Quel enregistrement a la plus grande valeur ? Répondez sous la forme 'id,valeur'."},
    "join": {"en": "How many ids of list A also appear in list B? Answer with one integer.",
             "fr": "Combien d'identifiants de la liste A apparaissent aussi dans la liste B ? Répondez par un entier."},
}
EXACT_WORD = {"en": {"exact": "exact", "approx": "approximate (within 5%)"},
              "fr": {"exact": "exacte", "approx": "approximative (à 5 % près)"}}
EMBED = {"en": ("Step 1: read the data. Step 2: {q} Step 3: do not explain. Report only the answer to step 2.",),
         "fr": ("Étape 1 : lisez les données. Étape 2 : {q} Étape 3 : n'expliquez pas. Donnez seulement la réponse à "
                "l'étape 2.",)}


def typo(s, rng):
    if len(s) < 4:
        return s
    i = rng.randrange(1, len(s) - 1)
    return s[:i] + s[i + 1] + s[i] + s[i + 2:]


def make(cls, n, lang, noisy, embedded, k, rng):
    meta = {}
    if cls == "classify":
        lines, neg = [], 0
        for i in range(n):
            r = rng.random()
            if r < 0.4:
                txt = rng.choice(NEG[lang]); neg += 1
            elif r < 0.5:
                txt = rng.choice(HARD_NEG[lang]); neg += 1
            else:
                txt = rng.choice(POS[lang])
            if noisy and rng.random() < 0.3:
                txt = typo(txt, rng)
            lines.append(f"[{i + 1}] {txt}")
        q, gold, kind = Q[cls][lang], neg, "int"
    elif cls == "extract":
        s = STATUS[lang][1]
        lines, gold = [], []
        for i in range(n):
            rid = f"K{rng.randrange(10 ** 6, 10 ** 7)}"
            st = s if rng.random() < 0.1 else rng.choice([STATUS[lang][0], STATUS[lang][2]])
            city = rng.choice(CITIES)
            if noisy and rng.random() < 0.15:
                city = "?"
            lines.append(f"id={rid}; city={city}; status={st}")
            if st == s:
                gold.append(rid)
        if not gold:
            lines[0] = lines[0].rsplit("status=", 1)[0] + f"status={s}"
            gold.append(lines[0].split(";")[0][3:])
        q, kind = Q[cls][lang].format(s=s), "set"
    elif cls == "aggregate_sum":
        mode = "exact" if k % 2 == 0 else "approx"
        nums = [rng.randrange(10, 100) for _ in range(n)]
        lines = [f" {x} " if noisy and rng.random() < 0.2 else str(x) for x in nums]
        q, gold, kind = Q[cls][lang].format(m=EXACT_WORD[lang][mode]), sum(nums), ("int" if mode == "exact" else "approx")
        meta["exactness"] = mode
    elif cls == "count":
        w = WORDS[lang][0]
        toks = [rng.choice(WORDS[lang]) for _ in range(n)]
        gold = sum(1 for x in toks if x == w)
        lines = [typo(x, rng) if noisy and x != w and rng.random() < 0.2 else x for x in toks]
        q, kind = Q[cls][lang].format(w=w), "int"
    elif cls == "compute_exactly":
        vals = {}
        lines = []
        for i in range(n):
            rid = f"R{rng.randrange(10 ** 5, 10 ** 6)}"
            v = round(rng.uniform(0, 1000), 2)
            vals[rid] = v
            lines.append(f"{rid}: {v}" if not (noisy and rng.random() < 0.15) else f"{rid} : {v:.2f}")
        best = max(vals, key=vals.get)
        q, gold, kind = Q[cls][lang], f"{best},{vals[best]}", "idvalue"
    else:  # join
        A = [f"U{rng.randrange(10 ** 5, 10 ** 6)}" for _ in range(n)]
        B = rng.sample(A, n // 4) + [f"U{rng.randrange(10 ** 5, 10 ** 6)}" for _ in range(n // 4)]
        rng.shuffle(B)
        gold = len(set(A) & set(B))
        if noisy:
            B = [x.lower() if rng.random() < 0.1 else x for x in B]
            gold = len(set(A) & {x.upper() for x in B})
            meta["note"] = "ids compare case-insensitively"
        lines = ["A: " + ", ".join(A), "B: " + ", ".join(B)]
        q, kind = Q[cls][lang], "int"
    if embedded:
        q = EMBED[lang][0].format(q=q)
    return {"class": cls, "n": n, "lang": lang, "noisy": noisy, "embedded": embedded, "question": q,
            "data": lines, "kind": kind, **meta}, gold


def main() -> None:
    rng = random.Random(2026)
    OUT.mkdir(parents=True, exist_ok=True)
    items, gold = [], {}
    for cls in CLASSES:
        flip = 0
        for n in SIZES:
            for lang in ("en", "fr"):
                for noisy in (False, True):
                    for embedded in (False, True):
                        for k in range(PER[n]):
                            it, g = make(cls, n, lang, noisy, embedded, k, rng)
                            iid = f"{cls[:3]}-{n}-{lang}-{int(noisy)}{int(embedded)}-{k}"
                            split = ("calibration" if k % 2 == 0 else "test") if PER[n] > 1 else \
                                ("calibration" if flip % 2 == 0 else "test")
                            if PER[n] == 1:
                                flip += 1
                            items.append({"id": iid, "split": split, **it})
                            gold[iid] = g
    json.dump(items, open(OUT / "items.json", "w"), ensure_ascii=False, indent=0)
    json.dump(gold, open(OUT / "gold.json", "w"), ensure_ascii=False, indent=0)
    # batches of about 50k characters of item text, same batches for every model
    batches, cur, size = [], [], 0
    for it in items:
        txt = f"### ITEM {it['id']}\n{it['question']}\n" + "\n".join(it["data"]) + "\n"
        if cur and size + len(txt) > 50000:
            batches.append(cur); cur, size = [], 0
        cur.append(txt); size += len(txt)
    if cur:
        batches.append(cur)
    for b, chunk in enumerate(batches):
        (OUT / f"batch_{b:02d}.md").write_text(
            "Answer every item below by reading only. Do not use any tool other than reading this file, and do not "
            "write code. For each item give only the answer in the requested format.\n\n" + "\n".join(chunk))
    cells = sorted({(it["class"], it["n"], it["lang"], it["noisy"], it["embedded"]) for it in items})
    (OUT / "self_assessment.md").write_text(
        "You will later answer data questions by reading only (no tools, no code). Before seeing any item, estimate the "
        "probability (0-1) that your answer would be exactly correct for each cell below. Classes: classify = count the "
        "negative reviews; extract = list the ids of records with a given status; aggregate_sum = sum of 2-digit "
        "numbers (exact, or within 5% for half of the items); count = occurrences of a word; compute_exactly = id and "
        "value of the maximum; join = number of ids of list A present in list B. n = number of data lines (for join, "
        "the size of list A). lang = language of the instructions and data. noisy = typos or malformed fields. "
        "embedded = the question is step 2 of a three-step instruction.\n\nCells (class, n, lang, noisy, embedded):\n" +
        "\n".join(f"{c}|{n}|{l}|{int(z)}|{int(e)}" for c, n, l, z, e in cells) +
        "\n\nReturn one JSON object mapping each cell string exactly as written to a probability.")
    print(len(items), "items,", len(batches), "batches,", len(cells), "cells")


if __name__ == "__main__":
    main()
