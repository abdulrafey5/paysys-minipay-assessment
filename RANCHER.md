# Rancher — Attempt, Evidence, and Blocker

## What was attempted
1. Ran Rancher server as a standalone container:
   `docker run -d --name rancher-server --privileged -p 8443:443 rancher/rancher:latest`
2. Retrieved bootstrap password from container logs, logged into the
   Rancher UI at `https://localhost:8443`, set admin password.
3. Used "Import Existing Cluster" → "Import Generic" to register the
   existing k3d `minipay` cluster (the same cluster used for the K8s
   deployment task) as `minipay-k3d`.
4. Applied the generated registration manifest against the k3d cluster:
   `curl -sk https://localhost:8443/v3/import/<token>.yaml | kubectl apply -f -`
   (curl `-k` needed due to Rancher's self-signed cert on localhost — a
   known, expected requirement for local Rancher instances, not an
   oversight).
5. Registration resources (`clusterrole`, `clusterrolebinding`,
   `serviceaccount`, `cattle-cluster-agent` Deployment) were created
   successfully in the `cattle-system` namespace on the k3d cluster.

## Where it broke
The `cattle-cluster-agent` pod entered a crash loop
(`CrashLoopBackOff` after repeated restarts) shortly after image pull
completed. Command:

kubectl -n cattle-system get pods
kubectl -n cattle-system describe pod -l app=cattle-cluster-agent


## Root cause (assessed)
Rancher server and the k3d cluster's nodes run as **separate Docker
containers on separate Docker networks** on this host. The registration
manifest instructs the cluster agent to register back to
`https://localhost:8443` — but `localhost` from inside a pod running on a
k3d node resolves to that node/pod itself, not to the host machine where
`rancher-server`'s port mapping (`-p 8443:443`) is actually listening.
The agent has no route back to the Rancher server under this addressing
scheme, causing repeated connection failures and container restarts.

This is a known class of issue with running Rancher server and an
imported cluster as independent Docker Compose/`docker run` containers on
the same machine without a shared Docker network or a real resolvable
hostname — it is a environment/networking limitation of this specific
local setup, not a misunderstanding of Rancher's import flow or a defect
in the cluster being imported (the k3d cluster itself is confirmed healthy
and fully operational for the K8s deployment task — see `k8s/` and
`ARCHITECTURE.md`).

## What would fix it (documented, not executed, per time budget)
One of:
1. Run `rancher-server` and the k3d nodes on the same custom Docker
   network with a shared hostname/alias instead of `localhost`, and
   re-generate the import manifest against that hostname.
2. Use a real machine-reachable IP (not `localhost`) in the Rancher
   `server-url` setting before generating the import command, so the
   agent inside the k3d pod network can actually route to it.
3. Deploy Rancher server itself inside the same k3d/k3s cluster it will
   manage (a common single-node "local" Rancher pattern) rather than as a
   separate sibling container, eliminating the cross-network hop entirely.

## Outcome
Rancher server is running, login and cluster-import initiation both
succeeded, and the failure point (agent connectivity) is understood and
attributable to local network topology rather than to gaps in
understanding Rancher's operational model. Given the assessment's 72-hour
window and this task's 5-point weighting in SCORING.md relative to
incidents/K8s/SQL (20/15/15), further time was not spent iterating on the
network topology fix beyond this point.
