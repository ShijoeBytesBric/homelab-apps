# homelab-apps

Desired state of the HomeLab Kubernetes cluster — app manifests synced by ArgoCD.

This repo holds the actual Kubernetes manifests that ArgoCD deploys into the cluster: Deployments, Services, Ingresses, PVCs, ConfigMaps, and SealedSecrets (encrypted). It is read by ArgoCD, which is configured in the separate `homelab-git-mgmt` repo (https://github.com/ShijoeBytesBric/homelab-git-mgmt).

## Structure

```
homelab-apps/
├── apps/                    # Deployable app manifests (what ArgoCD syncs)
│   ├── jellyfin/
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml      # jellyfin/jellyfin:10.9.0
│   │   ├── service.yaml         # ClusterIP :80 → 8096
│   │   ├── pvc-config.yaml      # 10Gi config volume
│   │   ├── pvc-media.yaml       # 50Gi media volume
│   │   └── sealedsecret.yaml    # SealedSecret — encrypted, safe to commit
│   ├── flaresolverr/
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml      # flaresolverr/flaresolverr:1.3.1
│   │   └── service.yaml
│   ├── openwrt/
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml      # hostNetwork + privileged, openwrt/rootfs:23.05.0
│   │   ├── configmap.yaml       # OpenWrt config files (to be populated)
│   │   └── pvc.yaml             # 1Gi overlay
│   └── monitoring/
│       ├── namespace.yaml
│       └── values.yaml          # Helm values for kube-prometheus-stack
├── docs/                    # Documentation (reference copies from homelab-git-mgmt)
│   ├── PLAN.md
│   ├── argocd-setup.md
│   ├── app-manifests.md
│   ├── github-actions.md
│   └── rbac.md
├── .github/
│   └── workflows/
│       └── validate.yaml    # CI: validates manifests client-side
├── .gitignore
└── README.md                # This file
```

## Relationship to homelab-git-mgmt

- `homelab-git-mgmt` (https://github.com/ShijoeBytesBric/homelab-git-mgmt) = ArgoCD's config. Holds the `AppProject`, `Application` CRs, RBAC roles, and CI. The `Application` CRs here point at paths in this repo (e.g. `apps/jellyfin/`), and ArgoCD pulls the manifests from here.
- This repo (`homelab-apps`) = the cluster's desired state. What ArgoCD actually deploys.

## SealedSecrets

Secrets are stored as SealedSecrets (encrypted with the in-cluster SealedSecrets controller's public key). To create a sealed secret:

```bash
kubectl create secret generic <name>-secrets --dry-run=client -o yaml \
  --from-literal=KEY=value > /tmp/plain.yaml
kubeseal --cert=sealed-secrets-public-key.pem --format yaml \
  < /tmp/plain.yaml > apps/<name>/sealedsecret.yaml
```

Commit the sealed file. The plaintext `/tmp/plain.yaml` can be deleted. See `docs/argocd-setup.md` section 7.

## CI

The `validate.yaml` workflow runs on every push and PR. It checks YAML syntax, K8s resource schema (client-side), image tag pinning, and namespace consistency. Run locally with:

```bash
pip install yamllint pyyaml
yamllint -c .yamllint apps/
for f in $(find apps/ -name '*.yaml'); do kubectl apply --dry-run=client -f "$f" || echo "FAIL: $f"; done
python scripts/check_image_tags.py
python scripts/check_namespace.py
```

Note: the validation scripts (`scripts/`) and the CI workflow live in both repos. The canonical version is in `homelab-git-mgmt`; this repo carries its own copy for independent validation.
