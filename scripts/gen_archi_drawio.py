"""Generate docs/archi/taas-lad.drawio and docs/archi/taas-pad.drawio.

Architecture-as-code: pages are declared as node/edge lists against a shared
style vocabulary (real draw.io stencils) and a disciplined grid, so the
enterprise diagrams stay consistent with the SoW/LAD/PAD text.

Run:  python scripts/gen_archi_drawio.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "archi"

# ---------------------------------------------------------------- palette --
C_CONSUMER = "fillColor=#dae8fc;strokeColor=#6c8ebf;"
C_GOV      = "fillColor=#d5e8d4;strokeColor=#82b366;"
C_IDENT    = "fillColor=#fff2cc;strokeColor=#d6b656;"
C_STORE    = "fillColor=#e1d5e7;strokeColor=#9673a6;"
C_BACKEND  = "fillColor=#ffe6cc;strokeColor=#d79b00;"
C_RISK     = "fillColor=#f8cecc;strokeColor=#b85450;"
C_NEUT     = "fillColor=#f5f5f5;strokeColor=#666666;"
C_ACCENT   = "fillColor=#1ba1e2;strokeColor=#006EAF;fontColor=#ffffff;"

BOX   = "rounded=1;whiteSpace=wrap;html=1;fontSize=11;arcSize=8;align=center;verticalAlign=middle;"
BOXL  = BOX + "align=left;spacingLeft=8;verticalAlign=middle;"
TXT   = "text;html=1;fontSize=11;align=left;spacingLeft=4;"
TITLE = "text;html=1;fontSize=12;fontStyle=2;fontColor=#333333;"
DASH  = "dashed=1;dashPattern=3 3;"

def zone(fill, stroke, extra=""):
    return (f"swimlane;startSize=26;html=1;fontSize=12;fontStyle=1;"
            f"fillColor={fill};strokeColor={stroke};rounded=1;{extra}")

def vstyle(color, dashed=False):
    return BOX + color + (DASH if dashed else "")

def vlstyle(color, dashed=False):
    return BOXL + color + (DASH if dashed else "")

EDGE   = "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;fontSize=10;endArrow=block;strokeWidth=1.5;"
EDASH  = EDGE + "dashed=1;dashPattern=4 4;"

# ------------------------------------------------------------- stencils ----
ICON = {
    "k8s_pod":  "shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/kubernetes/1/pod.svg",
    "k8s_svc":  "shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/kubernetes/1/svc.svg",
    "k8s_netpol":"shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/kubernetes/1/netpol.svg",
    "k8s_cm":   "shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/kubernetes/1/cm.svg",
    "k8s_secret":"shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/kubernetes/1/secret.svg",
    "aws_gw":   "sketch=0;outlineConnect=0;fontColor=#232F3E;fillColor=#8C4FFF;strokeColor=#ffffff;html=1;fontSize=10;aspect=fixed;verticalLabelPosition=bottom;verticalAlign=top;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.api_gateway;",
    "az_gw":    "image;aspect=fixed;html=1;align=center;fontSize=10;verticalLabelPosition=bottom;verticalAlign=top;image=https://app.diagrams.net/img/lib/azure2/integration/AI_Gateway.svg;",
    "az_entra": "image;aspect=fixed;html=1;align=center;fontSize=10;verticalLabelPosition=bottom;verticalAlign=top;image=https://app.diagrams.net/img/lib/azure2/identity/Entra_ID_Protection.svg;",
    "az_kv":    "shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/azure/1/Key_Vault.svg",
    "az_fw":    "shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/azure/1/Azure_Firewall.svg",
    "az_dns":   "shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/azure/1/DNS.svg",
    "az_lb":    "shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/azure/1/Load_Balancer.svg",
    "user":     "shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/azure/1/Users.svg",
    "db":       "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=12;fontSize=10;" + C_STORE,
    "shield":   "shape=image;html=1;verticalAlign=top;verticalLabelPosition=bottom;labelBackgroundColor=default;imageAspect=0;aspect=fixed;fontSize=10;image=https://icons.diagrams.net/assets/azure/1/Multi-Factor_Authentication.svg",
}

class P:
    """Page builder: collects mxCell XML for one diagram."""
    def __init__(self, page_w=1400, page_h=900):
        self.cells = []
        self.w, self.h = page_w, page_h
        self.n = 0

    def _id(self, base):
        self.n += 1
        return base or f"c{self.n}"

    def _val(self, v):
        return escape(v, {chr(34): "&quot;"}).replace("\n", "&lt;br&gt;")

    def node(self, id, value, style, x, y, w=170, h=60, parent="1"):
        id = self._id(id)
        self.cells.append(
            f'<mxCell id="{id}" value="{self._val(value)}" '
            f'style="{style}" vertex="1" parent="{parent}">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return id

    def edge(self, src, dst, label="", dashed=False):
        id = self._id(None)
        self.cells.append(
            f'<mxCell id="{id}" value="{self._val(label)}" style="{EDASH if dashed else EDGE}" '
            f'edge="1" source="{src}" target="{dst}" parent="1">'
            f'<mxGeometry relative="1" as="geometry"/></mxCell>')

    def title(self, text):
        self.node(None, text, TITLE, 40, 12, 1200, 26)

    def legend(self, text, y=640, x=40, w=1200):
        self.node(None, text, TXT, x, y, w, 40)

    def render(self):
        return (f'<mxGraphModel dx="1000" dy="700" grid="1" gridSize="10" guides="1" '
                f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
                f'pageWidth="{self.w}" pageHeight="{self.h}" math="0" shadow="0">'
                f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>'
                + "".join(self.cells) + "</root></mxGraphModel>")


def mxfile(pages):
    body = "".join(
        f'  <diagram name="{name}" id="{pid}">{xml}</diagram>\n'
        for name, pid, xml in pages)
    return ('<mxfile host="app.diagrams.net" agent="taas" version="24.0.0">\n'
            + body + "</mxfile>\n")


# ================================================================ LAD pages

def build_lad_p1():
    p = P()
    p.title("LAD-01 · System context — consumers reach backends only through the governed access layer")
    z = p.node(None, "Consumers", zone("#f5f5f5", "#666666"), 40, 60, 210, 560)
    c1 = p.node(None, "Business apps\nfrontends", vstyle(C_CONSUMER), 30, 60, 150, 55, z)
    c2 = p.node(None, "Agents", vstyle(C_CONSUMER), 30, 150, 150, 55, z)
    c3 = p.node(None, "M2M service clients", vstyle(C_CONSUMER), 30, 240, 150, 55, z)
    p.node(None, "", ICON["user"], 70, 330, 60, 60, z)

    z2 = p.node(None, "Governed access layer", zone("#eaf6ea", "#4d7a4d"), 300, 60, 500, 560)
    gw = p.node(None, "API Gateway\nTLS·WAF·quota·2MiB", vstyle(C_GOV, True), 160, 40, 180, 60, z2)
    px = p.node(None, "MCP proxy\nfiltered tools/list · call gated", vstyle(C_GOV, True), 160, 130, 180, 60, z2)
    tb = p.node(None, "Bearer-token broker\nOAuth2.1·8693·6750·opaque", vstyle(C_IDENT, True), 30, 240, 200, 65, z2)
    rg = p.node(None, "TaaS registry\ncatalogue·lifecycle·policy·health", vstyle(C_STORE), 270, 240, 200, 65, z2)
    p.node(None, "Policy engine\nexposure·quota·approvals", vstyle(C_IDENT, True), 30, 340, 200, 60, z2)
    p.node(None, "Audit + observability\nhash chain · request-ID", vstyle(C_STORE), 270, 340, 200, 60, z2)
    p.node(None, "solid = delivered · dashed = design seam", TXT, 60, 440, 360, 40, z2)

    z3 = p.node(None, "Runtimes", zone("#fdf3e7", "#a66a3f"), 860, 60, 230, 250)
    p.node(None, "Mistral", vstyle(C_BACKEND), 30, 50, 170, 50, z3)
    rt = p.node(None, "Vertex / Bedrock / Foundry", vstyle(C_BACKEND), 30, 115, 170, 50, z3)
    p.node(None, "Ollama / vLLM / local", vstyle(C_BACKEND), 30, 180, 170, 50, z3)

    z4 = p.node(None, "Tool & resource backends", zone("#fbeaea", "#a05a5a"), 860, 350, 230, 270)
    b1 = p.node(None, "Private MCP services", vstyle(C_RISK), 30, 50, 170, 50, z4)
    b2 = p.node(None, "REST→MCP adapter\nJDE / WSO2-class", vstyle(C_RISK, True), 30, 115, 170, 55, z4)
    b3 = p.node(None, "SaaS MCP (controlled egress)", vstyle(C_RISK), 30, 185, 170, 50, z4)

    for c in (c1, c2, c3):
        p.edge(c, gw)
    p.edge(tb, gw, "validate+exchange")
    p.edge(rg, px, "policy/exposure")
    p.edge(gw, px)
    for b in (b1, b2, b3):
        p.edge(px, b)
    p.edge(px, rt, "Phase C only", dashed=True)
    p.legend("Invariant: proposal ≠ evidence ≠ authorization ≠ execution — inspection today, governed execution Phase C only.")
    return p


def build_lad_p2():
    p = P()
    p.title("LAD-02 · Consumer access sequence — numbered hops, every hop audited")
    c = p.node("c", "Consumer\n(Bearer token)", vstyle(C_CONSUMER), 40, 150, 150, 60)
    gw = p.node("gw", "API Gateway\nedge controls", vstyle(C_GOV, True), 280, 150, 170, 60)
    tb = p.node("tb", "Token broker / IdP\nOAuth 2.1 · RFC 8693 · opaque", vstyle(C_IDENT, True), 560, 50, 240, 65)
    rg = p.node("rg", "Registry\npolicy profile + exposure set", vstyle(C_STORE), 560, 160, 240, 60)
    px = p.node("px", "MCP proxy\nfiltered tools/list · call gated", vstyle(C_GOV, True), 560, 280, 240, 60)
    bk = p.node("bk", "MCP backend\n(LB / private endpoint)", vstyle(C_RISK), 900, 280, 200, 60)
    fg = p.node("fg", "Fine-grained authZ\nAuthZEN → ABAC/ReBAC\nnormalized 403 · step-up 6750", vstyle(C_IDENT, True), 900, 60, 240, 80)
    au = p.node("au", "Audit\nrequest-ID + caller context", vstyle(C_STORE), 280, 280, 170, 60)
    p.edge(c, gw, "1 HTTPS+Bearer")
    p.edge(gw, tb, "2 validate/exchange")
    p.edge(gw, rg, "3 resolve profile")
    p.edge(gw, px, "4 route approved")
    p.edge(px, bk, "5 governed call")
    p.edge(px, fg, "D9 FGA check", dashed=True)
    p.edge(gw, au, "audit each hop", dashed=True)
    p.legend("Deny paths: missing/invalid token → 401 · wrong audience → 401 · over-scope tool → 403+step-up · disallowed backend → deny+log.", y=420)
    return p


def build_lad_p3():
    p = P()
    p.title("LAD-03 · Provisioning & lifecycle — READY only after smoke tests")
    orc = p.node("or", "Provisioning orchestrator\n(Backstage/Camunda-class)", vstyle(C_IDENT, True), 40, 90, 230, 65)
    s1 = p.node("s1", "1 REGISTER\nidempotency key + corr-ID", vstyle(C_CONSUMER), 360, 40, 190, 60)
    s2 = p.node("s2", "2 VALIDATE\nmanifest / schema", vstyle(C_CONSUMER), 590, 40, 190, 60)
    s3 = p.node("s3", "3 APPLY\ngateway route + policy", vstyle(C_GOV, True), 820, 40, 190, 60)
    s4 = p.node("s4", "4 SMOKE TEST\nhealth + auth + route", vstyle(C_IDENT, True), 820, 170, 190, 60)
    s5 = p.node("s5", "5 READY → PUBLISHED\nonly on pass", vstyle(C_GOV), 590, 170, 190, 60)
    rg = p.node("rg", "TaaS registry\n(state machine)", vstyle(C_STORE), 360, 170, 190, 60)
    fl = p.node("fl", "fail → compensate\nbounded retries · timeout", "rhombus;whiteSpace=wrap;html=1;fontSize=11;" + C_RISK, 820, 300, 190, 90)
    dr = p.node("dr", "Drift reconciliation\nscheduled compare gw↔registry → alert/correct", vstyle(C_RISK, True), 360, 320, 420, 60)
    p.edge(orc, s1); p.edge(s1, s2); p.edge(s2, s3); p.edge(s3, s4)
    p.edge(s4, s5, "pass"); p.edge(s4, fl, "fail"); p.edge(s5, rg); p.edge(s1, rg)
    p.edge(dr, rg, "", dashed=True)
    p.legend("Lifecycle: REGISTERED → VALIDATED → READY FOR CONSUMPTION → PUBLISHED → REVOKED/DECOMMISSIONED — configuration states, never runtime states.", y=420)
    return p


def build_lad_p4():
    p = P()
    p.title("LAD-04 · Inspection vs invocation — the execution boundary")
    l1 = p.node(None, "Today — inspection (delivered)", zone("#eaf6ea", "#4d7a4d", "horizontal=0;"), 40, 60, 1160, 190)
    a1 = p.node("a1", "Studio API\n/discovery · /mcp/servers", vstyle(C_GOV), 130, 60, 210, 60, l1)
    a2 = p.node("a2", "tools/list inspect\ninspection_only=true\ntool_execution_performed=false", vstyle(C_GOV), 420, 55, 230, 75, l1)
    a3 = p.node("a3", "Registry snapshot\n+ persisted runs + audit", vstyle(C_STORE), 730, 60, 210, 60, l1)
    p.edge(a1, a2); p.edge(a2, a3)
    l2 = p.node(None, "Phase C — governed invocation (design only)", zone("#fbeaea", "#a05a5a", "horizontal=0;"), 40, 290, 1160, 200)
    b1 = p.node("b1", "Gateway", vstyle(C_RISK, True), 120, 70, 140, 60, l2)
    b2 = p.node("b2", "Policy check\n+ AuthZEN FGA", vstyle(C_RISK, True), 320, 70, 170, 60, l2)
    b3 = p.node("b3", "PEP + isolated worker\nfresh evidence\none-time approval", vstyle(C_RISK, True), 550, 60, 210, 90, l2)
    b4 = p.node("b4", "tools/call\n(audited)", vstyle(C_RISK, True), 830, 70, 160, 60, l2)
    p.edge(b1, b2); p.edge(b2, b3); p.edge(b3, b4)
    p.legend("No /tools/call route exists in the control-plane API. A selected toolkit or valid certificate never implies execution.", y=520)
    return p


def build_lad_p5():
    p = P()
    p.title("LAD-05 · Registry data model — italic = design-seam extension fields (E1–E3)")
    ag = p.node("ag", "Agent (v1alpha1)\n────────\nmodel · instructions\ntool_allowlist · resources\napproval · lifecycle_state\n+ identity.workload_identity_ref\n+ exposure { publish_via, scopes }", vlstyle(C_CONSUMER), 60, 70, 300, 180)
    mc = p.node("mc", "MCP server\n────────\nid · transport · inspection history\nhealth · lifecycle_state\n+ exposure { mode, route_ref,\n private_endpoint, dns_name,\n adapter, backends[] }", vlstyle(C_CONSUMER), 60, 300, 300, 180)
    pp = p.node("pp", "Policy profile\n────────\nselection policy (UX-17)\n+ exposure_rules { consumer_scopes,\n tools_visible, tools_callable*,\n egress_class, quota }", vlstyle(C_IDENT, True), 450, 70, 310, 160)
    ep = p.node("ep", "Endpoint\n────────\nprivate FQDN / route_ref\nservice attachment / LB ref\n(never a raw-IP runtime claim)", vlstyle(C_BACKEND), 450, 300, 310, 120)
    ev = p.node("ev", "Evidence / audit\n────────\nhash-chained events · signed bundles\nrequest_id ↔ seq\n+ kinds: exposure.* · gateway.decision\n · token.exchange", vlstyle(C_STORE), 830, 70, 310, 160)
    lc = p.node("lc", "Lifecycle\nREGISTERED→VALIDATED→READY\n→PUBLISHED→REVOKED\n(config states, never runtime)", vlstyle(C_GOV), 830, 300, 310, 120)
    p.edge(ag, mc, "tool grants")
    p.edge(ag, pp, "policy_profile_ref")
    p.edge(mc, ep)
    p.edge(ag, ev)
    p.edge(mc, lc)
    return p


def build_lad_p6():
    p = P()
    p.title("LAD-06 · Five identity domains + control layers + threat map")
    i1 = p.node("i1", "1 Consumer\nprincipal", vstyle(C_CONSUMER), 60, 70, 160, 55)
    i2 = p.node("i2", "2 End-user\nprincipal", vstyle(C_CONSUMER), 60, 155, 160, 55)
    i3 = p.node("i3", "3 Gateway\nworkload identity", vstyle(C_GOV), 330, 70, 170, 55)
    i4 = p.node("i4", "4 Agent runtime\nidentity", vstyle(C_BACKEND), 580, 70, 170, 55)
    i5 = p.node("i5", "5 Backend / MCP\nidentity", vstyle(C_RISK), 830, 70, 170, 55)
    p.edge(i1, i3, "exchange/delegate"); p.edge(i2, i3, "on-behalf-of")
    p.edge(i3, i4); p.edge(i4, i5, "own authZ")
    p.node("cl", "Control layers\nEdge TLS/WAF/size → Identity (validate+exchange)\n→ Policy (exposure/quota) → Routing (allowlist)\n→ Audit (correlated) → Observability", vlstyle(C_IDENT), 60, 270, 450, 120)
    p.node("th", "Threat → control\n────────\nconfused deputy → no passthrough (D5)\naudience misuse → iss/aud/sig/exp checks\nover-exposed tools → filtered tools/list\nSSRF → FQDN allowlists, no raw IP\ninjection→unsafe call → tools/call PEP-gated\ninsufficient scope → 403 + step-up (6750)\nfine-grained rules → AuthZEN→ReBAC/ABAC\nsecret leakage → no payload logs · opaque tokens\nreplay/DoS → quotas + 2 MiB cap\ncross-tenant → RBAC + isolation (Phase B)", vlstyle(C_RISK), 560, 270, 500, 260)
    return p


def build_lad_p7():
    p = P()
    p.title("LAD-07 · Decision map — D1..D14 around the centralized gateway")
    core = p.node("core", "Centralized\nMCP gateway\n(D1)", "ellipse;whiteSpace=wrap;html=1;fontSize=12;" + C_GOV, 560, 210, 160, 110)
    ds = [
        ("d2", "D2 Token broker\nIdP-agnostic", 90, 60, C_IDENT),
        ("d9", "D9 AuthZEN→ReBAC/ABAC", 330, 60, C_IDENT),
        ("d6", "D6 REST→MCP adapter", 700, 60, C_IDENT),
        ("d8", "D8 Orchestrated prov.\n+ drift", 950, 60, C_IDENT),
        ("d11", "D11 MCP session &\nnotification policy", 1160, 60, C_RISK),
        ("d3", "D3 Gateway per env\nK8s GW API / ApigeeX /\nPrivateLink / Private Link", 90, 220, C_IDENT),
        ("d13", "D13 Sender-constrained\ntokens (DPoP/mTLS)", 1160, 220, C_IDENT),
        ("d5", "D5 No token\npassthrough", 330, 400, C_RISK),
        ("d4", "D4 Control plane\ninspection-only", 90, 400, C_CONSUMER),
        ("d7", "D7 Registry owns\nlifecycle ≠ runtime", 700, 400, C_IDENT),
        ("d10", "D10 OAuth2.1·8693\n·6750·opaque", 950, 400, C_IDENT),
        ("d12", "D12 External audit\nanchoring (WORM)", 90, 540, C_RISK),
        ("d14", "D14 Enforcement-domain\nseparation (PEP)", 330, 540, C_RISK),
    ]
    ids = []
    for i, (pid, lbl, x, y, col) in enumerate(ds):
        ids.append(p.node(pid, lbl, vstyle(col), x, y, 190, 70))
    for d in ids:
        p.edge(d, core)
    p.node(None, "D11–D14 added from principal-architect threat review: MCP session semantics, external anchoring,\n"
                  "sender-constrained tokens, enforcement-domain separation — the seams most likely to be attacked.",
           vlstyle(C_NEUT), 700, 540, 660, 70)
    return p


# ================================================================ PAD pages

def build_pad_p1():
    p = P(1500, 1000)
    p.title("PAD-01 · Reference physical topology — dedicated gateway project/VPC (ApigeeX-style, names TBD)")
    cz = p.node(None, "Consumer VPC / tenant", zone("#f5f5f5", "#666666"), 40, 60, 250, 340)
    c1 = p.node("cv1", "Consumers\nmcp-gw.example.corp", vstyle(C_CONSUMER), 35, 50, 180, 60, cz)
    c2 = p.node("cv2", "Inbound private endpoint\nPSC / PrivateLink / Private Link", vstyle(C_CONSUMER), 35, 160, 180, 70, cz)
    p.node(None, "", ICON["az_dns"], 90, 260, 70, 70, cz)

    gz = p.node(None, "prj-taas-mcp-gateway-<env> — dedicated gateway project / VPC", zone("#eaf6ea", "#4d7a4d"), 350, 60, 520, 340)
    g1 = p.node("g1", "Inbound service\nattachment", vstyle(C_GOV, True), 30, 150, 170, 60, gz)
    g2 = p.node("g2", "Gateway runtime + MCP proxy\n+ token broker", vstyle(C_GOV, True), 150, 45, 220, 70, gz)
    g3 = p.node("g3", "Outbound private\nendpoint", vstyle(C_GOV, True), 320, 150, 170, 60, gz)
    p.node(None, "Internal DNS /\npeering zone", vstyle(C_STORE), 160, 250, 180, 55, gz)

    bz = p.node(None, "Backend project / VPC", zone("#fdf3e7", "#a66a3f"), 930, 60, 280, 340)
    b1 = p.node("b1", "Service attachment", vstyle(C_BACKEND), 45, 150, 180, 55, bz)
    p.node(None, "", ICON["az_lb"], 80, 55, 80, 80, bz)
    b3 = p.node("b3", "MCP services · model endpoints\nMistral·Vertex·Bedrock·local", vstyle(C_BACKEND), 45, 240, 190, 65, bz)

    op = p.node("op", "On-prem datacenter\nSD-WAN + firewall → WSO2/JDE", vstyle(C_RISK), 100, 470, 280, 70)
    eg = p.node("eg", "Controlled egress (Zscaler-class)\n→ SaaS MCP (Snowflake/Atlassian/…)", vstyle(C_RISK), 460, 470, 300, 70)
    p.node(None, "", ICON["az_fw"], 790, 470, 60, 60)

    p.edge(c1, c2); p.edge(c2, g1, "private connect")
    p.edge(g1, g2); p.edge(g2, g3); p.edge(g3, b1, "private connect")
    p.edge(b1, b3)
    p.edge(g2, op, "SD-WAN"); p.edge(g2, eg, "allowlisted egress")
    p.legend("Rules: private FQDNs only (never raw IP) · producer/consumer recorded per flow · backends LB/attachment-fronted · SaaS only via approved egress.", y=580)
    return p


def build_pad_p2():
    p = P()
    p.title("PAD-02 · Private/on-prem realization — Kubernetes Gateway API (AC-04: no cloud-specific CRDs)")
    gns = p.node(None, "namespace: gateway", zone("#eaf6ea", "#4d7a4d"), 60, 60, 470, 330)
    gc = p.node("gc", "GatewayClass\nEnvoy GW / NGINX / Kong\n(ADR-01 open)", vstyle(C_GOV), 30, 50, 200, 80, gns)
    gw = p.node("gw", "Gateway\nlisteners + TLS", vstyle(C_GOV), 30, 170, 200, 60, gns)
    hr = p.node("hr", "HTTPRoute\nhost/path → backend\n+ policy attachment", vstyle(C_GOV), 270, 160, 170, 85, gns)
    p.node(None, "pod", ICON["k8s_pod"], 60, 265, 55, 55, gns)

    mns = p.node(None, "namespace: mcp-proxy — reachable only via gateway", zone("#fdf3e7", "#a66a3f"), 590, 60, 320, 330)
    px = p.node("px", "MCP proxy\nService", vstyle(C_BACKEND), 60, 50, 200, 55, mns)
    bk = p.node("bk", "MCP backend\nService", vstyle(C_BACKEND), 60, 140, 200, 55, mns)
    p.node(None, "netpol: ingress gw-ns only", ICON["k8s_netpol"], 90, 230, 70, 70, mns)

    cns = p.node(None, "namespace: control-plane", zone("#f5f5f5", "#666666"), 60, 430, 460, 140)
    cp = p.node("cp", "TaaS Studio\nregistry + audit + inspection", vstyle(C_STORE), 30, 45, 200, 60, cns)
    p.node(None, "Vault / secrets", ICON["k8s_secret"], 300, 45, 55, 55, cns)

    p.edge(gc, gw, "implements"); p.edge(gw, hr); p.edge(hr, px, "routes")
    p.edge(px, bk)
    p.legend("Service identity (SPIFFE/workload ID) · consistent enablement across env-group clusters · limits+PDBs · GPU node pools for colocated runtimes (Phase D).", y=600)
    return p


def build_pad_p3():
    p = P()
    p.title("PAD-03 · Per-environment gateway baseline — one logical contract, provider-native realization")
    lc = p.node("lc", "Logical contract\n────────\nidentity · exposure\npolicy · audit\ncorrelation", vlstyle(C_STORE), 40, 90, 220, 130)
    a = p.node("a", "Private / on-prem\n────────\nKubernetes Gateway API\nGatewayClass+Gateway+HTTPRoute\nNetworkPolicy pods-only\nVault · Keycloak\nOllama / vLLM", vlstyle(C_GOV), 340, 50, 290, 160)
    b = p.node("b", "GCP\n────────\nApigeeX / Hybrid\nPSC in/out + attachments + ILB\nSecret Manager · Workload Identity\nVertex AI / Model Garden\n(version/feature check at impl.)", vlstyle(C_GOV), 680, 50, 290, 160)
    c = p.node("c", "AWS\n────────\nAPI GW / ALB / NLB\nPrivateLink endpoint services\nIAM / Identity Center\nSecrets Manager\nBedrock (private)", vlstyle(C_GOV), 340, 250, 290, 160)
    d = p.node("d", "Azure\n────────\nAPIM / App Gateway\nPrivate Link / private endpoints\nEntra ID (native broker)\nKey Vault · workload identity\nAzure AI / Foundry", vlstyle(C_GOV), 680, 250, 290, 160)
    for t in (a, b, c, d):
        p.edge(lc, t)
    p.legend("AC-05: identical logical contract across all four environments. Status: design — not implemented.", y=460)
    return p


def build_pad_p4():
    p = P()
    p.title("PAD-04 · Connectivity map NET-01..10 (PAD §5.1 table is authoritative)")
    s1 = p.node("s1", "Consumers", vstyle(C_CONSUMER), 80, 80, 190, 45)
    s2 = p.node("s2", "Gateway / proxy", vstyle(C_GOV, True), 80, 160, 190, 45)
    s3 = p.node("s3", "All components", vstyle(C_STORE), 80, 400, 190, 45)
    s4 = p.node("s4", "Orchestrator", vstyle(C_IDENT, True), 80, 480, 190, 45)
    flows = [
        ("d1", "NET-01 → inbound endpoint (TLS+private)", C_CONSUMER, 80),
        ("d2", "NET-02 → token broker/IdP (OIDC·JWKS)", C_IDENT, 140),
        ("d3", "NET-03 → private MCP (endpoint→LB→svc)", C_BACKEND, 200),
        ("d4", "NET-04 → REST→MCP adapter (private)", C_BACKEND, 260),
        ("d5", "NET-05 → model endpoints (private)", C_BACKEND, 320),
        ("d6", "NET-06 → on-prem API (SD-WAN+FW)", C_RISK, 380),
        ("d7", "NET-07 → SaaS MCP (controlled egress)", C_RISK, 440),
        ("d8", "NET-08 → private DNS (fwd/peering)", C_STORE, 500),
        ("d9", "NET-09 → registry+gw mgmt", C_STORE, 560),
        ("d10", "NET-10 → observability/SIEM", C_STORE, 620),
    ]
    for pid, lbl, col, y in flows:
        p.node(pid, lbl, vlstyle(col), 560, y, 380, 40)
    p.edge(s1, "d1"); p.edge(s2, "d2"); p.edge(s2, "d3"); p.edge(s2, "d4")
    p.edge(s2, "d5"); p.edge(s2, "d6"); p.edge(s2, "d7")
    p.edge(s3, "d8"); p.edge(s4, "d9"); p.edge(s3, "d10")
    return p


def build_pad_p5():
    p = P()
    p.title("PAD-05 · Private-connectivity record — required per PSC / PrivateLink / Private Link")
    pr = p.node("pr", "Producer side\n────────\nproject/VPC/region\nservice attachment ID\naccepted/rejected state\nconnection preference", vlstyle(C_BACKEND), 60, 70, 270, 150)
    cn = p.node("cn", "Consumer side\n────────\nproject/VPC/region\nendpoint ID + IP/subnet\nDNS record + zone owner", vlstyle(C_CONSUMER), 420, 70, 270, 150)
    fl = p.node("fl", "Flow attributes\n────────\nfirewall + routes both sides\nhealth-check + failover\nmaintenance owner\nrole: ingress-gw / gw-rt / gw-model", vlstyle(C_GOV), 780, 70, 320, 150)
    p.edge(pr, cn, "attachment ≠ endpoint")
    p.edge(cn, fl)
    p.node("rl", "Port & egress rules\n────────\n· private FQDNs only, never raw IPs\n· explicit FQDN/IP/port allowlists, no wildcards\n· TLS everywhere; verify each listener, never assume 443\n· MCP proxy reachable only via gateway path (NetworkPolicy)\n· prefer private connectivity for internal/model endpoints\n· public SaaS only via approved egress path", vlstyle(C_RISK), 60, 270, 520, 170)
    return p


def build_pad_p6():
    p = P()
    p.title("PAD-06 · DNS design + environment strategy")
    p.node("dn", "DNS design\n────────\n· private FQDNs for all backends\n· zone ownership + change process\n· split-horizon where required\n· peering/forwarding direction recorded\n· records: FQDN/type/target/TTL\n· SAN covers exact published FQDNs\n· env names never cross-resolve\n· example (TBD): mcp-gw.example.corp", vlstyle(C_STORE), 60, 60, 360, 220)
    p.node("e1", "DEV\nseparate env + non-prod endpoints\ntest creds · synthetic data", vlstyle(C_CONSUMER), 480, 60, 320, 90)
    p.node("e2", "TEST / INT\nseparate policies + test backends\nrepresentative data · SaaS sandboxes", vlstyle(C_CONSUMER), 850, 60, 320, 90)
    p.node("e3", "PREPROD\nprod-like connectivity/policy\nno uncontrolled prod data · release gate", vlstyle(C_IDENT), 480, 190, 320, 90)
    p.node("e4", "PROD\napproved cluster/network + private DNS\nprod IAM/secrets · audit retention · change windows", vlstyle(C_RISK), 850, 190, 320, 90)
    p.legend("Environment differences are configuration overlays — never divergent manually-maintained bundles.", y=330)
    return p


def build_pad_p7():
    p = P()
    p.title("PAD-07 · Trust boundaries + availability/DR checklist")
    p.node("tb", "Trust boundaries\n────────\nconsumer→gw: TLS+token+scope, WAF\ngw→proxy: pods-only NetworkPolicy\ngw→backends: private endpoints+allowlist\ngw→models: private conn + backend authN\ngw→on-prem: SD-WAN+FW+mTLS+audit\ngw→SaaS: egress allowlist+tenant limits\nbroker→IdP: trusted metadata+JWKS\norchestrator→planes: workload ID+least priv\nadmin→planes: MFA/SSO+PAM+change audit", vlstyle(C_IDENT), 60, 60, 420, 240)
    p.node("dr", "Availability / DR checklist\n────────\n· ≥2 runtime clusters where traffic diversion needed\n· health checks: gw, registry, runtimes, backends\n· registry outage → cached-policy serving only;\n  new publications FAIL CLOSED\n· backend fail → documented timeout/retry/breaker\n· never silently switch model providers\n· backups: registry + gw config + stateful parts\n· rollback: publication, policy, schema, upgrade\n· RTO/RPO/availability/retention = TBD per env", vlstyle(C_RISK), 540, 60, 460, 240)
    return p


def build_pad_p8():
    p = P()
    p.title("PAD-08 · Deployment pipeline + physical test plan PT-01..14")
    p1 = p.node("p1", "Source\nbundles·routes·schemas·overlays", vstyle(C_CONSUMER), 60, 60, 180, 70)
    p2 = p.node("p2", "CI/CD\nstatic checks·secret scan·policy tests·approvals", vstyle(C_IDENT), 290, 60, 220, 70)
    p3 = p.node("p3", "Deploy\nleast-priv identity · audited release", vstyle(C_GOV), 560, 60, 190, 70)
    p4 = p.node("p4", "Reconcile\ndrift detect + correct (scheduled)", vstyle(C_RISK, True), 800, 60, 200, 70)
    p.edge(p1, p2); p.edge(p2, p3); p.edge(p3, p4)
    p.node("t1", "PT-01..07 — connectivity & identity\n────────\n01 FQDN resolve per env\n02 endpoint/attachment state\n03 TLS chain + SAN\n04 unauthorized pod→proxy denied\n05 consumer→MCP direct denied+logged\n06 private path to MCP service\n07 model backend via approved route", vlstyle(C_STORE), 60, 190, 360, 220)
    p.node("t2", "PT-08..14 — behavior & hygiene\n────────\n08 on-prem API approved route\n09 SaaS egress: allowed pass / non-listed denied\n10 invalid/expired/wrong-aud token → 401\n11 consumer token replayed downstream → rejected\n12 registry outage → cached-policy only; publish fails closed\n13 orphan proxy/registry state detected after failed publish\n14 egress + log redaction review clean", vlstyle(C_STORE), 470, 190, 460, 220)
    return p


PAGES_LAD = [
    ("LAD-01-Context-Boundary", "l1", build_lad_p1),
    ("LAD-02-Consumer-Access", "l2", build_lad_p2),
    ("LAD-03-Provisioning", "l3", build_lad_p3),
    ("LAD-04-Inspect-vs-Invoke", "l4", build_lad_p4),
    ("LAD-05-Registry-Model", "l5", build_lad_p5),
    ("LAD-06-Identity-Threats", "l6", build_lad_p6),
    ("LAD-07-Decisions", "l7", build_lad_p7),
]

# ============================================================ STUDIO pages
# Studio-centric architecture: every box names a real module under
# src/taas/studio/ (solid = delivered) or an explicit MCP extension seam
# (dashed) defined in docs/studio/MCP_GATEWAY_EXTENSION.md.

def build_stu_p1():
    p = P(1500, 1000)
    p.title("STU-01 · TaaS Studio component map — real modules (src/taas/studio/) + MCP extension seams")

    cz = p.node(None, "Clients", zone("#f5f5f5", "#666666"), 30, 60, 180, 760)
    c1 = p.node("cl1", "Static UI\nstatic/index.html", vstyle(C_CONSUMER), 20, 50, 140, 55, cz)
    c2 = p.node("cl2", "Colab / notebooks\n(proxy tunnel)", vstyle(C_CONSUMER), 20, 140, 140, 55, cz)
    c3 = p.node("cl3", "SDK / scripts\npython client", vstyle(C_CONSUMER), 20, 230, 140, 55, cz)
    p.node(None, "Consumers, agents\n& M2M clients\n(gateway path)", vstyle(C_CONSUMER, True), 20, 400, 140, 75, cz)

    sz = p.node(None, "TaaS Studio process — FastAPI control plane (single process today)", zone("#eaf6ea", "#4d7a4d"), 250, 60, 760, 760)

    ap = p.node("ap", "api.py — /api/v1 surface\nrequire_api_token on every route\n(~89 routes · OpenAPI)", vstyle(C_GOV), 20, 40, 330, 70, sz)
    gw = p.node("gw", "Edge API Gateway\nTLS · WAF · quota · 2MiB", vstyle(C_GOV, True), 390, 40, 330, 70, sz)

    row1 = p.node(None, "Core services", zone("#fdf3e7", "#a66a3f", "startSize=22;"), 20, 140, 720, 200, sz)
    p.node("svc_tools", "tool_service.py\ntool_registry.py\ntool_intelligence.py", vstyle(C_BACKEND), 15, 30, 160, 80, row1)
    p.node("svc_disc", "discovery_runs.py\ndiscovery_diagnostics.py\nengine.py (core)", vstyle(C_BACKEND), 190, 30, 160, 80, row1)
    p.node("svc_agent", "agent_registry.py\nagent_spec.py\nagent_context.py\nagent_skill_bindings.py", vstyle(C_BACKEND), 365, 30, 160, 80, row1)
    p.node("svc_skill", "skill_registry.py\nskill_spec.py\nskill_dependency_graph.py", vstyle(C_BACKEND), 540, 30, 160, 80, row1)
    p.node("svc_obj", "objective_contract*.py\nobjective_traceability.py\ngoalspec_templates.py", vstyle(C_BACKEND), 15, 118, 160, 75, row1)
    p.node("svc_ws", "workspaces.py\nmodels.py (pydantic)\njson_diff.py", vstyle(C_BACKEND), 190, 118, 160, 75, row1)
    p.node("svc_rt", "model_runtime.py\nollama_runtime.py\nruntime.py", vstyle(C_BACKEND), 365, 118, 160, 75, row1)
    p.node("svc_rel", "release_readiness.py\nassurance_routes.py", vstyle(C_BACKEND), 540, 118, 160, 75, row1)

    row2 = p.node(None, "Governance services", zone("#f4f0f8", "#9673a6", "startSize=22;"), 20, 365, 720, 130, sz)
    p.node("svc_pol", "policy_engine.py\npolicy profiles (UX-17)", vstyle(C_STORE), 15, 30, 160, 70, row2)
    p.node("svc_authz", "authorization_preflight.py\ntrusted auth config", vstyle(C_STORE), 190, 30, 160, 70, row2)
    p.node("svc_exec", "execution_gateway.py\npolicy_fingerprint ·\nrequire_policy_allow ·\nApprovalStore", vstyle(C_STORE), 365, 30, 160, 70, row2)
    p.node("svc_audit", "audit_ledger.py\nhash chain · request_id", vstyle(C_STORE), 540, 30, 160, 70, row2)

    row3 = p.node(None, "MCP extension seams (E1–E7 · design)", zone("#fbfbe6", "#a6a040", "startSize=22;"), 20, 520, 720, 110, sz)
    px = p.node("seam_px", "mcp proxy service\nfiltered tools/list\ncall gated (Phase C)", vstyle(C_GOV, True), 15, 30, 160, 70, row3)
    tb = p.node("seam_tb", "token broker\nOAuth2.1·8693·6750\n(evolve api_keys.py)", vstyle(C_IDENT, True), 190, 30, 160, 70, row3)
    xr = p.node("seam_xr", "exposure resolver\nregistry exposure block\nroute_ref → env gw", vstyle(C_IDENT, True), 365, 30, 160, 70, row3)
    fg = p.node("seam_fg", "AuthZEN facade →\nABAC/ReBAC engine\nnormalized 403", vstyle(C_IDENT, True), 540, 30, 160, 70, row3)
    p.node("seam_mcp", "mcp_registry.py (delivered)\n+ exposure { mode, route_ref,\n private_endpoint, backends[] }", vstyle(C_STORE, True), 20, 650, 700, 70, sz)

    dz = p.node(None, "Persistence (file/JSON today)", zone("#f4f0f8", "#9673a6"), 1040, 60, 200, 760)
    p.node(None, "registries dir\nagents · skills · mcp", ICON["db"], 35, 55, 130, 80, dz)
    p.node(None, "audit log\nhash chain", ICON["db"], 35, 175, 130, 80, dz)
    p.node(None, "evidence bundles\nsigned", ICON["db"], 35, 295, 130, 80, dz)
    p.node(None, "workspaces\n+ revisions", ICON["db"], 35, 415, 130, 80, dz)
    p.node(None, "discovery runs\nsnapshots", ICON["db"], 35, 535, 130, 80, dz)

    bz = p.node(None, "Backends", zone("#fbeaea", "#a05a5a"), 1270, 60, 200, 760)
    b1 = p.node("b1", "MCP servers\n(private / LB-fronted)", vstyle(C_RISK), 20, 50, 160, 60, bz)
    b2 = p.node("b2", "REST→MCP adapter\nJDE / WSO2-class", vstyle(C_RISK, True), 20, 145, 160, 65, bz)
    b3 = p.node("b3", "SaaS MCP\n(controlled egress)", vstyle(C_RISK), 20, 245, 160, 60, bz)
    r1 = p.node("r1", "Model runtimes\nMistral·Vertex·Foundry\nOllama/vLLM", vstyle(C_BACKEND), 20, 340, 160, 75, bz)
    p.node("idp", "IdP · Entra ID\n/equivalent", vstyle(C_IDENT, True), 20, 460, 160, 60, bz)

    for c in (c1, c2, c3):
        p.edge(c, ap)
    p.edge(ap, "svc_tools"); p.edge(ap, "svc_authz"); p.edge(ap, "svc_audit")
    p.edge(ap, gw, "egress via edge", dashed=True)
    p.edge(gw, px, "", dashed=True)
    p.edge(tb, gw, "JWKS·exchange", dashed=True)
    p.edge("seam_mcp", xr, "E1 exposure", dashed=True)
    p.edge("svc_pol", fg, "E3 exposure_rules", dashed=True)
    p.edge("svc_exec", fg, "PEP (Phase C)", dashed=True)
    p.edge(px, b1, "", dashed=True); p.edge(px, b2, "", dashed=True); p.edge(px, b3, "", dashed=True)
    p.edge("svc_rt", r1); p.edge(tb, "idp", "", dashed=True)
    p.legend("solid = delivered module (src/taas/studio/) · dashed = design seam · the Studio stays inspection-only until Phase C.", y=860)
    return p


def build_stu_p2():
    p = P(1500, 1000)
    p.title("STU-02 · API surface by agent-tool lifecycle — real /api/v1 routes + MCP extension routes (dashed)")
    lanes = [
        ("DEFINE",  ["POST /goals/validate", "GET /goalspec/templates",
                     "POST /agents/validate (manifest v1alpha1)", "POST /workspaces"],
                    ["+ v1alpha2 spec.exposure / spec.identity (E2)"]),
        ("BUILD",   ["POST /skills · /skills/validate", "GET /skills/{id}/versions",
                     "POST /agents/decompose · /objectives/prepare",
                     "POST /objectives/discover"],
                    ["+ POST /mcp/servers/{id}/exposure-draft (E1)"]),
        ("DISCOVER",["POST /discover", "GET /tools · /tools/retrieve",
                     "POST /tools/eligibility · /tools/compare",
                     "GET /mcp/servers · POST /mcp/servers/{id}/inspect",
                     "GET /mcp/registry/snapshots(+diff)"],
                    ["+ GET /mcp/exposure-map (visible tools per profile)"]),
        ("VERIFY",  ["GET /agents/{id}/versions/{v}/policy-verdict",
                     "GET /agents/{id}/versions/{v}/release-readiness",
                     "POST /agents/{id}/versions/{v}/sign",
                     "GET /audit/events · /audit/verify · /assurance/evidence/*"],
                    ["+ POST /mcp/exposure/verify (smoke test, E4)"]),
        ("OPERATE", ["GET /discovery/runs(+diff)", "GET /notifications",
                     "GET /platform/overview", "GET /runtime/status"],
                    ["+ GET /mcp/routes/{route_ref}/health (E7)",
                     "+ POST /mcp/exposure/publish → READY (E4)"]),
        ("EVALUATE & MANAGE", ["GET /bench/datasets · /bench/tasks",
                     "GET /skills/events · versions/{a}/diff/{b}",
                     "GET /hypergraph/projections"],
                    ["+ GET /audit?kind=exposure.*|gateway.decision|token.exchange (E5)"]),
    ]
    y = 60
    for name, solid, dashed in lanes:
        lz = p.node(None, name, zone("#f5f5f5", "#666666", "horizontal=0;"), 40, y, 1400, 120)
        x = 30
        for r in solid:
            p.node(None, r, vstyle(C_GOV), x, 32, 215, 60, lz)
            x += 228
        for r in dashed:
            p.node(None, r, vstyle(C_IDENT, True), x, 32, 250, 60, lz)
            x += 263
        y += 130
    p.legend("Every delivered route sits behind require_api_token (api_keys.py / TAAS_STUDIO_API_TOKEN). "
             "Dashed routes are design seams — none expose tools/call; the Studio API stays inspection-only.", y=y+10)
    return p


def build_stu_p3():
    p = P(1500, 950)
    p.title("STU-03 · MCP extension points — where E1–E7 land on existing Studio modules")
    rows = [
        ("E1 exposure block",  "mcp_registry.py",       "server record gains exposure { mode, route_ref,\nprivate_endpoint, dns_name, adapter, backends[] }"),
        ("E2 manifest v1alpha2","agent_spec.py + /agents/validate","spec.exposure { publish_via, consumer_scopes }\nspec.identity { workload_identity_ref }"),
        ("E3 exposure_rules",  "policy_engine.py",      "profile gains { consumer_scopes, tools_visible,\ntools_callable*, egress_class, quota } — AuthZEN-portable"),
        ("E4 READY gate",      "agent_registry.py\nlifecycle state machine","draft→published kept; READY requires\nexposure smoke-test pass"),
        ("E5 audit kinds",     "audit_ledger.py",       "+ exposure.* · gateway.decision · token.exchange\nsame hash chain, same payload.request_id"),
        ("E6 token broker",    "api_keys.py /\nrequire_api_token","TAAS_STUDIO_API_TOKEN + ak_* evolve to\nOAuth2.1 · RFC 8693 · opaque bearer at edge"),
        ("E7 route_ref",       "mcp_registry.py (exposure)","one schema; per-env realization:\nK8s GW API / ApigeeX / PrivateLink / Private Link"),
    ]
    p.node(None, "Extension", zone("#fbfbe6", "#a6a040"), 40, 60, 260, 30)
    p.node(None, "Existing module (anchored)", zone("#f4f0f8", "#9673a6"), 320, 60, 300, 30)
    p.node(None, "What is added", zone("#eaf6ea", "#4d7a4d"), 640, 60, 700, 30)
    y = 95
    for ext, mod, desc in rows:
        e = p.node(None, ext, vstyle(C_IDENT, True), 40, y, 260, 70)
        m = p.node(None, mod, vstyle(C_STORE), 320, y, 300, 70)
        p.node(None, desc, vlstyle(C_GOV), 640, y, 700, 70)
        p.edge(e, m)
        y += 82
    p.node(None, "Rule (per user directive): the gateway/proxy/token-broker is an extension of existing "
                 "registry, manifest, policy, lifecycle and audit entities — no parallel subsystem is invented.",
           vlstyle(C_RISK), 40, y + 15, 1300, 60)
    return p


def build_stu_p4():
    p = P(1500, 950)
    p.title("STU-04 · Request flow — inspection path today (solid) vs extended MCP path (dashed)")
    c = p.node("c", "Caller\nUI · notebook · SDK", vstyle(C_CONSUMER), 40, 120, 160, 65)
    tk = p.node("tk", "require_api_token\nTAAS_STUDIO_API_TOKEN\n/ ak_* key", vstyle(C_IDENT), 280, 120, 200, 65)
    ap = p.node("ap", "api.py route", vstyle(C_GOV), 560, 120, 170, 65)
    sv = p.node("sv", "service module\n(tool/agent/mcp_registry…)", vstyle(C_BACKEND), 820, 120, 210, 65)
    st = p.node("st", "registry / store\n+ audit_ledger event", vstyle(C_STORE), 1120, 120, 210, 65)
    p.edge(c, tk, "1"); p.edge(tk, ap, "2 authed"); p.edge(ap, sv, "3"); p.edge(sv, st, "4 read+audit")

    gw = p.node("gw", "Edge gateway\nTLS·WAF·quota", vstyle(C_GOV, True), 40, 320, 180, 60)
    br = p.node("br", "Token broker\nvalidate → exchange/downscope\nopaque out (E6)", vstyle(C_IDENT, True), 300, 320, 220, 75)
    xr = p.node("xr", "Exposure resolver\nserver.exposure + policy\nprofile (E1·E3)", vstyle(C_IDENT, True), 600, 320, 220, 75)
    px = p.node("px", "MCP proxy\nfiltered tools/list", vstyle(C_GOV, True), 900, 320, 190, 60)
    fg = p.node("fg", "AuthZEN → ReBAC/ABAC\n403 / step-up 6750", vstyle(C_IDENT, True), 1150, 320, 200, 75)
    bk = p.node("bk", "MCP backend\nLB / private endpoint", vstyle(C_RISK), 900, 480, 190, 60)
    p.edge(c, gw, "", dashed=True); p.edge(gw, br, "JWKS", dashed=True)
    p.edge(br, xr, "scoped claims", dashed=True); p.edge(xr, px, "allowed route", dashed=True)
    p.edge(px, fg, "sensitive call", dashed=True); p.edge(px, bk, "governed", dashed=True)
    p.edge(st, xr, "feeds profile", dashed=True)

    l1 = p.node(None, "Denied today (by design)", zone("#fbeaea", "#a05a5a", "horizontal=0;"), 40, 600, 1400, 110)
    p.node(None, "no /tools/call route in api.py", vstyle(C_RISK), 40, 35, 300, 60, l1)
    p.node(None, "no bearer passthrough (D5)", vstyle(C_RISK), 380, 35, 300, 60, l1)
    p.node(None, "inspection-only results\nexecution_performed=false", vstyle(C_RISK), 720, 35, 320, 60, l1)
    p.node(None, "Phase C: PEP in execution_gateway.py\n+ isolated worker + fresh evidence", vstyle(C_RISK, True), 1080, 30, 290, 75, l1)
    p.legend("Every hop writes an audit_ledger event carrying the same request_id — deny paths: 401 (token), 403+step-up (scope), deny+log (backend not allowlisted).", y=750)
    return p


def build_stu_p5():
    p = P(1500, 950)
    p.title("STU-05 · Assurance & evidence pipeline — signed evidence, hash-chained audit, MCP inspection")
    i1 = p.node("i1", "authorization_preflight.py\ntrusted auth config\nfail closed", vstyle(C_IDENT), 40, 80, 230, 80)
    i2 = p.node("i2", "assurance_evidence.py\nTAAS_EVIDENCE_ATTESTATION_KEY\nsigned bundles · freshness", vstyle(C_STORE), 340, 80, 260, 80)
    i3 = p.node("i3", "audit_ledger.py\nhash chain · /audit/verify\npayload.request_id", vstyle(C_STORE), 680, 80, 250, 80)
    i4 = p.node("i4", "release_readiness.py\napprovals · gates", vstyle(C_STORE), 1010, 80, 230, 80)
    p.edge(i1, i2); p.edge(i2, i3); p.edge(i3, i4)

    mz = p.node(None, "MCP inspection (delivered — mcp_registry.py)", zone("#eaf6ea", "#4d7a4d", "horizontal=0;"), 40, 230, 1400, 130)
    m1 = p.node("m1", "POST /mcp/registry/\nsnapshots/inspect", vstyle(C_GOV), 40, 35, 250, 70, mz)
    m2 = p.node("m2", "snapshot persisted\n(tools/list result)", vstyle(C_GOV), 340, 35, 250, 70, mz)
    m3 = p.node("m3", "GET snapshots/{a}/diff/{b}\ndrift evidence", vstyle(C_GOV), 640, 35, 250, 70, mz)
    m4 = p.node("m4", "audit event\n(inspection only)", vstyle(C_GOV), 940, 35, 250, 70, mz)
    p.edge(m1, m2); p.edge(m2, m3); p.edge(m3, m4)

    xz = p.node(None, "Extension (E5) — gateway-era audit kinds, same ledger", zone("#fbfbe6", "#a6a040", "horizontal=0;"), 40, 400, 1400, 130)
    x1 = p.node("x1", "exposure.published\n/ exposure.revoked", vstyle(C_IDENT, True), 40, 35, 280, 70, xz)
    x2 = p.node("x2", "gateway.decision\nallow/deny + reason", vstyle(C_IDENT, True), 380, 35, 280, 70, xz)
    x3 = p.node("x3", "token.exchange\nsubject→act-as chain\n(no token material logged)", vstyle(C_IDENT, True), 720, 35, 300, 70, xz)
    p.edge(x1, i3, "", dashed=True); p.edge(x2, i3, "", dashed=True); p.edge(x3, i3, "", dashed=True)

    p.node(None, "Invariant enforced by evidence: a snapshot or certificate proves what was observed — "
                 "never that a call is authorized or executed.", vlstyle(C_RISK), 40, 560, 1300, 60)
    return p


def build_stu_p6():
    p = P(1500, 1000)
    p.title("STU-06 · Deployment — Studio process today (solid) vs governed MCP topology (dashed seams)")

    tz = p.node(None, "Today — single process", zone("#eaf6ea", "#4d7a4d"), 40, 60, 380, 860)
    t1 = p.node("t1", "Studio FastAPI\n(src/taas/studio)\nall modules in-proc", vstyle(C_GOV), 60, 60, 260, 80, tz)
    t2 = p.node("t2", "static UI served\nby same process", vstyle(C_GOV), 60, 180, 260, 60, tz)
    t3 = p.node("t3", "file stores\nregistries·audit·evidence", vstyle(C_STORE), 60, 280, 260, 70, tz)
    t4 = p.node("t4", "Colab tunnel\n(reviewer path)", vstyle(C_CONSUMER), 60, 390, 260, 60, tz)
    p.edge(t4, t1); p.edge(t2, t1); p.edge(t1, t3)

    gz = p.node(None, "Target — governed topology (Phase B; dashed = not implemented)", zone("#fbfbe6", "#a6a040"), 460, 60, 980, 860)
    g1 = p.node("g1", "Edge API Gateway\n(per env: K8s GW API /\nApigeeX / API GW / APIM)", vstyle(C_GOV, True), 40, 60, 230, 90, gz)
    p.node(None, "", ICON["aws_gw"], 110, 170, 60, 60, gz)
    g2 = p.node("g2", "Studio control plane\n(unchanged modules\n+ exposure fields)", vstyle(C_STORE, True), 330, 60, 240, 90, gz)
    g3 = p.node("g3", "MCP proxy svc\nseparate deployment\n(filtered tools/list)", vstyle(C_GOV, True), 630, 60, 240, 90, gz)
    g4 = p.node("g4", "Token broker svc\nIdP-agnostic (E6)", vstyle(C_IDENT, True), 330, 220, 240, 75, gz)
    g5 = p.node("g5", "Policy/PEP svc\nAuthZEN → ReBAC (D9)", vstyle(C_IDENT, True), 630, 220, 240, 75, gz)

    kz = p.node(None, "Private cloud — K8s Gateway API", zone("#eaf3fb", "#3a6ea5", "startSize=22;"), 40, 350, 440, 300, gz)
    p.node(None, "GatewayClass", ICON["k8s_svc"], 30, 40, 120, 70, kz)
    p.node(None, "Gateway", ICON["k8s_svc"], 160, 40, 110, 70, kz)
    p.node(None, "HTTPRoute", ICON["k8s_svc"], 280, 40, 120, 70, kz)
    p.node(None, "mcp-proxy\npods", ICON["k8s_pod"], 60, 170, 120, 80, kz)
    p.node(None, "studio\npods", ICON["k8s_pod"], 250, 170, 120, 80, kz)
    p.node(None, "NetworkPolicy\npods-only ingress", ICON["k8s_netpol"], 155, 175, 85, 80, kz)

    p.node(None, "Namespaces: cp-studio · mcp-proxy · pep (separated)",
           vlstyle(C_NEUT), 40, 680, 440, 50, gz)
    p.node(None, "Backends via private endpoints only\nservice attachments / LB · private FQDN",
           vlstyle(C_RISK), 520, 350, 400, 80, gz)
    p.node(None, "IdP (Entra ID / equivalent)\nJWKS at edge", vstyle(C_IDENT, True), 520, 470, 200, 75, gz)
    p.node(None, "", ICON["az_entra"], 750, 470, 60, 60, gz)
    p.node(None, "", ICON["az_kv"], 840, 470, 60, 60, gz)

    p.edge(g1, g2, "", dashed=True); p.edge(g1, g3, "", dashed=True)
    p.edge(g4, g1, "", dashed=True); p.edge(g3, g5, "", dashed=True)
    p.edge(t1, g2, "same codebase,\nsplit deploy", dashed=True)
    p.legend("The Studio codebase does not fork: control-plane modules stay identical; the MCP proxy/broker are separate "
             "deployments configured through the same registry — schema identical across private/GCP/AWS/Azure.", y=940)
    return p


PAGES_PAD = [
    ("PAD-01-Physical-Overview", "pd1", build_pad_p1),
    ("PAD-02-K8s-GatewayAPI", "pd2", build_pad_p2),
    ("PAD-03-Env-Matrix", "pd3", build_pad_p3),
    ("PAD-04-Connectivity-Map", "pd4", build_pad_p4),
    ("PAD-05-Private-Conn-Checklist", "pd5", build_pad_p5),
    ("PAD-06-DNS-Environments", "pd6", build_pad_p6),
    ("PAD-07-Trust-DR", "pd7", build_pad_p7),
    ("PAD-08-Deploy-TestPlan", "pd8", build_pad_p8),
]


def build_stu_p7():
    p = P(1500, 1000)
    p.title("STU-07 · Threat & assurance gap map — findings from principal-architect review → required seams")
    rows = [
        ("Audit self-attestation", "audit_ledger.py hash-chains into a file the Studio\ncontrols — producer is sole anchor",
         "External anchor: signed digests → WORM/witness log;\nSIEM streaming export (LAD D12, NFR-AUD-3)"),
        ("Enforcement inside gated domain", "PEP/policy/ledger share the Studio's admin &\nfailure domain — gate can disable its own gate",
         "Separate identity/admin domains mandatory in\nany gating phase (LAD D14, NFR-SEC-5)"),
        ("Bearer replay", "OAuth bearer tokens are replayable; tool path is\nthe highest-value credential",
         "Sender-constrained tokens DPoP/mTLS (LAD D13);\nak_* stays control-plane only (E6)"),
        ("Registry tampering", "exposure.route_ref/backends are plain JSON —\nconfig plane is the confused-deputy surface",
         "Signed exposure + four-eyes publish + backend\nidentity pinning, fail-closed (E8)"),
        ("MCP session blind spot", "Bidirectional JSON-RPC: notifications/elicitation/\nsampling = covert channel; REST model unfit",
         "Session↔identity binding, notification allow-list,\nelicitation interception (LAD D11, FR-INT-9)"),
        ("Approval TOCTOU", "Approving call X must not authorize call Y",
         "Approval = hash(policy_fp, tool, canonical_args,\nevidence) — reuse with different args fails"),
        ("Description injection", "Tool descriptions are untrusted input delivered\nthrough a trusted channel",
         "Registry-side linting/sanitization at inspection\n(FR-SEC-7)"),
        ("Observation ≠ origin", "Snapshots prove what was observed, not what\nserved it — swapped backend still valid",
         "Artifact provenance: image digest + SBOM +\nSLSA attestation (E9)"),
        ("Divergent enforcement", "route_ref schema-identical but K8s GW API has\nno WAF; PrivateLink unidirectional",
         "Per-env capability matrix + conformance tests —\ncontract promises the floor (PAD §7.6)"),
        ("Broker SPOF", "Token broker sits in the data path; JWKS/IdP\noutage behavior undesigned",
         "HA replicas, JWKS cache TTL+rotation, IdP outage\nfail-closed new-publish / cached serving (PAD §7.7)"),
    ]
    p.node(None, "Finding", zone("#fbeaea", "#a05a5a"), 40, 60, 230, 30)
    p.node(None, "Why it matters (module-level)", zone("#f5f5f5", "#666666"), 285, 60, 560, 30)
    p.node(None, "Required seam (decision/requirement)", zone("#eaf6ea", "#4d7a4d"), 860, 60, 580, 30)
    y = 100
    for name, why, fix in rows:
        p.node(None, name, vstyle(C_RISK), 40, y, 230, 64)
        p.node(None, why, vlstyle(C_NEUT), 285, y, 560, 64)
        p.node(None, fix, vlstyle(C_GOV, True), 860, y, 580, 64)
        y += 76
    p.legend("None of these change the delivered Studio surface — they are Phase B/C seams recorded so the "
             "architecture cannot quietly assume guarantees it does not yet enforce.", y=y+15)
    return p


PAGES_STU = [
    ("STU-01-Component-Map", "st1", build_stu_p1),
    ("STU-02-API-Lifecycle", "st2", build_stu_p2),
    ("STU-03-Extension-Points", "st3", build_stu_p3),
    ("STU-04-Request-Flow", "st4", build_stu_p4),
    ("STU-05-Assurance-Audit", "st5", build_stu_p5),
    ("STU-06-Deployment", "st6", build_stu_p6),
    ("STU-07-Threat-Gap-Map", "st7", build_stu_p7),
]


def main():
    for fname, spec in (("taas-lad.drawio", PAGES_LAD),
                        ("taas-pad.drawio", PAGES_PAD),
                        ("taas-studio-architecture.drawio", PAGES_STU)):
        pages = [(name, pid, fn().render()) for name, pid, fn in spec]
        (OUT / fname).write_text(mxfile(pages), encoding="utf-8")
        print(f"wrote {OUT / fname} ({len(pages)} pages)")


if __name__ == "__main__":
    main()
