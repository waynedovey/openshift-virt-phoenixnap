## 1.1.1

- Add per-site phoenixNAP server type overrides.
- Add `make availability` to list currently available server SKUs in PHX and CHI.
- Preflight now validates each site's configured SKU independently and points to the availability command.
- Provision/replace roles use the site-specific SKU without silently choosing a fallback.

# Changelog

## v1.1.0

- Move the hourly server default to `s1.c1.medium`.
- Add a private phoenixNAP Layer2 network per region and attach it during server provisioning.
- Use deterministic site-local private CIDRs: SW1 `10.60.10.0/24`, C1 `10.60.20.0/24`.
- Add explicit `make replace-servers` workflow because phoenixNAP server type is immutable.
- Install Kubernetes NMState independently of EVPN activation.
- Auto-detect a non-default-route Ethernet interface for the lab VM private VLAN, with a hard safety gate and documented phoenixNAP LACP caveat.
- Create an OVS bridge and secondary OVN-Kubernetes Localnet CUDN for OpenShift Virtualization VMs.
- Keep the site-local private L2 networks separate from the staged cross-site EVPN `10.50.50.0/24` network.

## v1.0.4

- Fix SNO `AgentClusterInstall` admission failure on current RHACM/MCE Assisted Service.
- Use `platformType: None` with `networking.userManagedNetworking: true` for provider-neutral PhoenixNAP/iPXE SNO installs.
- Keep `ClusterDeployment.spec.platform.agentBareMetal.agentSelector` unchanged; it is still required to bind discovered Agents to the deployment.
- This resolves the webhook conflict: `Can't set baremetal platform with user-managed-networking enabled`.

## v1.0.2

- Fix RHACM/Hive `ClusterDeployment` creation on ACM 2.16 / OpenShift 4.22 by adding the required `spec.platform.agentBareMetal.agentSelector`.
- Match the selector to the existing `InfraEnv.spec.agentLabels` (`cluster-name: <cluster>`), ensuring discovered Agents bind deterministically to the correct SNO deployment.
- Safe to rerun after the prior HTTP 422 failure; existing RHACM resources are reconciled idempotently.

## 1.0.1

- Run every Make target through `.venv/bin/ansible-playbook` instead of a global Ansible installation.
- Set localhost `ansible_python_interpreter` to `{{ ansible_playbook_python }}`.
- Make `bootstrap` verify the Kubernetes Python client is importable.
- Add `clean-venv` and macOS interpreter troubleshooting guidance.
