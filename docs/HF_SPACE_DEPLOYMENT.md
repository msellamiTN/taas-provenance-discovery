# Publish TAAS Studio E8 to Hugging Face

This deployment targets the existing Space:
https://huggingface.co/spaces/MSellami/TAAS_Studio

## One-time Hugging Face trust setup (no permanent token)

Open the Space **Settings → Trusted Publishers** and add:

- Provider: **GitHub Actions**
- Repository: `msellamiTN/taas-provenance-discovery`
- Branch: `hf-space-deploy`
- Workflow: `publish-taas-studio-hf.yml`
- Read-only: **off** (write access is required)

This creates a narrowly scoped OIDC publisher. Each GitHub Actions run receives a short-lived token for this Space; no S3 key or permanent Hugging Face token is stored in GitHub.

After saving this publisher, tell the deployment operator that the trust entry is ready. The first deployment is activated by adding `.github/taas-hf-deploy-enabled` to the `hf-space-deploy` branch. The workflow then uploads the validated bundle to the root of the Space. Later updates to the ZIP automatically trigger another upload.

## What the workflow does

1. Installs the current Hugging Face CLI with OIDC support.
2. Validates the archive and required root files.
3. Extracts the Space bundle into a clean temporary directory.
4. Uses the OIDC token exchange to publish to `MSellami/TAAS_Studio`.

## Space runtime setup

After the upload, verify that the Space hardware is set to **ZeroGPU**. Free personal accounts in good standing can host up to two ZeroGPU Spaces. Gradio on CPU Basic requires a paid plan.

The app's full E8 Job controls require separate Space configuration:

**Secrets**
- `HF_TOKEN`: write token for submitting HF Jobs and uploading artifacts.
- `HF_E8_LAUNCH_KEY`: a separate strong workbench access key.

**Variables**
- `HF_E8_ARTIFACT_REPO`: private Dataset repository for E8 outputs, e.g. `MSellami/pamcp-e8-results`.
- `HF_E8_BUCKET_ID` (optional): writable Storage Bucket for checkpoints, e.g. `MSellami/pamcp-e8-checkpoints`.

The OIDC publishing token is separate from the app runtime `HF_TOKEN`. The Space's ZeroGPU function is only a short readiness diagnostic; the complete E8 campaign runs as an HF Job and requires available paid compute/credits.

## Safety

Never commit S3 credentials, Hugging Face tokens, workbench launch keys, or experiment outputs to this repository.
