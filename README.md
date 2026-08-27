# ojof-gym

LookML patterns, benchmark tasks, and evaluation harnesses for Outer Join On False (OJOF) multi-fact explores.

---

## 1. Project Setup & Prerequisites

### A. BigQuery & GCP Configuration
The evaluation harness and agent use BigQuery to introspect schemas, validate generated queries, and analyze execution performance metrics.

1. **Set your active GCP project:**
   ```bash
   export GOOGLE_CLOUD_PROJECT="<YOUR_PROJECT_ID>"
   gcloud config set project "$GOOGLE_CLOUD_PROJECT"
   ```

2. **Dual Service Account Architecture (Principle of Least Privilege):**
   We enforce a clean separation between the **Harness Evaluator** (which creates test datasets and validates results) and the **Agent Under Evaluation** (which can only query and inspect metadata, but cannot alter or delete benchmark datasets).

   Run the following script to provision both accounts in your project:

   ```bash
   export PROJECT_ID="<YOUR_PROJECT_ID>"
   export YOUR_USER_EMAIL="<YOUR_USER_EMAIL>"  # Your in-org GCP login email

   # ==========================================
   # 1. HARNESS SERVICE ACCOUNT (Evaluator / Provisioner)
   # Permissions: Run query jobs, create & edit benchmark datasets
   # ==========================================
   HARNESS_SA="ojof-eval-harness"
   HARNESS_EMAIL="${HARNESS_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

   gcloud iam service-accounts create "$HARNESS_SA" \
     --project="$PROJECT_ID" \
     --description="Benchmarking harness provisioner & evaluator" \
     --display-name="OJOF Eval Harness"

   gcloud projects add-iam-policy-binding "$PROJECT_ID" \
     --member="serviceAccount:$HARNESS_EMAIL" \
     --role="roles/bigquery.user"

   gcloud projects add-iam-policy-binding "$PROJECT_ID" \
     --member="serviceAccount:$HARNESS_EMAIL" \
     --role="roles/bigquery.dataEditor"

   # Allow your user account to impersonate the Harness SA (Keyless / Org-Policy Compliant)
   gcloud iam service-accounts add-iam-policy-binding "$HARNESS_EMAIL" \
     --project="$PROJECT_ID" \
     --member="user:${YOUR_USER_EMAIL}" \
     --role="roles/iam.serviceAccountTokenCreator"

   # ==========================================
   # 2. AGENT SERVICE ACCOUNT (Model Under Evaluation)
   # Permissions: Run query jobs, read-only metadata & tables (NO edit/delete)
   # ==========================================
   AGENT_SA="ojof-agent-runner"
   AGENT_EMAIL="${AGENT_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

   gcloud iam service-accounts create "$AGENT_SA" \
     --project="$PROJECT_ID" \
     --description="Agent under evaluation (read-only queries & introspection)" \
     --display-name="OJOF Agent Runner"

   gcloud projects add-iam-policy-binding "$PROJECT_ID" \
     --member="serviceAccount:$AGENT_EMAIL" \
     --role="roles/bigquery.jobUser"

   gcloud projects add-iam-policy-binding "$PROJECT_ID" \
     --member="serviceAccount:$AGENT_EMAIL" \
     --role="roles/bigquery.dataViewer"

   # Allow your user account to impersonate the Agent SA (Keyless / Org-Policy Compliant)
   gcloud iam service-accounts add-iam-policy-binding "$AGENT_EMAIL" \
     --project="$PROJECT_ID" \
     --member="user:${YOUR_USER_EMAIL}" \
     --role="roles/iam.serviceAccountTokenCreator"
   ```

3. **Keyless Authentication in Runner Environment:**
   Authenticate your user session (Application Default Credentials):
   ```bash
   gcloud auth application-default login --no-launch-browser
   ```
   Both the harness and the agent driver will automatically generate short-lived, in-memory tokens via impersonation without requiring static key files on disk.

---

### B. Looker API & Spectacles Setup
Create a `.env` file in the project root to configure Looker validation (this file is git-ignored):

```env
LOOKER_BASE_URL=https://your-looker-instance.cloud.looker.com
LOOKER_CLIENT_ID=your_client_id
LOOKER_CLIENT_SECRET=your_client_secret
LOOKER_PROJECT=your_project_name
```

---

## 2. Running Benchmarks & Verifiers

### A. Run SkillsBench Evaluation Suite
Execute the benchmark runner to evaluate tasks across skill modes (`with-skill` vs. `no-skill`):

```bash
# Dry run mode (validates task compilation and CLI command structure)
python3 eval/run_benchmark.py --tasks-dir tasks

# Live execution mode with Antigravity driver
python3 eval/run_benchmark.py --tasks-dir tasks --execute --model gemini-3.6-flash
```

### B. Run Offline LookML Linter & Verifiers
Audit any LookML directory directly against OJOF architectural invariants:

```bash
# Audit specific example or task directory
python3 verifiers/ojof_linter.py examples/tpch_sf1

# Run task-specific verifier
python3 tasks/task_tpch_sf1_multifact/verifier/test_outputs.py
```

### C. Validation with Spectacles
```bash
# Test connection
uvx --env-file .env spectacles connect

# Validate LookML syntax
uvx --env-file .env spectacles lookml

# Validate SQL queries against the warehouse
uvx --env-file .env spectacles sql

# Run Looker data tests
uvx --env-file .env spectacles assert
```

