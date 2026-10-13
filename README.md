# ☸️ CKA Testing Agent

An automated, interactive testing and proctoring tool for the **Certified Kubernetes Administrator (CKA)** exam. Designed to connect to your live Kubernetes cluster (Minikube, Kind, or bare-metal), provide performance-based exam scenarios, enforce 2-hour timers, and execute deterministic automated audits with instant diagnostic feedback.

---

## 🚀 Quick Start

From the project directory:

```bash
cd /Users/jcalleja/code/ckaTestAgent

# Launch in Untimed Practice Mode (Default)
./run.sh

# Launch in 2-Hour Timed Exam Simulation Mode
./run.sh --timed

# Launch with custom timer duration (e.g. 60 minutes)
./run.sh --timed --minutes 60
```

---

## 🎮 Interactive Mode Commands

When running `./run.sh`, you will enter the interactive test runner:

| Command | Action |
|---|---|
| `audit` (or `check`) | Audit your work on the current task against the live cluster |
| `audit-all` | Grade all 15 exam tasks and output a complete scorecard |
| `next` / `prev` | Move to the next or previous task |
| `goto <N>` | Jump directly to Task N (e.g. `goto 5`) |
| `list` | View the full task list and current pass/fail progress |
| `hint` | Reveal helpful hints for the active task |
| `setup` | Automatically create the target namespace/prerequisites |
| `score` | View the overall scorecard and domain breakdown |
| `reset-cluster` | Clean up test namespaces, PVs, node taints & static pods |
| `help` | Show command reference |
| `quit` | Exit the test session |

---

## 🛠 Command Line Flags

```bash
# Untimed practice mode (default)
./run.sh

# Enable official 2-hour CKA timer
./run.sh --timed

# Run a full automated audit of all tasks and display scorecard
./run.sh --audit-all

# Reset minikube cluster to a clean vanilla state
./run.sh --reset
```

---

## 📋 Exam Coverage & Domain Breakdown

The test suite evaluates real Kubernetes resources across the official CNCF CKA exam curriculum:

1. **Cluster Architecture, Installation & Configuration (25%)**
   - RBAC (`ServiceAccount`, `Role`, `RoleBinding`, permission validation)
   - Node maintenance (`drain`, `cordon`, `uncordon`)
   - Static Pod creation & control-plane kubelet manifests
   - etcd snapshot backup & status verification
2. **Workloads & Scheduling (15%)**
   - Multi-container pods & shared volumes (`emptyDir`, log streaming sidecars)
   - Deployments, rolling updates, and scaling
   - Node affinity & nodeSelector targeting
   - ConfigMaps & Secrets (environment injection & volume mounts)
   - DaemonSet deployments
3. **Services & Networking (20%)**
   - NetworkPolicy ingress security & podSelector isolation
   - ClusterIP services & endpoints
   - Ingress routing (host & prefix path routing)
   - NodePort service exposure
4. **Storage (10%)**
   - PersistentVolumes (`hostPath`, access modes, capacity)
   - PersistentVolumeClaims & dynamic/manual binding
   - Pod persistent volume mounts
5. **Troubleshooting (30%)**
   - Resource requests, limits & CPU/memory metric queries
   - InitContainers & pod lifecycle sequencing
