"""The paper's scenarios as executable registries, goal specifications and policies.

* ``reviews``  — motivating scenario (Fig. 1, Fig. 4, Fig. 6, Table 5): expected Γ = {g1, g5},
                 K = {db::query_reviews, report::generate}.
* ``github``   — Fig. 2 (reference servers GitHub, Slack, filesystem; Table 6):
                 K = {github::list_issues, slack::post_message}.
* ``revenue``  — Fig. 3: K = {postgres::query, stats::aggregate, filesystem::write_file,
                 slack::post_message}; aggregation is delegated because exact sums at n≈40,000 are
                 outside the model's reliable profile, and (L) holds via a declassification rule.

ρ values are the illustrative ones of the figures (Figs. 4 and 6), not measurements.
"""
from __future__ import annotations

from .contracts import QoS, make_contract
from .model_profile import ClassProfile, ModelProfile
from .policy import Declassification, Policy


def illustrative_profile(tau: float = 0.8) -> ModelProfile:
    """Profile with the illustrative reliabilities of Figs. 4 and 6 (strict=False: declared cells)."""
    def flat(v: float, nmax: int = 1000) -> ClassProfile:
        return ClassProfile([10, 100, nmax], [v, v, v * 0.97], [v, v, v * 0.97], [1, 1, 1], source="illustrative")
    classes = {"classify": flat(0.92), "extract": flat(0.86), "aggregate_sum": ClassProfile(
        [10, 100, 1000], [0.95, 0.6, 0.2], [0.95, 0.6, 0.2], [1, 1, 1], source="illustrative")}
    p = ModelProfile("illustrative", tau, classes, strict=False,
                     priors={"synthesise": 0.9, "write": 0.95, "summarise": 0.92, "convert_format": 0.95,
                             "plan": 0.92, "translate": 0.93})
    return p


# --------------------------------------------------------------------------- scenario 1
def reviews_registry():
    return [
        make_contract("db::query_reviews", {"q": "query"}, "record:review[]", ["read(db)"], "att",
                      tool_class="retrieve", description="Query the customer review database", source_label="private"),
        make_contract("nlp::sentiment", {"reviews": "record:review[]"}, "record:score[]", ["read(local)"], "ann",
                      tool_class="classify", description="Sentiment scores for reviews"),
        make_contract("nlp::classify", {"reviews": "record:review[]"}, "record:labeled[]", ["read(local)"], "obs",
                      kappa=0.9, tool_class="classify", description="Classify review text into labels"),
        make_contract("ml::cluster", {"vectors": "record:vector[]"}, "record:cluster[]", ["read(local)"], "lex",
                      tool_class="aggregate", description="Cluster vectors"),
        make_contract("nlp::extract", {"labeled": "record:labeled[]"}, "record:category[]", ["read(local)"], "ann",
                      tool_class="extract", description="Extract complaint categories"),
        make_contract("nlp::summarize", {"cats": "record:category[]"}, "text:summary", ["read(local)"], "lex",
                      tool_class="summarise", description="Summarise categories"),
        make_contract("stats::aggregate", {"scores": "record:score[]"}, "record:stats", ["read(local)"], "ann",
                      tool_class="aggregate", description="Aggregate statistics over scores"),
        make_contract("report::generate", {"findings": "record:findings"}, "document:report", ["write(/reports)"],
                      "ann", tool_class="create_document",
                      description="Generate a report file with findings and recommendations"),
        make_contract("viz::plot", {"table": "table"}, "media:image", ["read(local)"], "ann",
                      tool_class="render_media", description="Plot a report chart from a table"),
        make_contract("web::fetch", {"url": "url"}, "document:web", ["read(web)", "egress(*)"], "lex",
                      tool_class="fetch_web", description="Fetch a web page to retrieve reviews"),
        make_contract("mail::send", {"report": "document:report"}, "none", ["egress(mail)"], "ann",
                      tool_class="send", description="Send a report by e-mail"),
    ]


def reviews_spec() -> dict:
    return {"id": "scenario-reviews", "prompt_inputs": ["text"], "goals": [
        {"id": "g1", "desc": "retrieve reviews", "class": "retrieve", "in": ["query"], "out": "record:review[]",
         "eff": ["read(db)"], "sigma": "data", "n": 300},
        {"id": "g2", "desc": "analyze sentiment", "class": "classify", "in": ["record:review[]"],
         "out": "record:stats", "sigma": "native", "n": 300, "deps": ["g1"]},
        {"id": "g3", "desc": "extract complaints", "class": "extract", "in": ["record:review[]"],
         "out": "record:category[]", "sigma": "native", "n": 300, "deps": ["g1"]},
        {"id": "g4", "desc": "write recommendations", "class": "synthesise",
         "in": ["record:category[]", "record:stats"], "out": "record:findings", "sigma": "native", "n": 300,
         "deps": ["g2", "g3"]},
        {"id": "g5", "desc": "produce report file", "class": "create_document", "in": ["record:findings"],
         "out": "document:report", "eff": ["write(/reports)"], "sigma": "effect", "deps": ["g4"]},
        {"id": "g6", "desc": "frequency chart", "class": "render_media", "in": ["record:category[]"],
         "out": "media:image", "sigma": "data", "optional": True, "deps": ["g3"]},
    ]}


def reviews_policy() -> Policy:
    return Policy.make("reviews", required={"no_delete", "no_exec", "no_money"},
                       allowed=("read(db)", "read(local)", "write(/reports)"), lmin="ann",
                       egress_threshold="internal")


# --------------------------------------------------------------------------- scenario 2
def github_registry():
    return [
        make_contract("github::list_issues", {"repo": "identifier:repo", "filter": "text"}, "record:issue[]",
                      ["read(github)"], "att", tool_class="retrieve", description="List issues of a repository",
                      optional=["filter"]),
        make_contract("github::create_issue", {"repo": "identifier:repo", "issue": "record:issue"}, "record:issue",
                      ["write(github)"], "ann", tool_class="store", description="Create an issue"),
        make_contract("github::delete_repository", {"repo": "identifier:repo"}, "none", ["delete(github)"], "ann",
                      tool_class="store", description="Delete a repository", req=["admin_token"]),
        make_contract("slack::post_message", {"channel": "identifier:channel", "text": "text"}, "record:message",
                      ["egress(slack:#eng)"], "att", tool_class="send", description="Post a message to a channel"),
        make_contract("slack::list_channels", {}, "identifier:channel[]", ["read(slack)"], "ann",
                      tool_class="retrieve", description="List channels"),
        make_contract("filesystem::read_file", {"path": "path"}, "text", ["read(fs)"], "obs",
                      tool_class="retrieve", description="Read a file", source_label="private"),
        make_contract("filesystem::write_file", {"path": "path", "content": "text"}, "none", ["write(fs)"], "obs",
                      tool_class="store", description="Write a file"),
        make_contract("fetch::fetch", {"url": "url"}, "text", ["read(web)", "egress(*)"], "lex",
                      tool_class="fetch_web", description="Fetch a URL"),
        make_contract("brave-search::brave_web_search", {"query": "query"}, "record:search_result[]",
                      ["read(web)", "egress(brave)"], "ann", tool_class="search", description="Web search"),
        make_contract("memory::create_entities", {"entities": "record:entity[]"}, "none", ["session"], "ann",
                      tool_class="store", description="Store entities in memory"),
        make_contract("puppeteer::navigate", {"url": "url"}, "record:page", ["read(web)", "egress(*)", "exec"], "lex",
                      tool_class="navigate_browser", description="Navigate a browser"),
    ]


def github_spec() -> dict:
    return {"id": "scenario-github-slack", "prompt_inputs": ["text", "identifier:repo", "identifier:channel"],
            "goals": [
                {"id": "g1", "desc": "list open bug issues", "class": "retrieve", "in": ["identifier:repo"],
                 "out": "record:issue[]", "eff": ["read(github)"], "sigma": "data", "n": 1},
                {"id": "g2", "desc": "summarise issues into a digest", "class": "summarise",
                 "in": ["record:issue[]"], "out": "text:digest", "sigma": "native", "n": 40, "deps": ["g1"]},
                {"id": "g3", "desc": "post digest to slack", "class": "send", "in": ["identifier:channel", "text:digest"],
                 "out": "none", "eff": ["egress(slack:#eng)"], "sigma": "effect", "deps": ["g2"]}]}


def github_policy() -> Policy:
    return Policy.make("github-slack", required={"no_delete", "no_exec", "no_money"},
                       allowed=("read(github)", "egress(slack:#eng)"), lmin="obs", egress_threshold="internal")


# --------------------------------------------------------------------------- scenario 3
def revenue_registry():
    return [
        make_contract("postgres::query", {"sql": "query:sql"}, "table:sales", ["read(db)"], "obs",
                      tool_class="retrieve", description="Run a read-only SQL query", source_label="private"),
        make_contract("postgres::execute", {"sql": "query:sql"}, "none", ["write(db)", "exec"], "ann",
                      tool_class="execute", description="Execute SQL statements"),
        make_contract("filesystem::write_file", {"path": "path", "content": "table:revenue"}, "none",
                      ["write(/reports)"], "obs", tool_class="store", description="Write a file"),
        make_contract("filesystem::move_file", {"src": "path", "dst": "path"}, "none", ["write(*)"], "obs",
                      tool_class="store", description="Move a file"),
        make_contract("slack::post_message", {"channel": "identifier:channel", "text": "text"}, "record:message",
                      ["egress(slack:#finance)"], "att", tool_class="send", description="Post a message"),
        make_contract("slack::list_channels", {}, "identifier:channel[]", ["read(slack)"], "ann",
                      tool_class="retrieve", description="List channels"),
        make_contract("fetch::fetch", {"url": "url"}, "text", ["read(web)", "egress(*)"], "lex",
                      tool_class="fetch_web", description="Fetch a URL"),
        make_contract("stats::aggregate", {"table": "table:sales"}, "table:revenue", ["read(local)"], "obs",
                      tool_class="aggregate", description="Exact group-by aggregation (sums per group)",
                      qos=QoS(0.0, 0.5, 0.01)),
    ]


def revenue_spec() -> dict:
    return {"id": "scenario-revenue", "prompt_inputs": ["text", "path", "identifier:channel"], "goals": [
        {"id": "g1", "desc": "query last week's sales", "class": "retrieve", "in": ["query:sql"], "out": "table:sales",
         "eff": ["read(db)"], "sigma": "data", "n": 40000},
        {"id": "g2", "desc": "aggregate revenue per region", "class": "aggregate", "in": ["table:sales"],
         "out": "table:revenue", "sigma": "native", "n": 40000, "exactness": "exact", "deps": ["g1"]},
        {"id": "g3", "desc": "write the table to /reports/weekly.csv", "class": "store",
         "in": ["table:revenue", "path"], "out": "none", "eff": ["write(/reports)"], "sigma": "effect",
         "deps": ["g2"]},
        {"id": "g4", "desc": "notify #finance", "class": "send", "in": ["identifier:channel", "text"], "out": "none",
         "eff": ["egress(slack:#finance)"], "sigma": "effect", "deps": ["g2"]}]}


def revenue_policy() -> Policy:
    return Policy.make("revenue", required={"no_delete", "no_money"},
                       allowed=("read(db)", "read(local)", "write(/reports)", "egress(slack:#finance)"), lmin="obs",
                       egress_threshold="internal",
                       declass=(Declassification("private", "internal", frozenset({"aggregate"}), frozenset(),
                                                 "obs", 10),))


SCENARIOS = {
    "reviews": (reviews_registry, reviews_spec, reviews_policy,
                {"gap": ["g1", "g5"], "toolkit": ["db::query_reviews", "report::generate"]}),
    "github": (github_registry, github_spec, github_policy,
               {"gap": ["g1", "g3"], "toolkit": ["github::list_issues", "slack::post_message"]}),
    "revenue": (revenue_registry, revenue_spec, revenue_policy,
                {"gap": ["g1", "g2", "g3", "g4"],
                 "toolkit": ["filesystem::write_file", "postgres::query", "slack::post_message", "stats::aggregate"]}),
}
