# Model-profile self-assessment (E12 control)

You will later be given data items in your context and asked a question about them, which you must answer
by reading only (no tools, no code, no calculator). Before seeing any item, estimate for yourself the
probability (0-1) that your answer would be exactly correct, for each class and input size n (number of
data lines in the item):

* `aggregate_sum` — "What is the exact sum of all the numbers listed below (one per line)?" (2-digit numbers)
* `count` — "How many lines below are exactly the word 'noise'?" (exact count over n short lines)
* `classify` — "Classify each review below as positive or negative. Is the majority positive or negative?"
* `extract` — "In the records below, which city belongs to the record with id K3373000?" (one record among n)

Sizes: n in {10, 40, 160, 640}.

Output a single JSON object: {"model": "<your model name>", "self_assessment": {"<class>": {"10": p, "40": p,
"160": p, "640": p}, ...}} with all 4 classes and 4 sizes.
