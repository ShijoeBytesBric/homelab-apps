# homelab-apps

Desired-state manifest repository for the Homelab Kubernetes cluster.

This repository holds the Kubernetes resources that ArgoCD deploys into the cluster:
Deployments, Services, PersistentVolumeClaims, SealedSecrets (encrypted), HTTPRoutes,
and Namespaces. ArgoCD reads this repository and applies the manifests to the cluster.
It is configured by the separate [homelab-git-mgmt](https://github.com/ShijoeBytesBric/homelab-git-mgmt)
repository, which holds the `AppProject`, `Application` CRs, and RBAC.


## What is deployed

| Application | Image | Storage | Secret | Exposure |
|---|---|---|---|---|
| jellyfin | `jellyfin/jellyfin:10.9.0` | 10Gi config PVC + 50Gi media PVC | SealedSecret: `JELLYFIN__DEFAULTADMINPASSWORD` | HTTPRoute (`jellyfin.<your-domain>`) |
| flaresolverr | `flaresolverr/flaresolverr:v3.5.0` | none | none | HTTPRoute (optional) |
| monitoring | kube-prometheus-stack chart v60.3.0 | 20Gi PVC (Prometheus) | optional: Grafana `adminPassword` | HTTPRoute (`monitoring.<your-domain>`) |

**Repository structure:**

```
homelab-apps/
├── apps/
│   ├── jellyfin/
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml          # jellyfin/jellyfin:10.9.0
│   │   ├── service.yaml             # ClusterIP :80 → 8096
│   │   ├── pvc-config.yaml          # 10Gi config volume
│   │   ├── pvc-media.yaml           # 50Gi media volume
│   │   ├── sealedsecret.yaml        # SealedSecret — JELLYFIN__DEFAULTADMINPASSWORD
│   │   └── httproute.yaml           # Gateway API HTTPRoute (explicit defaults)
│   ├── flaresolverr/
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml          # flaresolverr/flaresolverr:v3.5.0
│   │   ├── service.yaml
│   │   └── httproute.yaml           # (optional — copy jellyfin pattern)
│   └── monitoring/
│       ├── namespace.yaml
│       ├── values.yaml              # Helm values for kube-prometheus-stack (reference only)
│       └── httproute.yaml           # (optional — copy jellyfin pattern)
├── .github/workflows/
│   └── validate.yaml               # CI: client-side manifest validation
├── scripts/
│   ├── validate_k8s.py
│   ├── check_image_tags.py
│   ├── check_namespace.py
│   └── check_servicemonitor.py     # placeholder
├── .yamllint
└── README.md
```


## SealedSecrets

Secrets are stored as **SealedSecrets** — encrypted with the in-cluster
SealedSecrets controller's public key. The plaintext never touches Git.

To create or update a sealed secret:

```bash
# 1. Build the plaintext Secret locally (never committed)
kubectl create secret generic <name>-secrets --dry-run=client -o yaml \
  --from-literal=KEY=value \
  > /tmp/plain.yaml

# 2. Seal it with the controller's public key
kubeseal --cert=sealed-secrets-public-key.pem --format yaml \
  < /tmp/plain.yaml > apps/<name>/sealedsecret.yaml

# 3. Commit the sealed file, delete the plaintext
git add apps/<name>/sealedsecret.yaml
rm /tmp/plain.yaml
```

The public key (`sealed-secrets-public-key.pem`) is exported from the controller
with `kubeseal --fetch-cert > sealed-secrets-public-key.pem` and is gitignored.
Keep it safe — you need it to seal secrets.

**Jellyfin password** — the committed `apps/jellyfin/sealedsecret.yaml` contains an
encrypted `JELLYFIN__DEFAULTADMINPASSWORD`. Verify it is the password you want, or
re-seal with a new one using the `--merge-into` command documented in the deploy
guide. This preserves the existing template's namespace and labels.

**Grafana password** — optional. Leave blank for the default `admin`/`admin`, or set
it in the `Application` CR's inline `values:` block in `homelab-git-mgmt`.


## Image tags

All container images must use a pinned tag — no `:latest`, no untagged images. CI
enforces this with `scripts/check_image_tags.py`.

| Application | Image | Tag |
|---|---|---|
| jellyfin | `jellyfin/jellyfin` | `10.9.0` |
| flaresolverr | `flaresolverr/flaresolverr` | `v3.5.0` |

FlareSolverr tags on Docker Hub use a `v` prefix (for example, `v3.5.0`,
`v3.4.1`). A bare version number without the `v` prefix does not exist on Docker Hub.


## Values source of truth (monitoring)

The monitoring `Application` CR in `homelab-git-mgmt` points at the Helm chart repo
and declares an inline `values:` block. The `apps/monitoring/values.yaml` file in
this repository is reference documentation only — ArgoCD does not render it. If you
change monitoring values, edit the inline block in the `Application` CR. Alternatively,
point the `Application` CR at a git path in this repository and make `values.yaml`
authoritative.


## CI

The `validate` workflow runs on every push and pull request to `main`. It checks:

| Check | Tool | Catches |
|---|---|---|
| YAML lint | `yamllint` | Indentation, tabs, missing `---`, `yes`/`no` vs `true`/`false` |
| K8s resource structure | `scripts/validate_k8s.py` | Missing required fields per resource kind |
| Image tags | `scripts/check_image_tags.py` | `:latest` or untagged images |
| Namespace consistency | `scripts/check_namespace.py` | Resource namespace does not match app directory name |

Run locally before pushing:

```bash
pip install yamllint pyyaml
yamllint -c .yamllint apps/
python scripts/validate_k8s.py
python scripts/check_image_tags.py
python scripts/check_namespace.py
```

CI is fully client-side — no cluster access. Broken YAML in the repository results in
a failed ArgoCD sync attempt, so green CI before pushing matters.


## Relationship to homelab-git-mgmt

| Repository | Role |
|---|---|
| `homelab-git-mgmt` | ArgoCD's configuration — AppProject, Application CRs, RBAC, repo secret, CI |
| `homelab-apps` (this repository) | Cluster's desired state — what ArgoCD actually deploys |

The `Application` CRs in `homelab-git-mgmt` point at paths in this repository. When
a change is pushed here, ArgoCD detects the new commit and syncs automatically
(automated sync with `selfHeal: true`).


## License

This repository does not currently include a license. If you plan to use or
modify this project, check with the repository owner before doing so.
