import json, sys, urllib.request
import websocket

def targets():
    return json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list"))

def page_ws(substr):
    for t in targets():
        if t["type"] == "page" and substr in t.get("url", ""):
            return t["webSocketDebuggerUrl"], t["url"]
    raise SystemExit(f"no page matching {substr!r}")

def ev(expr, url_sub="colab.research.google.com", timeout=30, ret_json=True):
    ws_url, page_url = page_ws(url_sub)
    ws = websocket.create_connection(ws_url, timeout=timeout)
    mid = 1
    ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid:
            ws.close()
            r = msg.get("result", {}).get("result", {})
            if "value" in r:
                return r["value"]
            return msg
    ws.close()

if __name__ == "__main__":
    expr = sys.argv[1]
    sub = sys.argv[2] if len(sys.argv) > 2 else "colab.research.google.com"
    out = ev(expr, sub)
    print(json.dumps(out, indent=2, default=str)[:8000])
