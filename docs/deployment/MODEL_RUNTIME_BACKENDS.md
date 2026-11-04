# TaaS Studio — Model Runtime Backends

TaaS Studio supports two inference providers with one Studio workflow:

- **Hugging Face Transformers**: weights run inside the TaaS API process, on CPU or CUDA.
- **Ollama**: inference is delegated to an operator-managed Ollama daemon over its HTTP API.

The provider is explicit per request. The selected model is not a tool, and model inference does not invoke MCP tools, grant authorization, or enable governed execution.

## Hugging Face on CPU

Install the optional dependencies:

```bash
pip install -e ".[studio,hf]"
```

Choose **Hugging Face · Transformers**, enter a repository ID such as `Qwen/Qwen2.5-0.5B-Instruct`, and select **CPU** or **Automatic**. Automatic selects CUDA only when PyTorch reports CUDA available; otherwise it selects CPU. Explicit CUDA fails closed if CUDA is unavailable.

CPU inference is supported but memory- and latency-sensitive. Begin with small models and short contexts. Weight memory is only part of the total: tokenizer, activations, generation cache, Python, and the Studio process also consume RAM. A 0.5B FP32 model has roughly 2 GB of raw parameter storage before overhead; this is an estimate, not a capacity guarantee.

## Hugging Face tokenizer compatibility

The loader first attempts the fast tokenizer and then falls back to the slow tokenizer. The `hf` extra includes `sentencepiece` and `tiktoken` to cover common tokenizer implementations. Remote model code remains disabled (`trust_remote_code=False`). If both modes fail, the API returns both failure causes and the installation hint instead of silently changing model trust settings.

After changing dependencies, restart the Python process and retry the model load.

## Ollama

Install and start Ollama separately from TaaS. Pull a model before selecting it in Studio:

```bash
ollama serve
ollama pull qwen2.5:0.5b
```

The TaaS process uses the Ollama HTTP API; it does not shell out to the Ollama CLI. The default endpoint is:

```text
http://127.0.0.1:11434
```

For a different endpoint, set `TAAS_OLLAMA_BASE_URL` in the environment **before starting Uvicorn**. Do not embed credentials in the URL. Protect remote Ollama endpoints with network controls and an authenticated TLS reverse proxy; the Ollama API itself must not be exposed publicly without protection.

In Studio select **Ollama · local or configured API**, enter the installed model tag (for example `qwen2.5:0.5b`), and click **Download & load model**. This action validates the model with `/api/show`; Ollama loads weights lazily on the first inference. The device and quantization are managed by Ollama, not by the TaaS device selector.

The authenticated TaaS API exposes only the configured Ollama status and the model list returned by `/api/tags`. The adapter uses `/api/chat` with streaming disabled. It does not expose arbitrary URL selection in the browser, execute shell commands, or forward MCP tool calls.

## Optional Colab Ollama setup

Colab can run Ollama in the same runtime as TaaS, subject to available RAM, disk, and network access. Run this optional setup **before** the Studio launch cell. It installs Ollama, starts its daemon, and pulls a small model:

```python
import os, shutil, subprocess, time, urllib.request

if not shutil.which("ollama"):
    subprocess.run(["bash", "-lc", "curl -fsSL https://ollama.com/install.sh | sh"], check=True)

ollama_env = os.environ.copy()
ollama_env["OLLAMA_HOST"] = "127.0.0.1:11434"
ollama_process = subprocess.Popen(
    ["ollama", "serve"], env=ollama_env,
    stdout=open("/content/ollama.log", "a"), stderr=subprocess.STDOUT
)
for attempt in range(45):
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2).read()
        break
    except Exception:
        time.sleep(2)
else:
    raise RuntimeError("Ollama daemon did not become ready; inspect /content/ollama.log")

subprocess.run(["ollama", "pull", "qwen2.5:0.5b"], check=True)
os.environ["TAAS_OLLAMA_BASE_URL"] = "http://127.0.0.1:11434"
print("Ollama is ready for TaaS Studio.")
```

This setup is optional and is not run automatically by the default notebook. If Colab disconnects or reclaims the runtime, the daemon and downloaded model may be lost. Keep the Ollama process alive while using Studio.

## Runtime status and semantics

- Hugging Face status reports whether weights are loaded into the TaaS Python process.
- Ollama status reports daemon reachability, installed model tags, and the selected model. A successful selection check is **not** a claim that weights are already resident; Ollama loads on first inference.
- The Studio provider selector is shared by model loading, chat, and GoalSpec decomposition.
- CPU is a supported execution target; CUDA is an optional acceleration path.
- Inference outputs include the provider so that logs and tests can distinguish backends.
- This adapter is process-local and intended for the current single-process Studio. Production deployments still need isolated workers, resource scheduling, tenant isolation, and secret/network management.

## Troubleshooting

| Symptom | Action |
|---|---|
| CUDA requested but unavailable | Choose CPU or Automatic; do not force CUDA on a CPU runtime |
| Fast tokenizer backend error | Restart after installing `.[hf]`; loader retries slow mode |
| Both tokenizer modes fail | Check the returned fast/slow causes and model tokenizer artifacts |
| Ollama unavailable | Start `ollama serve`, verify `/api/tags`, and check `TAAS_OLLAMA_BASE_URL` |
| Model tag not found | Run `ollama pull <model-tag>` before selecting it |
| Ollama selection succeeds but first inference is slow | Expected lazy model load; check available RAM/VRAM and Ollama logs |
| CPU inference is too slow or runs out of memory | Use a smaller model, lower generation/context limits, or use Ollama quantized models |
