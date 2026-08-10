## 1.2.9

- Fix dynamic Kubernetes label-map rendering in the OpenShift Localnet role.
- Build the VM workload namespace labels as a rendered dictionary before passing them to `kubernetes.core.k8s`; Ansible does not template the quoted YAML mapping key in this definition path.
- Reuse the same rendered label map for the `ClusterUserDefinedNetwork` namespace selector.
- Add an assertion that prevents an unresolved Jinja expression from being sent as a Kubernetes label key.
- No install-time RHACM or phoenixNAP lifecycle resources are changed by this fix.

## v1.2.8

- Make `make deploy` lifecycle-idempotent after successful cluster installation.
- Stop declaring `ClusterDeployment.spec.installed: false`; Hive owns the one-way transition to `true`.
- Detect installed `ClusterDeployment` objects and skip AgentClusterInstall/InfraEnv/iPXE reconciliation on day-2 reruns.
- Skip phoenixNAP discovery/reboot/Agent approval for already-installed sites.
- Preserve existing phoenixNAP servers without requiring live spare SKU inventory during preflight or `make provision`.
- Make the install wait return immediately for clusters whose ClusterDeployment is already installed.

# Changelog

## 1.2.7

- Move the second phoenixNAP site from CHI to ASH because phoenixNAP custom `os: ipxe` provisioning is currently supported only in PHX, ASH and NLD.
- Add `phoenixnap.ipxe_supported_locations` and fail early in validation, availability, SKU selection and provisioning if a site is configured in an unsupported iPXE location.
- Keep dynamic per-site SKU selection under the strict `$0.30/hour` cap; ASH stock and pricing are selected live at runtime.
- Rename the second-site private network to `ocp-c1-ash-vm-l2` so an existing CHI network from earlier lab runs cannot be mistaken for the ASH VLAN.
- Update architecture and networking documentation from PHX/CHI to PHX/ASH.


## 1.2.6

- Rebuilds the RHACM `InfraEnv` after phoenixNAP NIC discovery so the per-host `NMStateConfig` selector is present from InfraEnv creation rather than relying on an in-place discovery-image refresh.
- Preserves the existing InfraEnv spec, including the direct RHCOS rootfs bypass, NTP sources, pull secret, SSH key, agent labels and iPXE mode.
- Verifies the recreated InfraEnv has a new Kubernetes UID and a new usable iPXE boot artifact before rebooting the phoenixNAP server.
- Uses the preferred DHCP NIC MAC explicitly on `bond0`, matching the configuration validated interactively on phoenixNAP.
- Removes the false-positive `createdTime` regeneration check that could pass when both old and new values were empty.

## v1.2.5

- Fix post-reboot Agent polling so an empty/transient Assisted Installer inventory annotation cannot crash the play with `from_json`.
- Poll structured `Agent.status.inventory.interfaces` and `status.validationsInfo.network` instead.
- Add sanitized diagnostics for bond presence, overlapping-subnet validation, and NTP validation when rediscovery does not become ready.


## 1.2.4

- Treat phoenixNAP iPXE dual NICs as a redundancy pair instead of dedicating NIC2 to the VM VLAN.
- After first RHACM Agent discovery, dynamically create an `NMStateConfig` for `bond0` using the discovered physical NIC MAC addresses.
- Use `802.3ad` LACP, clone the preferred physical NIC MAC for DHCP, regenerate the InfraEnv and reboot iPXE before Agent approval.
- Add explicit discovery NTP sources and wait for `non-overlapping-subnets` and `ntp-synced` validations to pass.
- Consume the site-local private VLAN as `bond0.<VLAN>` for the OpenShift Virtualization Localnet bridge.
- Surface sanitized phoenixNAP server-provisioning 400/409/422 validation errors instead of hiding the useful API message.
- Keep an already-provisioned auto-selected server type pinned on reruns to avoid unnecessary replacement when live stock changes.

## 1.2.3

- Work around RHACM/OpenTLC ingress truncation of the large RHCOS PXE rootfs.
- Read the matching OpenShift 4.22 x86_64 `rootFSUrl` from `AgentServiceConfig`.
- Append that direct URL to each `InfraEnv.spec.kernelArguments`; dracut honors the later value, while RHACM continues to provide the discovery initrd/kernel and agent configuration.
- Fail early if the hub does not expose a valid direct `rootFSUrl`.

## 1.2.2

- Fix phoenixNAP private-network creation when the account has no existing network in a location.
- Automatically set `locationDefault: true` for the first private network in a location and `false` for subsequent networks.
- Track newly-created networks during the play so multiple sites in one location remain safe.
- Preserve pure Layer-2 NO-CIDR (`force=true`) behavior for the VM transport VLAN.
- Provision servers with `force=true` and an explicit empty private-network IP list so the SNO host remains unnumbered on the VM VLAN.

## 1.2.1

- Create phoenixNAP VM transport networks as pure Layer-2 NO-CIDR private VLANs using `force=true`.
- Do not assign a private IP to the SNO host; the secondary NIC/VLAN remains unnumbered and is bridged to OVN Localnet for VMs.
- Preserve `private_l2.cidr` only as a guest VM addressing convention.
- Surface phoenixNAP private-network validation errors without exposing OAuth headers/tokens.

## 1.2.0

- Added live phoenixNAP SKU selection from Billing `/products` plus `/product-availability`.
- Enforced a strict `< $0.30/hour` per-server budget by default.
- Added hard 64 GB RAM / 6-core minimums and preferred 128 GB / 8-core sizing.
- Prefer the same qualifying SKU in PHX and CHI, with per-site fallback when a common SKU is unavailable.
- `make availability` now shows only budget- and sizing-qualified live candidates with price, RAM, cores and stock.
- Provision and explicit replacement workflows use the dynamic selection automatically.
- Selector output is sanitized and never prints the phoenixNAP bearer token.

## 1.1.1

- Add per-site phoenixNAP server type overrides.
- Add `make availability` to list currently available server SKUs in PHX and CHI.
- Preflight now validates each site's configured SKU independently and points to the availability command.
- Provision/replace roles use the site-specific SKU without silently choosing a fallback.

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

## 1.1.2
- Fixed `make availability` so it filters on live `minQuantityAvailable` / `availableQuantity`, rather than listing catalog SKUs with zero stock.
- Added a common-live-SKU intersection for PHX and CHI.
- Sanitized preflight availability assertions so failed checks no longer dump phoenixNAP OAuth Bearer tokens.
