## 1.4.9 - 2026-08-12

- Make RHACM release-image handling truly idempotent: existing `AgentClusterInstall.spec.imageSetRef.name` values are now treated as authoritative live install state and preserved per site.
- Skip `ClusterImageSet` catalog discovery entirely when existing AgentClusterInstall resources already provide the image-set references, so reruns no longer fail just because `oc` discovery temporarily cannot resolve `clusterimagesets`.
- For genuinely fresh installs, query the Hive collection through the raw Kubernetes REST endpoint (`/apis/hive.openshift.io/v1/clusterimagesets`) instead of relying on the client RESTMapper; raw create is used for deterministic self-heal when needed.
- Add `OPENSHIFT_CLUSTER_IMAGE_SET` as an explicit escape hatch for fresh hubs where the desired ClusterImageSet is known but catalog discovery/controller health is temporarily degraded.
- Preserve each site's existing imageSetRef independently, avoiding accidental OpenShift payload changes on reruns after the hub refreshes its ClusterImageSet catalog.

## 1.4.8

- Fix RHACM `ClusterImageSet` reconciliation on idempotent reruns. The Kubernetes Python dynamic client could query the resource and then fail to resolve the same cluster-scoped kind for `kubernetes.core.k8s`, causing `make deploy` to stop even though both phoenixNAP servers already existed.
- Use `oc get clusterimagesets.hive.openshift.io -o json` for deterministic discovery and `oc apply -f -` only when a 4.22 image set is genuinely absent.
- Keep the v1.4.7 server-capacity idempotency behavior: existing SW1/C1 servers bypass live-stock gating and are reused in place.

## 1.4.7 - 2026-08-12

- Make phoenixNAP capacity preflight genuinely idempotent: `make deploy` now inventories existing servers by configured hostname before consulting live SKU stock.
- Exclude already-deployed SW1/C1 servers from live availability gating, so consuming the last qualifying unit no longer makes the next `make deploy` fail.
- Support partial reruns: if one site exists and the other is missing, only the missing site must have live stock and only that site is dynamically selected.
- Apply the same behavior to static-SKU preflight and `make availability`, with clear `REUSE` versus `SELECT` reporting.
- Keep `make replace-servers` safe by forcing a fresh capacity check before any destructive replacement instead of reusing the idempotent deploy shortcut.
- Guard against silently adopting a same-hostname server from the wrong phoenixNAP location.

## 1.4.6 - 2026-08-12

- Fix C1 provisioning after phoenixNAP rejected native `os: ipxe` in CHI; default the second physical site to ASH while retaining the logical `c1` cluster identity and addressing.
- Add a native-iPXE location guard (`PHX`, `ASH`, `NLD`) to validate, availability, and preflight so a valid SERVER SKU can no longer produce a false-green result in an OS-incompatible location.
- Improve server-provisioning diagnostics to distinguish provider OS/location incompatibility from ordinary SKU stock races.
- Make self-managed EVPN transit labels location-neutral so the same PHX↔ASH lab fabric code can later be pointed at any confirmed iPXE-capable pair.

## 1.4.5 - 2026-08-11

- Refresh phoenixNAP OAuth credentials at the start of every SNO site because phoenixNAP bearer tokens are short-lived and SW1 Assisted Installer/LACP bootstrap can outlive the token before C1 provisioning begins.
- Refresh the phoenixNAP token again immediately before the post-InfraEnv LACP reboot, preventing long discovery/image-generation waits from causing a 401 on the next BMC action.
- Refactor token acquisition into `roles/pnap_auth/tasks/refresh.yml` so long-running API roles can safely renew credentials without duplicating OAuth logic.

## 1.4.4 - 2026-08-11

- Hardened Assisted Installer discovery polling against transient `kubernetes.core.k8s_info` results that do not contain a `resources` key.
- `Wait for RHACM Agent discovered by iPXE` now treats transient client/API failures as retryable instead of crashing while evaluating the `until` condition.
- Applied the same defensive polling to the Agent inventory wait, rebuilt InfraEnv image wait, and post-LACP Agent validation wait.
- Guarded Agent selection/approval facts with `default([])` so a transient discovery response cannot cause a secondary attribute error.
- No server destroy/rebuild is required for this fix; `make deploy` can be rerun against the current partially provisioned lab.

## 1.4.3 - 2026-08-11

- Fixed fresh `make deploy` racing the Assisted Installer Agent inventory publication. The Agent CR can exist before the `agent.agent-install.openshift.io/inventory` annotation is populated, which previously caused `from_json` to fail on an empty string.
- Select the newest discovered Agent, then re-read that exact Agent until the inventory annotation contains both `interfaces` and `routes` before parsing it.
- Refresh `discovered_agent` from the post-inventory API response instead of reusing the stale object from the initial discovery poll.
- Add a defensive inventory completeness assertion before deriving the LACP primary/secondary NICs.
- Add configurable `inventory_wait_seconds` and `inventory_wait_retries` defaults under `phoenixnap.ipxe_network`.

## 1.4.2

- Made `make destroy` idempotent across phoenixNAP asynchronous server lifecycle states.
- Treats an existing `deleting` server as an in-progress teardown instead of issuing a second deprovision request.
- Handles HTTP 409 from the deprovision action as a retryable lifecycle conflict, refreshes live server state, and retries for up to four minutes by default.
- Waits for each server to disappear from the BMC API before continuing, preventing teardown races with Cloudflare/RHACM/network cleanup.
- Fails with a clear sanitized message if a potentially billable server still cannot be deprovisioned after retries.

## 1.4.1 - 2026-08-10

- Fixed `make deploy` when the RHACM hub has no OpenShift 4.22 `ClusterImageSet`. The deployment now self-heals by creating `openshift-4.22.0-auto` with the documented `quay.io/openshift-release-dev/ocp-release:4.22.0-x86_64` default, overridable with `OPENSHIFT_RELEASE_IMAGE`.
- Fixed `make destroy` failing on `ManagedCluster` dynamic API discovery. Teardown now deletes the cluster-scoped `ManagedCluster` with `oc`, before deleting its namespace, and tolerates an absent ManagedCluster API while still surfacing real authorization/API errors.
- Improved destroy idempotency for partially destroyed labs.

## 1.4.0

- Add a default `self-managed-vxlan` PHX↔CHI lab fabric so `make deploy` can complete EVPN without assuming phoenixNAP standard BGP Peer Groups provide L2VPN EVPN.
- Build `NNCP/evpn-cross-site-transit` on both SNO nodes using the existing public `bond0` addresses, VXLAN VNI 4090, UDP/4790, MTU 1450 and a point-to-point `192.168.254.0/30` transit.
- Directly peer SW1 FRR-K8s ASN 65011 with C1 FRR-K8s ASN 65021 over that transit, with an idempotently generated shared BGP password.
- Bootstrap cross-site BGP in phases so both `FRRConfiguration` peers exist before either site waits for `Established`; this avoids a fresh-deploy deadlock.
- Create the `evpn-vm-net` primary EVPN CUDN and `evpn-vm-routes` automatically after the base BGP session is up.
- Verify MP-BGP L2VPN EVPN is established and that each cluster learns the remote OpenShift VTEP `/32` before deployment succeeds.
- Keep nested MTUs at 1500 (physical), 1450 (lab transit) and 1400 (OpenShift EVPN CUDN) so both VXLAN headers fit without requiring jumbo frames.
- Partition the shared `10.50.50.0/24` IPAM space by site using distinct gateways, infrastructure subnets and reserved subnets, preventing duplicate automatic VM IP allocation across the two independent clusters.
- Preserve `EVPN_FABRIC_MODE=external` for a real provider/DC EVPN fabric.

## 1.3.4

- Fix dynamic namespace label rendering in the OpenShift Localnet role. The previous YAML mapping key was passed literally as `{{ vm_l2.namespace_label_key }}`, causing Kubernetes to reject `vm-workloads` with HTTP 422.
- Build the namespace selector labels as an Ansible/Jinja dictionary before passing them to `metadata.labels` and the CUDN `namespaceSelector.matchLabels`.
- Keep the Localnet namespace and CUDN selector using the configured `digitaldovey.net/vm-l2=true` label while remaining idempotent on reruns.

## 1.3.3

- Make `make deploy` resilient when phoenixNAP rejects an optional day-2 private-network attachment on an already-installed SNO.
- Cross-check private-network membership from both the BMC Server API and the Networks API before attempting a repair, avoiding false negatives from one API view.
- Use the documented NO-CIDR day-2 request shape (`id` plus `ips: []` with `force=true`) and surface a sanitized API validation message instead of hiding the useful error.
- Treat private-L2 reconciliation as best-effort for existing servers by default so it cannot block the independent OpenShift Virtualization / EVPN platform stages. Newly provisioned servers still require the requested private network.
- Add `phoenixnap.fail_on_existing_private_network_reconcile_error` for users who want strict failure behavior.

## 1.3.2

- Attempt in-place private-network reconciliation for compatible existing phoenixNAP servers instead of requiring destructive replacement.
- Preserve existing server shape and `PUBLIC_AND_PRIVATE` mode during reruns.

## 1.3.1

- Fix idempotent `make deploy` reruns after SW1/C1 are already installed.
- Read and preserve the live Hive `ClusterDeployment.spec.installed` value instead of trying to force it back to `false`.
- Prevent the Hive admission error `cannot make uninstalled once installed`, allowing deployment to continue into the day-2 Virtualization, NMState and EVPN stages.

## 1.3.0

- Make `make deploy` enable OpenShift 4.22 EVPN platform prerequisites on both SNO clusters automatically.
- Enable FRR-K8s, OVN route advertisements, `routingViaHost: true` and `ipForwarding: Global` through the Cluster Network Operator.
- Wait for `FRRConfiguration`, `VTEP` and `RouteAdvertisements` CRDs and for an FRR-K8s pod before continuing.
- Create `evpn-vms` with the required `k8s.ovn.org/primary-user-defined-network` label at namespace creation time.
- Create and verify the NMState dummy VTEP interface and unmanaged `VTEP` CR even before the external EVPN fabric is available.
- Allow external EVPN peer settings to come from `.env`; rerunning the same `make deploy` completes `FRRConfiguration`, the EVPN CUDN and `RouteAdvertisements` when the fabric is confirmed.
- Keep phoenixNAP standard BGP peer groups separate from EVPN L2VPN fabric assumptions.

# Changelog

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

## 1.4.0

- Added a self-managed PHX<->CHI EVPN lab fabric to `make deploy`.
- Builds an NMState point-to-point VXLAN transit over the two SNO public IPs.
- Runs authenticated eBGP between SW1 ASN 65011 and C1 ASN 65021 over the private transit.
- Keeps OpenShift EVPN VTEPs private on the existing dummy interfaces.
- Makes the nested MTU explicit: 1500 outer, 1450 transit, 1400 EVPN CUDN.
- Verifies the BGP session, `EVPNTransportAccepted`, and RouteAdvertisements acceptance.
- Preserves `external` fabric mode for a real provider/DC EVPN fabric.
