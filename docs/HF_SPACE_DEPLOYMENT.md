# Publish TAAS Studio E8 to Hugging Face

This deployment is configured to publish to the existing Space:
https://huggingface.co/spaces/MSellami/TAAS_Studio

## One-time Hugging Face setup (no long-lived token)

Open the Space **Settings → Trusted Publishers** and add a publisher with:

- Provider: **GitHub Actions**
- Repository: `msellamiTN/taas-provenance-discovery`
- Branch: `hf-space-deploy`
- Workflow: `publish-taas-studio-hf.yml`
- Read-only: **off** (the publisher needs write access)

This grants a short-lived, repository-scoped upload token to that exact GitHub workflow. No S3 key or permanent HF token is stored in GitHub.

## Run the deployment

1. Open the GitHub Actions tab for this repository.
2. Select **Publish TAAS Studio E8 to Hugging Face**.
3. Choose **Run workflow** on branch `hf-space-deploy`.

The workflow validates the archive, extracts the Space root files, and uploads them to the root of `MSellami/TAAS_Studio` using the Hugging Face CLI's OIDC token exchange.

## Space runtime setup

After the first upload, select **ZeroGPU** in the Space hardware settings. Free personal accounts in good standing can host up to two ZeroGPU Spaces; Gradio on CPU Basic requires a paid plan.

The Space app also expects these settings before the full E8 Job controls can be used:

**Secrets**
- `HF_TOKEN`: Hugging Face write token for submitting Jobs and uploading artifacts.
- `HF_E8_LAUNCH_KEY`: separate private workbench launch key.

**Variables**
- `HF_E8_ARTIFACT_REPO`: private Dataset repository for E8 output, e.g. `MSellami/pamcp-e8-results`.
- `HF_E8_BUCKET_ID` (optional): Storage Bucket for resumable checkpoints, e.g. `MSellami/pamcp-e8-checkpoints`.

The OIDC publishing token is separate from the Space runtime `HF_TOKEN`. Jobs and stored artifacts may incur charges; ZeroGPU quota only covers the short diagnostic.

## Safety

Never commit S3 credentials, Hugging Face tokens, launch keys, or experiment outputs to this repository.
