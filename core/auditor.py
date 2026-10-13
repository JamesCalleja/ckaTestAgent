import subprocess
import json
import yaml
from typing import Dict, Any, Optional, List, Tuple
from .models import CheckResult

class Auditor:
    """Provides automated kubectl and cluster auditing utilities for CKA scenarios."""

    def __init__(self, kubeconfig: Optional[str] = None):
        self.kubeconfig = kubeconfig

    def run_cmd(self, cmd: str, timeout: int = 15) -> Tuple[int, str, str]:
        """Execute a shell command with timeout."""
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, "", str(e)

    def kubectl(self, args: str, timeout: int = 15) -> Tuple[int, str, str]:
        """Execute a kubectl command."""
        cmd = f"kubectl {args}"
        return self.run_cmd(cmd, timeout=timeout)

    def get_resource_json(self, kind: str, name: str, namespace: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetch a kubernetes resource and parse as JSON."""
        ns_flag = f"-n {namespace}" if namespace else ""
        code, out, _ = self.kubectl(f"get {kind} {name} {ns_flag} -o json")
        if code == 0 and out:
            try:
                return json.loads(out)
            except Exception:
                return None
        return None

    def get_resources_json(self, kind: str, namespace: Optional[str] = None, label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch list of kubernetes resources."""
        ns_flag = f"-n {namespace}" if namespace else "-A"
        label_flag = f"-l {label_selector}" if label_selector else ""
        code, out, _ = self.kubectl(f"get {kind} {ns_flag} {label_flag} -o json")
        if code == 0 and out:
            try:
                data = json.loads(out)
                return data.get("items", [])
            except Exception:
                return []
        return []

    def namespace_exists(self, ns: str) -> bool:
        """Check if namespace exists."""
        code, _, _ = self.kubectl(f"get ns {ns}")
        return code == 0

    def can_i(self, verb: str, resource: str, namespace: Optional[str] = None, as_user: Optional[str] = None, as_group: Optional[str] = None) -> bool:
        """Test RBAC permissions using kubectl auth can-i."""
        ns_flag = f"-n {namespace}" if namespace else ""
        as_flag = f"--as={as_user}" if as_user else ""
        group_flag = f"--as-group={as_group}" if as_group else ""
        code, out, _ = self.kubectl(f"auth can-i {verb} {resource} {ns_flag} {as_flag} {group_flag}")
        return code == 0 and out.strip().lower() == "yes"

    def check_node_cordoned(self, node_name: str) -> bool:
        """Check if a node is cordoned (SchedulingDisabled)."""
        node = self.get_resource_json("node", node_name)
        if not node:
            return False
        return node.get("spec", {}).get("unschedulable", False) is True

    def check_node_taint(self, node_name: str, key: str, value: Optional[str] = None, effect: Optional[str] = None) -> bool:
        """Check if a node has a specific taint."""
        node = self.get_resource_json("node", node_name)
        if not node:
            return False
        taints = node.get("spec", {}).get("taints", [])
        for t in taints:
            if t.get("key") == key:
                if value is not None and t.get("value") != value:
                    continue
                if effect is not None and t.get("effect") != effect:
                    continue
                return True
        return False

    def check_node_label(self, node_name: str, key: str, value: Optional[str] = None) -> bool:
        """Check if a node has a specific label."""
        node = self.get_resource_json("node", node_name)
        if not node:
            return False
        labels = node.get("metadata", {}).get("labels", {})
        if key in labels:
            if value is not None:
                return labels[key] == value
            return True
        return False

    def check_pod_running(self, name: str, namespace: str) -> bool:
        """Check if a pod is in Running phase with all containers ready."""
        pod = self.get_resource_json("pod", name, namespace)
        if not pod:
            return False
        phase = pod.get("status", {}).get("phase", "")
        if phase != "Running":
            return False
        container_statuses = pod.get("status", {}).get("containerStatuses", [])
        return len(container_statuses) > 0 and all(c.get("ready", False) for c in container_statuses)

    def check_deployment_ready(self, name: str, namespace: str, expected_replicas: Optional[int] = None) -> Tuple[bool, str]:
        """Check deployment availability and replica count."""
        deploy = self.get_resource_json("deployment", name, namespace)
        if not deploy:
            return False, f"Deployment '{name}' not found in namespace '{namespace}'"
        spec_replicas = deploy.get("spec", {}).get("replicas", 1)
        ready_replicas = deploy.get("status", {}).get("readyReplicas", 0)
        updated_replicas = deploy.get("status", {}).get("updatedReplicas", 0)

        if expected_replicas is not None and spec_replicas != expected_replicas:
            return False, f"Expected {expected_replicas} replicas, found spec.replicas={spec_replicas}"

        if ready_replicas != spec_replicas:
            return False, f"Ready replicas ({ready_replicas}) does not match desired ({spec_replicas})"

        if updated_replicas != spec_replicas:
            return False, f"Updated replicas ({updated_replicas}) does not match desired ({spec_replicas})"

        return True, f"Deployment '{name}' has {ready_replicas}/{spec_replicas} replicas ready"

    def check_pv_pvc_bound(self, pv_name: str, pvc_name: str, pvc_namespace: str) -> Tuple[bool, str]:
        """Check PV and PVC are bound to each other."""
        pv = self.get_resource_json("pv", pv_name)
        if not pv:
            return False, f"PersistentVolume '{pv_name}' not found"
        pvc = self.get_resource_json("pvc", pvc_name, pvc_namespace)
        if not pvc:
            return False, f"PersistentVolumeClaim '{pvc_name}' not found in '{pvc_namespace}'"

        pv_phase = pv.get("status", {}).get("phase", "")
        pvc_phase = pvc.get("status", {}).get("phase", "")

        if pv_phase != "Bound":
            return False, f"PV '{pv_name}' is in phase '{pv_phase}' (expected 'Bound')"
        if pvc_phase != "Bound":
            return False, f"PVC '{pvc_name}' is in phase '{pvc_phase}' (expected 'Bound')"

        # Check claimRef
        claim_ref = pv.get("spec", {}).get("claimRef", {})
        if claim_ref.get("name") != pvc_name or claim_ref.get("namespace") != pvc_namespace:
            return False, f"PV claimRef points to '{claim_ref.get('namespace')}/{claim_ref.get('name')}' instead of '{pvc_namespace}/{pvc_name}'"

        return True, "PV and PVC are successfully bound"
