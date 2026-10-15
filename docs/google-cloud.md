# Google Cloud and GitHub authentication

Project: `baseviewer-511722`. This guide prepares authentication; it does not assert that the project has already been registered or configured.

1. Open the [Earth Engine registration page](https://console.cloud.google.com/earth-engine) for this project. Enable the Earth Engine API and choose commercial access or the appropriate verified noncommercial registration for your actual use. Check your applicable terms and compute allowance.
2. Create a dedicated service account. Grant **Earth Engine Resource Viewer** (`roles/earthengine.viewer`) and **Service Usage Consumer** (`roles/serviceusage.serviceUsageConsumer`) on the project. The [Earth Engine service-account guide](https://developers.google.com/earth-engine/guides/service_account) documents the project registration, API and role requirements.
3. Configure GitHub OIDC/Workload Identity Federation to impersonate that service account. No downloadable service-account key is required.

## Local authentication

Install the [Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/install), then run:

```text
gcloud auth application-default login
gcloud auth application-default set-quota-project baseviewer-511722
sentinel-monitor run --output site-live --end-date 2026-10-12
```

The application uses ADC with the cloud-platform scope and an explicit project. Your user account also needs Earth Engine access and service-usage permissions. An interactive login must be completed by the account holder. Never put credential JSON files, access tokens, private keys or `.env` secrets in Git. The `.gitignore` includes common credential file patterns as a precaution.

## Workload Identity Federation

Use [Google's deployment-pipeline guide](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines) for full setup and [google-github-actions/auth](https://github.com/google-github-actions/auth) for the action configuration.

These Bash commands can be adapted in Cloud Shell by an administrator. They enable APIs, create an account and establish a provider limited to this repository's main branch. Existing resources should be reused instead of recreated.

```bash
PROJECT_ID=baseviewer-511722
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SERVICE_ACCOUNT="sentinel-monitor@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud services enable earthengine.googleapis.com iam.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com cloudresourcemanager.googleapis.com \
  --project="$PROJECT_ID"

gcloud iam service-accounts create sentinel-monitor --project="$PROJECT_ID" \
  --display-name='Sentinel ground-change monitor'

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" --role=roles/earthengine.viewer

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" --role=roles/serviceusage.serviceUsageConsumer

gcloud iam workload-identity-pools create github --project="$PROJECT_ID" \
  --location=global --display-name='GitHub Actions'

gcloud iam workload-identity-pools providers create-oidc baseviewer \
  --project="$PROJECT_ID" --location=global --workload-identity-pool=github \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping='google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id' \
  --attribute-condition="assertion.repository_id=='1421373524' && assertion.repository_owner_id=='123981133' && assertion.ref=='refs/heads/main'"

gcloud iam service-accounts add-iam-policy-binding "$SERVICE_ACCOUNT" \
  --project="$PROJECT_ID" --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/attribute.repository_id/1421373524"

printf 'WIF_PROVIDER=projects/%s/locations/global/workloadIdentityPools/github/providers/baseviewer\n' "$PROJECT_NUMBER"
printf 'EE_SERVICE_ACCOUNT=%s\n' "$SERVICE_ACCOUNT"
```

The stable repository ID `1421373524` belongs to `Savvyboi/baseviewer`; owner ID `123981133` belongs to `Savvyboi`, verified from the connected GitHub repository metadata. Numeric claims avoid relying only on reusable repository names. The provider condition restricts token exchange to this repository, owner and `refs/heads/main`.

Set the printed provider and service-account values as repository Actions variables, along with `EE_PROJECT_ID=baseviewer-511722`. Leave `MONITOR_ENABLED` unset until the first manual live run and Pages publication have been checked. The workflow provides `id-token: write` and `google-github-actions/auth` creates a temporary ADC file for the run.

If an organization restricts identity pools, service accounts, API enablement or Pages deployments, an administrator will need to apply the corresponding setup. Authentication failures must be resolved before running a real imagery or compute benchmark.
