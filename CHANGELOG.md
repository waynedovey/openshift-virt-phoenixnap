# Changelog

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
