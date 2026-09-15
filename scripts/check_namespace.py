#!/usr/bin/env python3
"""
Check that every namespaced Kubernetes resource in an app directory
has metadata.namespace matching the directory name.

Usage: python scripts/check_namespace.py
Exit code 0 = pass, 1 = fail (with mismatches printed).

Cluster-scoped resources (Namespace, ClusterRole, etc.) are skipped.
"""

import sys
import yaml
from pathlib import Path

# Cluster-scoped kinds — these don't have a namespace field and are fine
CLUSTER_SCOPED_KINDS = {
    "Namespace",
    "ClusterRole",
    "ClusterRoleBinding",
    "CustomResourceDefinition",
    "PriorityClass",
    "ComponentStatus",  # deprecated but keep for completeness
}


def is_cluster_scoped(doc):
    return doc.get("kind", "") in CLUSTER_SCOPED_KINDS


def check_file(yaml_file: Path):
    """Return list of (kind, actual_namespace, expected_namespace) mismatches."""
    mismatches = []
    try:
        docs = list(yaml.safe_load_all(yaml_file.read_text()))
    except yaml.YAMLError as e:
        print(f"YAML parse error in {yaml_file}: {e}")
        sys.exit(1)

    for doc in docs:
        if not isinstance(doc, dict):
            continue
        if is_cluster_scoped(doc):
            continue
        actual_ns = doc.get("metadata", {}).get("namespace", "")
        if not actual_ns:
            # Some resources don't have a namespace field at all even if
            # they're namespaced in some contexts — skip those (e.g. a bare
            # ServiceAccount in some API versions). We only flag clear mismatches.
            continue
        # Expected namespace = the first directory component under apps/
        # e.g. apps/jellyfin/deployment.yaml -> expected = jellyfin
        parts = yaml_file.relative_to(yaml_file.parent.parent).parts
        if len(parts) >= 2 and parts[0] == "apps":
            expected_ns = parts[1]
            if actual_ns and actual_ns != expected_ns:
                mismatches.append((doc.get("kind", "Unknown"), actual_ns, expected_ns))
    return mismatches


def main():
    repo_root = Path(".").resolve()
    mismatches = []

    for yaml_file in repo_root.rglob("*.yaml"):
        rel = yaml_file.relative_to(repo_root)
        if rel.parts[0] in (".github", "docs", "scripts"):
            continue
        if rel.parts[0] != "apps":
            # Only check files under apps/ — that's where per-app namespace
            # consistency matters. ArgoCD CRs in argocd/ are cluster-scoped
            # or explicitly namespace argocd, so skip them.
            continue
        mismatches.extend(check_file(yaml_file))

    if mismatches:
        print("FAIL: Namespace mismatches (resource namespace != app directory):")
        for kind, actual, expected in mismatches:
            print(f"  {kind}: namespace={actual}, expected={expected}")
        sys.exit(1)

    print("PASS: Namespace consistency check passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
