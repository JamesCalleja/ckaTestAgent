import os
from typing import List
from core.models import Scenario, Domain, VerificationCheck, CheckResult
from core.auditor import Auditor

def get_cka_exam_1() -> List[Scenario]:
    scenarios: List[Scenario] = []

    # -------------------------------------------------------------
    # Task 1: RBAC Configuration
    # -------------------------------------------------------------
    def check_task_1_sa(auditor: Auditor) -> CheckResult:
        sa = auditor.get_resource_json("serviceaccount", "dev-sa", "cka-auth")
        if sa:
            return CheckResult("ServiceAccount 'dev-sa' exists", True, 2.0, 2.0, "ServiceAccount found in cka-auth")
        return CheckResult("ServiceAccount 'dev-sa' exists", False, 0.0, 2.0, "dev-sa not found in namespace cka-auth")

    def check_task_1_role(auditor: Auditor) -> CheckResult:
        role = auditor.get_resource_json("role", "pod-reader", "cka-auth")
        if not role:
            # Check if created as ClusterRole by mistake
            cr = auditor.get_resource_json("clusterrole", "pod-reader")
            if cr:
                return CheckResult("Role 'pod-reader' exists in cka-auth", False, 0.0, 2.5, "Created as ClusterRole instead of namespace-scoped Role in cka-auth")
            return CheckResult("Role 'pod-reader' exists in cka-auth", False, 0.0, 2.5, "Role 'pod-reader' not found in cka-auth")
        
        rules = role.get("rules", [])
        has_pods = any("pods" in r.get("resources", []) and set(["get", "list", "watch"]).issubset(set(r.get("verbs", []))) for r in rules)
        if has_pods:
            return CheckResult("Role 'pod-reader' exists in cka-auth", True, 2.5, 2.5, "Role correctly permits get, list, watch on pods")
        return CheckResult("Role 'pod-reader' exists in cka-auth", False, 1.0, 2.5, "Role exists but rules do not permit get/list/watch on pods")

    def check_task_1_binding(auditor: Auditor) -> CheckResult:
        can_list = auditor.can_i("list", "pods", namespace="cka-auth", as_user="system:serviceaccount:cka-auth:dev-sa")
        can_get = auditor.can_i("get", "pods", namespace="cka-auth", as_user="system:serviceaccount:cka-auth:dev-sa")
        can_watch = auditor.can_i("watch", "pods", namespace="cka-auth", as_user="system:serviceaccount:cka-auth:dev-sa")
        can_delete = auditor.can_i("delete", "pods", namespace="cka-auth", as_user="system:serviceaccount:cka-auth:dev-sa")

        if can_list and can_get and can_watch and not can_delete:
            return CheckResult("RoleBinding 'dev-sa-binding' and permission check", True, 2.5, 2.5, "dev-sa successfully authorized for get/list/watch pods in cka-auth")
        elif can_list and can_get and can_watch:
            return CheckResult("RoleBinding 'dev-sa-binding' and permission check", True, 2.0, 2.5, "dev-sa has read access but has overly permissive verbs")
        return CheckResult("RoleBinding 'dev-sa-binding' and permission check", False, 0.0, 2.5, "dev-sa is NOT authorized to list/get pods in cka-auth")

    scenarios.append(Scenario(
        id="cka-exam1-t1",
        number=1,
        title="RBAC Configuration",
        domain=Domain.CLUSTER_ARCH,
        weight=7.0,
        namespace="cka-auth",
        description="Configure role-based access control (RBAC) to allow a dedicated service account to read pods within a specific namespace.",
        requirements=[
            "Create a ServiceAccount named 'dev-sa' in namespace 'cka-auth'.",
            "Create a Role named 'pod-reader' in namespace 'cka-auth' granting 'get', 'list', and 'watch' verbs on 'pods'.",
            "Create a RoleBinding named 'dev-sa-binding' in namespace 'cka-auth' binding 'dev-sa' to 'pod-reader'."
        ],
        hints=[
            "kubectl create sa dev-sa -n cka-auth",
            "kubectl create role pod-reader --verb=get,list,watch --resource=pods -n cka-auth",
            "kubectl create rolebinding dev-sa-binding --role=pod-reader --serviceaccount=cka-auth:dev-sa -n cka-auth"
        ],
        checks=[
            VerificationCheck("dev-sa ServiceAccount", 2.0, check_task_1_sa),
            VerificationCheck("pod-reader Role", 2.5, check_task_1_role),
            VerificationCheck("dev-sa-binding & Permissions", 2.5, check_task_1_binding)
        ]
    ))

    # -------------------------------------------------------------
    # Task 2: Node Maintenance (Drain / Cordon)
    # -------------------------------------------------------------
    def check_task_2_node_ready(auditor: Auditor) -> CheckResult:
        nodes = auditor.get_resources_json("node")
        for node in nodes:
            name = node.get("metadata", {}).get("name", "")
            unschedulable = node.get("spec", {}).get("unschedulable", False)
            if unschedulable:
                return CheckResult("Node uncordoned", False, 3.0, 6.0, f"Node '{name}' is still cordoned (SchedulingDisabled)")
        return CheckResult("Node uncordoned & available", True, 6.0, 6.0, "All worker nodes are uncordoned and Ready")

    scenarios.append(Scenario(
        id="cka-exam1-t2",
        number=2,
        title="Node Maintenance & Workload Eviction",
        domain=Domain.CLUSTER_ARCH,
        weight=6.0,
        namespace=None,
        description="Simulate node maintenance on 'minikube-m02' by draining running pods, verifying cordon status, and then uncordoning the node.",
        requirements=[
            "Drain all workloads from worker node 'minikube-m02' (ignore daemonsets and constraint pods if needed).",
            "Verify the node enters 'SchedulingDisabled' mode.",
            "Once verified, return 'minikube-m02' to active status by uncordoning it."
        ],
        hints=[
            "kubectl drain minikube-m02 --ignore-daemonsets --force --delete-emptydir-data",
            "kubectl get nodes",
            "kubectl uncordon minikube-m02"
        ],
        checks=[
            VerificationCheck("Node uncordoned and ready", 6.0, check_task_2_node_ready)
        ]
    ))

    # -------------------------------------------------------------
    # Task 3: Multi-Container Pod & Shared Volume
    # -------------------------------------------------------------
    def check_task_3(auditor: Auditor) -> CheckResult:
        pod = auditor.get_resource_json("pod", "multi-app", "cka-workload")
        if not pod:
            return CheckResult("Multi-container pod 'multi-app'", False, 0.0, 7.0, "Pod 'multi-app' not found in namespace 'cka-workload'")
        
        containers = pod.get("spec", {}).get("containers", [])
        c_names = [c.get("name") for c in containers]

        if "app" not in c_names or "sidecar" not in c_names:
            return CheckResult("Multi-container pod 'multi-app'", False, 3.0, 7.0, f"Expected containers ['app', 'sidecar'], found: {c_names}")

        # Check volume mount
        app_c = next(c for c in containers if c.get("name") == "app")
        side_c = next(c for c in containers if c.get("name") == "sidecar")
        app_mounts = [m.get("mountPath") for m in app_c.get("volumeMounts", [])]
        side_mounts = [m.get("mountPath") for m in side_c.get("volumeMounts", [])]

        if "/var/log" not in app_mounts or "/var/log" not in side_mounts:
            return CheckResult("Volume mount on /var/log", False, 4.5, 7.0, "Both containers must mount shared volume at /var/log")

        phase = pod.get("status", {}).get("phase", "")
        if phase != "Running":
            return CheckResult("Pod running status", False, 5.0, 7.0, f"Pod is in phase '{phase}' (expected Running)")

        return CheckResult("Multi-container pod 'multi-app'", True, 7.0, 7.0, "Pod is running with both 'app' and 'sidecar' containers sharing /var/log volume")

    scenarios.append(Scenario(
        id="cka-exam1-t3",
        number=3,
        title="Multi-Container Pod & Shared Volume",
        domain=Domain.WORKLOADS,
        weight=7.0,
        namespace="cka-workload",
        description="Deploy a multi-container pod where an application container writes logs and a sidecar container tails the log stream from a shared emptyDir volume.",
        requirements=[
            "Create a pod named 'multi-app' in namespace 'cka-workload'.",
            "Container 1: name 'app', image 'busybox', command writing date to '/var/log/app.log' every 5s.",
            "Container 2: name 'sidecar', image 'busybox', command tailing '/var/log/app.log'.",
            "Volume: emptyDir named 'shared-logs' mounted at '/var/log' in both containers."
        ],
        hints=[
            "Define 'volumes: - name: shared-logs emptyDir: {}' under spec",
            "Add 'volumeMounts: - name: shared-logs mountPath: /var/log' to both containers"
        ],
        checks=[
            VerificationCheck("Multi-container pod 'multi-app'", 7.0, check_task_3)
        ]
    ))

    # -------------------------------------------------------------
    # Task 4: NetworkPolicy Enforcement
    # -------------------------------------------------------------
    def check_task_4(auditor: Auditor) -> CheckResult:
        deploy_ok, msg = auditor.check_deployment_ready("backend", "cka-network", expected_replicas=2)
        if not deploy_ok:
            return CheckResult("Deployment 'backend'", False, 0.0, 8.0, msg)

        svc = auditor.get_resource_json("service", "backend-svc", "cka-network")
        if not svc:
            return CheckResult("Service 'backend-svc'", False, 2.5, 8.0, "Service 'backend-svc' not found in 'cka-network'")

        svc_selector = svc.get("spec", {}).get("selector", {})
        if svc_selector != {"app": "backend"}:
            return CheckResult("Service 'backend-svc' selector", False, 3.5, 8.0, f"Service selector is {svc_selector}, expected {{'app': 'backend'}}")

        netpol = auditor.get_resource_json("networkpolicy", "backend-netpol", "cka-network")
        if not netpol:
            return CheckResult("NetworkPolicy 'backend-netpol'", False, 4.0, 8.0, "NetworkPolicy 'backend-netpol' not found in 'cka-network'")

        pod_selector = netpol.get("spec", {}).get("podSelector", {}).get("matchLabels", {})
        if pod_selector != {"app": "backend"}:
            return CheckResult("NetworkPolicy podSelector", False, 5.0, 8.0, f"podSelector is {pod_selector}, expected {{'app': 'backend'}}")

        ingress = netpol.get("spec", {}).get("ingress", [])
        if not ingress:
            return CheckResult("NetworkPolicy ingress rules", False, 5.5, 8.0, "NetworkPolicy has no ingress rules configured")

        from_rule = ingress[0].get("from", [])
        has_access_label = any(f.get("podSelector", {}).get("matchLabels", {}).get("access") == "granted" for f in from_rule)
        
        if not has_access_label:
            return CheckResult("NetworkPolicy ingress source", False, 6.0, 8.0, "Ingress rule does not filter by podSelector matchLabels: {access: granted}")

        return CheckResult("NetworkPolicy enforcement", True, 8.0, 8.0, "Deployment, Service, and NetworkPolicy correctly configured")

    scenarios.append(Scenario(
        id="cka-exam1-t4",
        number=4,
        title="NetworkPolicy Enforcement",
        domain=Domain.NETWORKING,
        weight=8.0,
        namespace="cka-network",
        description="Enforce ingress network security to isolate backend pods so only authorized client pods can reach them on port 80.",
        requirements=[
            "Create deployment 'backend' in 'cka-network' (image: nginx:alpine, 2 replicas, label app=backend, port 80).",
            "Expose deployment with ClusterIP service 'backend-svc' on port 80.",
            "Create NetworkPolicy 'backend-netpol' targeting 'app=backend' pods.",
            "Allow ingress on TCP port 80 ONLY from pods with label 'access=granted'. Deny all other ingress."
        ],
        hints=[
            "kubectl expose deployment backend --name=backend-svc --port=80 --target-port=80 -n cka-network",
            "NetworkPolicy spec: podSelector: matchLabels: {app: backend}, ingress: - from: - podSelector: matchLabels: {access: granted} ports: - protocol: TCP port: 80"
        ],
        checks=[
            VerificationCheck("NetworkPolicy & Service Setup", 8.0, check_task_4)
        ]
    ))

    # -------------------------------------------------------------
    # Task 5: Persistent Storage (PV & PVC)
    # -------------------------------------------------------------
    def check_task_5(auditor: Auditor) -> CheckResult:
        bound, msg = auditor.check_pv_pvc_bound("pv-data", "pvc-data", "cka-storage")
        if not bound:
            return CheckResult("PV & PVC Binding", False, 0.0, 8.0, msg)

        pod = auditor.get_resource_json("pod", "storage-pod", "cka-storage")
        if not pod:
            return CheckResult("Pod 'storage-pod'", False, 5.0, 8.0, "Pod 'storage-pod' not found in namespace 'cka-storage'")

        mounts = pod.get("spec", {}).get("containers", [{}])[0].get("volumeMounts", [])
        has_mount = any(m.get("mountPath") == "/data" for m in mounts)
        if not has_mount:
            return CheckResult("Volume Mount '/data'", False, 6.0, 8.0, "Pod does not mount claim at '/data'")

        phase = pod.get("status", {}).get("phase", "")
        if phase != "Running":
            return CheckResult("Pod running status", False, 6.5, 8.0, f"Pod phase is '{phase}' (expected Running)")

        return CheckResult("PV, PVC, and Pod Storage", True, 8.0, 8.0, "PV & PVC bound and successfully mounted at /data in storage-pod")

    scenarios.append(Scenario(
        id="cka-exam1-t5",
        number=5,
        title="Persistent Storage (PV & PVC)",
        domain=Domain.STORAGE,
        weight=8.0,
        namespace="cka-storage",
        description="Provision a persistent hostPath volume, claim it via PVC, and mount it into an application pod.",
        requirements=[
            "Create PersistentVolume 'pv-data' (capacity: 1Gi, accessMode: ReadWriteOnce, storageClassName: manual, hostPath: /mnt/data).",
            "Create PersistentVolumeClaim 'pvc-data' in 'cka-storage' requesting 1Gi, accessMode ReadWriteOnce, storageClassName: manual.",
            "Create Pod 'storage-pod' in 'cka-storage' (image: busybox, command: sleep 3600), mounting 'pvc-data' at '/data'."
        ],
        hints=[
            "Make sure both PV and PVC have storageClassName: manual",
            "Under pod spec: volumes: - name: data persistentVolumeClaim: claimName: pvc-data"
        ],
        checks=[
            VerificationCheck("Persistent Storage", 8.0, check_task_5)
        ]
    ))

    # -------------------------------------------------------------
    # Task 6: Static Pod Creation
    # -------------------------------------------------------------
    def check_task_6(auditor: Auditor) -> CheckResult:
        pod = auditor.get_resource_json("pod", "static-web-minikube", "default")
        if not pod:
            # Check without -minikube suffix or other namespace
            pods = auditor.get_resources_json("pod", "default")
            static_candidates = [p for p in pods if "static-web" in p.get("metadata", {}).get("name", "")]
            if static_candidates:
                pod = static_candidates[0]
            else:
                return CheckResult("Static Pod running", False, 0.0, 7.0, "Static pod 'static-web-minikube' not found running in default namespace")

        phase = pod.get("status", {}).get("phase", "")
        if phase != "Running":
            return CheckResult("Static Pod status", False, 3.5, 7.0, f"Pod is in phase '{phase}' (expected Running)")

        image = pod.get("spec", {}).get("containers", [{}])[0].get("image", "")
        if "nginx" not in image:
            return CheckResult("Static Pod image", False, 4.0, 7.0, f"Pod image is '{image}', expected 'nginx:alpine'")

        return CheckResult("Static Pod running", True, 7.0, 7.0, "Static pod 'static-web-minikube' running successfully on control plane")

    scenarios.append(Scenario(
        id="cka-exam1-t6",
        number=6,
        title="Static Pod Creation",
        domain=Domain.CLUSTER_ARCH,
        weight=7.0,
        namespace="default",
        description="Deploy a static pod directly managed by the kubelet on the control plane node.",
        requirements=[
            "Configure a static pod named 'static-web' using image 'nginx:alpine'.",
            "Place the manifest in the kubelet static pod directory on node 'minikube' (/etc/kubernetes/manifests/).",
            "Verify the pod is running as 'static-web-minikube' in the default namespace."
        ],
        hints=[
            "SSH into the node: minikube ssh",
            "Place static-web.yaml in /etc/kubernetes/manifests/",
            "Verify with: kubectl get pods"
        ],
        checks=[
            VerificationCheck("Static Pod Deployment", 7.0, check_task_6)
        ]
    ))

    # -------------------------------------------------------------
    # Task 7: Deployment Rollouts & Scaling
    # -------------------------------------------------------------
    def check_task_7(auditor: Auditor) -> CheckResult:
        deploy = auditor.get_resource_json("deployment", "nginx-deploy", "cka-deploy")
        if not deploy:
            return CheckResult("Deployment 'nginx-deploy'", False, 0.0, 7.0, "Deployment 'nginx-deploy' not found in 'cka-deploy'")

        image = deploy.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [{}])[0].get("image", "")
        if "1.25" not in image:
            return CheckResult("Image update to 1.25.0", False, 2.0, 7.0, f"Container image is '{image}', expected 'nginx:1.25.0'")

        ready, msg = auditor.check_deployment_ready("nginx-deploy", "cka-deploy", expected_replicas=5)
        if not ready:
            return CheckResult("Scaling to 5 replicas", False, 4.0, 7.0, msg)

        return CheckResult("Deployment Rollouts & Scaling", True, 7.0, 7.0, "Deployment updated to nginx:1.25.0 with all 5 replicas available")

    scenarios.append(Scenario(
        id="cka-exam1-t7",
        number=7,
        title="Deployment Rollouts & Scaling",
        domain=Domain.WORKLOADS,
        weight=7.0,
        namespace="cka-deploy",
        description="Manage application lifecycles by performing a rolling image update and scaling replicas.",
        requirements=[
            "Create Deployment 'nginx-deploy' in 'cka-deploy' with 3 replicas (image: nginx:1.24.0).",
            "Update the container image to 'nginx:1.25.0' and ensure rollout completes.",
            "Scale the deployment up to 5 replicas and verify all pods are running."
        ],
        hints=[
            "kubectl create deployment nginx-deploy --image=nginx:1.24.0 --replicas=3 -n cka-deploy",
            "kubectl set image deployment/nginx-deploy nginx=nginx:1.25.0 -n cka-deploy",
            "kubectl scale deployment/nginx-deploy --replicas=5 -n cka-deploy"
        ],
        checks=[
            VerificationCheck("Deployment Rollout & Scale", 7.0, check_task_7)
        ]
    ))

    # -------------------------------------------------------------
    # Task 8: Node Affinity & Scheduling
    # -------------------------------------------------------------
    def check_task_8(auditor: Auditor) -> CheckResult:
        has_label = auditor.check_node_label("minikube-m02", "tier", "frontend")
        if not has_label:
            return CheckResult("Node label 'tier=frontend'", False, 0.0, 7.0, "Node 'minikube-m02' does not have label 'tier=frontend'")

        pod = auditor.get_resource_json("pod", "frontend-sched", "cka-sched")
        if not pod:
            return CheckResult("Pod 'frontend-sched'", False, 3.0, 7.0, "Pod 'frontend-sched' not found in 'cka-sched'")

        node_name = pod.get("spec", {}).get("nodeName", "")
        if node_name != "minikube-m02":
            return CheckResult("Scheduled on minikube-m02", False, 4.0, 7.0, f"Pod is scheduled on node '{node_name}' (expected 'minikube-m02')")

        phase = pod.get("status", {}).get("phase", "")
        if phase != "Running":
            return CheckResult("Pod running state", False, 5.0, 7.0, f"Pod phase is '{phase}' (expected Running)")

        return CheckResult("Node Affinity & Scheduling", True, 7.0, 7.0, "Node labeled tier=frontend and pod scheduled and running on minikube-m02")

    scenarios.append(Scenario(
        id="cka-exam1-t8",
        number=8,
        title="Node Affinity & Scheduling",
        domain=Domain.WORKLOADS,
        weight=7.0,
        namespace="cka-sched",
        description="Target specific nodes using node labels and pod scheduling constraints (nodeSelector or nodeAffinity).",
        requirements=[
            "Label node 'minikube-m02' with 'tier=frontend'.",
            "Create a pod named 'frontend-sched' in namespace 'cka-sched' using image 'nginx:alpine'.",
            "Configure nodeSelector or nodeAffinity so the pod is scheduled strictly onto nodes with label 'tier=frontend'.",
            "Verify the pod is running on 'minikube-m02'."
        ],
        hints=[
            "kubectl label node minikube-m02 tier=frontend",
            "Under pod spec: nodeSelector: tier: frontend"
        ],
        checks=[
            VerificationCheck("Node Affinity & Scheduling", 7.0, check_task_8)
        ]
    ))

    # -------------------------------------------------------------
    # Task 9: Ingress Routing
    # -------------------------------------------------------------
    def check_task_9(auditor: Auditor) -> CheckResult:
        svc = auditor.get_resource_json("service", "web-service", "cka-ingress")
        if not svc:
            return CheckResult("Service 'web-service'", False, 0.0, 8.0, "Service 'web-service' not found in 'cka-ingress'")

        ing = auditor.get_resource_json("ingress", "web-ingress", "cka-ingress")
        if not ing:
            return CheckResult("Ingress 'web-ingress'", False, 3.0, 8.0, "Ingress 'web-ingress' not found in 'cka-ingress'")

        rules = ing.get("spec", {}).get("rules", [])
        if not rules:
            return CheckResult("Ingress rules", False, 4.0, 8.0, "Ingress has no rules defined")

        rule = rules[0]
        host = rule.get("host", "")
        if host != "app.example.com":
            return CheckResult("Ingress host", False, 5.0, 8.0, f"Ingress host is '{host}', expected 'app.example.com'")

        paths = rule.get("http", {}).get("paths", [])
        if not paths:
            return CheckResult("Ingress HTTP path", False, 5.5, 8.0, "No HTTP paths defined under ingress rules")

        backend_svc = paths[0].get("backend", {}).get("service", {}).get("name", "")
        if backend_svc != "web-service":
            return CheckResult("Ingress backend service", False, 6.0, 8.0, f"Backend service is '{backend_svc}', expected 'web-service'")

        return CheckResult("Ingress Routing", True, 8.0, 8.0, "Service and Ingress configured for host 'app.example.com' -> 'web-service:80'")

    scenarios.append(Scenario(
        id="cka-exam1-t9",
        number=9,
        title="Ingress Routing",
        domain=Domain.NETWORKING,
        weight=8.0,
        namespace="cka-ingress",
        description="Expose a backend service using an HTTP Ingress rule configured with host and path routing.",
        requirements=[
            "Create deployment/pod 'web-app' (image: nginx:alpine) in 'cka-ingress'.",
            "Expose it with ClusterIP service 'web-service' on port 80.",
            "Create Ingress 'web-ingress' in 'cka-ingress' with host 'app.example.com', path '/' (Prefix), routing to 'web-service' on port 80."
        ],
        hints=[
            "kubectl create ingress web-ingress --rule=app.example.com/=web-service:80 -n cka-ingress"
        ],
        checks=[
            VerificationCheck("Ingress Routing", 8.0, check_task_9)
        ]
    ))

    # -------------------------------------------------------------
    # Task 10: Resource Requests, Limits & Metrics Querying
    # -------------------------------------------------------------
    def check_task_10(auditor: Auditor) -> CheckResult:
        pod = auditor.get_resource_json("pod", "heavy-pod", "cka-resources")
        if not pod:
            return CheckResult("Pod 'heavy-pod'", False, 0.0, 6.0, "Pod 'heavy-pod' not found in 'cka-resources'")

        res = pod.get("spec", {}).get("containers", [{}])[0].get("resources", {})
        req = res.get("requests", {})
        lim = res.get("limits", {})

        if req.get("cpu") != "100m" or req.get("memory") != "128Mi":
            return CheckResult("Resource requests", False, 2.0, 6.0, f"Requests are {req}, expected cpu: 100m, memory: 128Mi")

        if lim.get("cpu") != "200m" or lim.get("memory") != "256Mi":
            return CheckResult("Resource limits", False, 3.5, 6.0, f"Limits are {lim}, expected cpu: 200m, memory: 256Mi")

        if not os.path.exists("/tmp/top-cpu-pods.txt"):
            return CheckResult("CPU metrics file '/tmp/top-cpu-pods.txt'", False, 4.0, 6.0, "File '/tmp/top-cpu-pods.txt' does not exist")

        with open("/tmp/top-cpu-pods.txt", "r") as f:
            content = f.read().strip()
            if not content:
                return CheckResult("CPU metrics file content", False, 4.5, 6.0, "File '/tmp/top-cpu-pods.txt' is empty")

        return CheckResult("Resource Requests & Limits", True, 6.0, 6.0, "Pod requests/limits set accurately and CPU metrics captured")

    scenarios.append(Scenario(
        id="cka-exam1-t10",
        number=10,
        title="Resource Requests, Limits & Pod Metrics",
        domain=Domain.TROUBLESHOOTING,
        weight=6.0,
        namespace="cka-resources",
        description="Set compute resource requests and limits on a container and query pod resource consumption.",
        requirements=[
            "Create pod 'heavy-pod' in namespace 'cka-resources' (image: nginx:alpine).",
            "Configure requests: cpu: 100m, memory: 128Mi.",
            "Configure limits: cpu: 200m, memory: 256Mi.",
            "Query pod CPU usage across all namespaces and save output to '/tmp/top-cpu-pods.txt'."
        ],
        hints=[
            "kubectl run heavy-pod --image=nginx:alpine --requests='cpu=100m,memory=128Mi' --limits='cpu=200m,memory=256Mi' -n cka-resources",
            "kubectl top pods -A --sort-by=cpu > /tmp/top-cpu-pods.txt"
        ],
        checks=[
            VerificationCheck("Resource Limits & Metrics", 6.0, check_task_10)
        ]
    ))

    # -------------------------------------------------------------
    # Task 11: ConfigMaps & Secrets
    # -------------------------------------------------------------
    def check_task_11(auditor: Auditor) -> CheckResult:
        cm = auditor.get_resource_json("configmap", "app-config", "cka-config")
        if not cm or cm.get("data", {}).get("APP_COLOR") != "darkblue":
            return CheckResult("ConfigMap 'app-config'", False, 0.0, 6.0, "ConfigMap 'app-config' missing or key APP_COLOR != darkblue")

        sec = auditor.get_resource_json("secret", "app-secret", "cka-config")
        if not sec:
            return CheckResult("Secret 'app-secret'", False, 2.0, 6.0, "Secret 'app-secret' not found in 'cka-config'")

        pod = auditor.get_resource_json("pod", "config-pod", "cka-config")
        if not pod:
            return CheckResult("Pod 'config-pod'", False, 3.0, 6.0, "Pod 'config-pod' not found in 'cka-config'")

        # Check env var
        c0 = pod.get("spec", {}).get("containers", [{}])[0]
        envs = c0.get("env", [])
        has_color_env = any(e.get("name") == "APP_COLOR" for e in envs)
        if not has_color_env:
            return CheckResult("ConfigMap Environment Injection", False, 4.0, 6.0, "Pod missing environment variable APP_COLOR")

        # Check secret volume mount
        mounts = c0.get("volumeMounts", [])
        has_sec_mount = any(m.get("mountPath") == "/etc/secret" for m in mounts)
        if not has_sec_mount:
            return CheckResult("Secret Volume Mount", False, 4.5, 6.0, "Secret is not mounted at '/etc/secret'")

        phase = pod.get("status", {}).get("phase", "")
        if phase != "Running":
            return CheckResult("Pod running state", False, 5.0, 6.0, f"Pod phase is '{phase}' (expected Running)")

        return CheckResult("ConfigMaps & Secrets", True, 6.0, 6.0, "ConfigMap environment injected and Secret mounted at /etc/secret")

    scenarios.append(Scenario(
        id="cka-exam1-t11",
        number=11,
        title="ConfigMaps & Secrets",
        domain=Domain.WORKLOADS,
        weight=6.0,
        namespace="cka-config",
        description="Inject configuration data into a pod via environment variables and secret volume mounts.",
        requirements=[
            "Create ConfigMap 'app-config' in 'cka-config' with 'APP_COLOR=darkblue'.",
            "Create Secret 'app-secret' in 'cka-config' with 'DB_PASS=secret123'.",
            "Create Pod 'config-pod' in 'cka-config' (image: busybox, command: sleep 3600).",
            "Inject 'APP_COLOR' from the ConfigMap as an environment variable.",
            "Mount 'app-secret' as a volume at mountPath '/etc/secret'."
        ],
        hints=[
            "kubectl create cm app-config --from-literal=APP_COLOR=darkblue -n cka-config",
            "kubectl create secret generic app-secret --from-literal=DB_PASS=secret123 -n cka-config",
            "Under pod spec containers env: - name: APP_COLOR valueFrom: configMapKeyRef: name: app-config key: APP_COLOR",
            "Under pod spec volumes: - name: sec-vol secret: secretName: app-secret"
        ],
        checks=[
            VerificationCheck("ConfigMaps & Secrets", 6.0, check_task_11)
        ]
    ))

    # -------------------------------------------------------------
    # Task 12: Control Plane etcd Snapshot
    # -------------------------------------------------------------
    def check_task_12(auditor: Auditor) -> CheckResult:
        if not os.path.exists("/tmp/etcd-backup.db"):
            # Check inside minikube node
            code, out, _ = auditor.run_cmd("minikube ssh 'ls /tmp/etcd-backup.db 2>/dev/null'")
            if code != 0:
                return CheckResult("etcd snapshot file", False, 0.0, 7.0, "Snapshot file '/tmp/etcd-backup.db' not found on host or minikube node")

        if not os.path.exists("/tmp/etcd-status.txt"):
            code, out, _ = auditor.run_cmd("minikube ssh 'cat /tmp/etcd-status.txt 2>/dev/null'")
            if code != 0 or not out:
                return CheckResult("etcd status output", False, 3.5, 7.0, "Status file '/tmp/etcd-status.txt' not found or empty")

        return CheckResult("etcd Backup & Snapshot Verification", True, 7.0, 7.0, "etcd snapshot created and status verified")

    scenarios.append(Scenario(
        id="cka-exam1-t12",
        number=12,
        title="Control Plane etcd Snapshot",
        domain=Domain.CLUSTER_ARCH,
        weight=7.0,
        namespace=None,
        description="Create an encrypted snapshot backup of the cluster etcd database and verify the snapshot integrity.",
        requirements=[
            "Take an etcd snapshot of the running etcd instance on 'minikube'.",
            "Save the snapshot file to '/tmp/etcd-backup.db'.",
            "Run 'etcdctl snapshot status' on the backup and save the output to '/tmp/etcd-status.txt'."
        ],
        hints=[
            "minikube ssh",
            "ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 --cacert=/var/lib/minikube/certs/etcd/ca.crt --cert=/var/lib/minikube/certs/etcd/server.crt --key=/var/lib/minikube/certs/etcd/server.key snapshot save /tmp/etcd-backup.db",
            "ETCDCTL_API=3 etcdctl snapshot status /tmp/etcd-backup.db > /tmp/etcd-status.txt"
        ],
        checks=[
            VerificationCheck("etcd Snapshot Backup", 7.0, check_task_12)
        ]
    ))

    # -------------------------------------------------------------
    # Task 13: DaemonSet Deployment
    # -------------------------------------------------------------
    def check_task_13(auditor: Auditor) -> CheckResult:
        ds = auditor.get_resource_json("daemonset", "node-monitor", "cka-daemon")
        if not ds:
            return CheckResult("DaemonSet 'node-monitor'", False, 0.0, 6.0, "DaemonSet 'node-monitor' not found in 'cka-daemon'")

        desired = ds.get("status", {}).get("desiredNumberScheduled", 0)
        ready = ds.get("status", {}).get("numberReady", 0)

        if ready == 0 or ready < desired:
            return CheckResult("DaemonSet pods ready", False, 3.0, 6.0, f"Scheduled pods ready: {ready}/{desired}")

        res = ds.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [{}])[0].get("resources", {})
        req = res.get("requests", {})
        if req.get("cpu") != "50m" or req.get("memory") != "50Mi":
            return CheckResult("DaemonSet resource requests", False, 4.0, 6.0, f"Requests are {req}, expected cpu: 50m, memory: 50Mi")

        return CheckResult("DaemonSet Deployment", True, 6.0, 6.0, f"DaemonSet 'node-monitor' running across all {ready} cluster nodes")

    scenarios.append(Scenario(
        id="cka-exam1-t13",
        number=13,
        title="DaemonSet Deployment",
        domain=Domain.WORKLOADS,
        weight=6.0,
        namespace="cka-daemon",
        description="Deploy a monitoring DaemonSet that automatically schedules an instance on every node in the cluster.",
        requirements=[
            "Create a DaemonSet named 'node-monitor' in namespace 'cka-daemon'.",
            "Container name: 'monitor', image: 'busybox', command: 'sh', '-c', 'while true; do echo monitoring; sleep 10; done'.",
            "Configure resource requests: cpu: 50m, memory: 50Mi.",
            "Verify all DaemonSet pods are running."
        ],
        hints=[
            "Create deployment first with --dry-run=client -o yaml, change kind to DaemonSet, and remove spec.replicas and strategy"
        ],
        checks=[
            VerificationCheck("DaemonSet Deployment", 6.0, check_task_13)
        ]
    ))

    # -------------------------------------------------------------
    # Task 14: Services & NodePort
    # -------------------------------------------------------------
    def check_task_14(auditor: Auditor) -> CheckResult:
        deploy_ok, msg = auditor.check_deployment_ready("web-backend", "cka-services", expected_replicas=2)
        if not deploy_ok:
            return CheckResult("Deployment 'web-backend'", False, 0.0, 6.0, msg)

        svc = auditor.get_resource_json("service", "web-nodeport", "cka-services")
        if not svc:
            return CheckResult("Service 'web-nodeport'", False, 2.0, 6.0, "Service 'web-nodeport' not found in 'cka-services'")

        svc_type = svc.get("spec", {}).get("type", "")
        if svc_type != "NodePort":
            return CheckResult("Service type NodePort", False, 3.0, 6.0, f"Service type is '{svc_type}', expected 'NodePort'")

        ports = svc.get("spec", {}).get("ports", [])
        if not ports:
            return CheckResult("Service ports", False, 3.5, 6.0, "No ports defined on service")

        p0 = ports[0]
        if p0.get("port") != 80 or p0.get("nodePort") != 30080:
            return CheckResult("NodePort port mapping", False, 4.0, 6.0, f"Port: {p0.get('port')}, NodePort: {p0.get('nodePort')} (expected port: 80, nodePort: 30080)")

        return CheckResult("Services & NodePort", True, 6.0, 6.0, "Deployment web-backend exposed via NodePort service on port 30080")

    scenarios.append(Scenario(
        id="cka-exam1-t14",
        number=14,
        title="Services & NodePort",
        domain=Domain.NETWORKING,
        weight=6.0,
        namespace="cka-services",
        description="Expose a backend deployment to external traffic using a static NodePort service.",
        requirements=[
            "Create Deployment 'web-backend' in 'cka-services' with 2 replicas (image: nginx:alpine, containerPort: 80).",
            "Expose it with a Service named 'web-nodeport' of type NodePort.",
            "Configure port: 80, targetPort: 80, nodePort: 30080."
        ],
        hints=[
            "kubectl create deployment web-backend --image=nginx:alpine --replicas=2 -n cka-services",
            "kubectl create service nodeport web-backend --tcp=80:80 --node-port=30080 -n cka-services"
        ],
        checks=[
            VerificationCheck("NodePort Service", 6.0, check_task_14)
        ]
    ))

    # -------------------------------------------------------------
    # Task 15: InitContainers & Pod Lifecycle
    # -------------------------------------------------------------
    def check_task_15(auditor: Auditor) -> CheckResult:
        pod = auditor.get_resource_json("pod", "init-ready-pod", "cka-troubleshoot")
        if not pod:
            return CheckResult("Pod 'init-ready-pod'", False, 0.0, 7.0, "Pod 'init-ready-pod' not found in 'cka-troubleshoot'")

        init_c = pod.get("spec", {}).get("initContainers", [])
        if not init_c:
            return CheckResult("initContainers defined", False, 2.0, 7.0, "No initContainers configured in pod spec")

        if init_c[0].get("name") != "init-check":
            return CheckResult("initContainer name 'init-check'", False, 3.5, 7.0, f"initContainer name is '{init_c[0].get('name')}', expected 'init-check'")

        phase = pod.get("status", {}).get("phase", "")
        if phase != "Running":
            return CheckResult("Pod running state", False, 4.5, 7.0, f"Pod phase is '{phase}' (expected Running)")

        return CheckResult("InitContainers & Pod Lifecycle", True, 7.0, 7.0, "initContainer completed successfully and main container app-main is Running")

    scenarios.append(Scenario(
        id="cka-exam1-t15",
        number=15,
        title="InitContainers & Pod Lifecycle",
        domain=Domain.TROUBLESHOOTING,
        weight=7.0,
        namespace="cka-troubleshoot",
        description="Configure an init container to perform pre-flight checks before the main application container starts.",
        requirements=[
            "Create a pod named 'init-ready-pod' in namespace 'cka-troubleshoot'.",
            "Configure initContainer 'init-check' (image: busybox, command: 'sh', '-c', 'sleep 2').",
            "Configure main container 'app-main' (image: nginx:alpine, containerPort: 80).",
            "Ensure the pod successfully completes initialization and enters Running state."
        ],
        hints=[
            "Under pod spec: initContainers: - name: init-check image: busybox command: ['sh', '-c', 'sleep 2']",
            "containers: - name: app-main image: nginx:alpine ports: - containerPort: 80"
        ],
        checks=[
            VerificationCheck("InitContainer Pod Lifecycle", 7.0, check_task_15)
        ]
    ))

    return scenarios
