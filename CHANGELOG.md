## 1.4.38

- Fix the v1.4.37 loopback BGP canary regression: FRR-K8s cannot establish the authenticated hosting-leaf session to `127.0.0.1:1179` while sourcing it from the public VTEP address. Both leaves now use the hosting SNO public TCP/1179 endpoint, matching the authenticated session path already proven in v1.4.36.
- Fix the underlying asymmetric EVPN issue instead of changing the transport endpoint. The host-network route-server now enables FRR `bgp allow-martian-nexthop`, allowing EVPN NLRI from the hosting leaf whose preserved next-hop is the same public IP that is local on the route-server host.
- Keep `attribute-unchanged next-hop`, TCP-MD5 authentication, `/32` dynamic-listen restrictions, and the stronger v1.4.37 Type-3/Remote-VTEP validation gates.
- Align canonical peers, canaries, status, and legacy-retirement verification on the single NAT-free public TCP/1179 route-server endpoint.

# 1.4.37

- Fix asymmetric EVPN propagation discovered after the authenticated v1.4.36 cutover: SW1 received C1 EVPN routes, but the embedded route server accepted zero EVPN prefixes from SW1, leaving C1 with no remote Type-2/Type-3 routes and `Remote VTEPs=0`.
- Keep the embedded FRR route server on `hostNetwork: true`, but make the hosting SNO peer to `127.0.0.1:1179` while the remote SNO continues to peer to the hosting public IP. Both sessions remain NAT-free and TCP-MD5 authenticated, while avoiding a same-source/same-destination public-IP BGP session on the hosting SNO.
- Use the same loopback/public endpoint split in migration canaries, canonical FRRConfiguration peers, verification, and legacy-router retirement checks.
- Strengthen final EVPN verification: embedded-router mode now requires the remote Type-3 VTEP and at least one remote VTEP in VNI 5050 on both SNOs before migration is considered healthy.
- Update status and documentation to show the local loopback BGP endpoint separately from the remote public listener.

# 1.4.36

- Keep BGP authentication enabled by default while removing Kubernetes NAT from the embedded route-server BGP path.
- Run the embedded FRR route-server explicitly with `hostNetwork: true`; both SW1 and C1 now dial the hosting SNO public IP on TCP/1179.
- Retain the ClusterIP Service only for health/discovery; it is no longer used as a BGP peer endpoint.
- Restrict dynamic FRR listen ranges to the two known public VTEP /32 addresses instead of `0.0.0.0/0`.
- Do not use plain TCP reachability probes against an MD5-protected BGP listener; authenticated canaries are the end-to-end reachability gate.
- Fix legacy retirement verification so both sites validate the NAT-free public route-server endpoint.
- This follows live proof that both canaries establish with authentication disabled while the ClusterIP path fails with TCP-MD5 enabled.

## 1.4.35

- Fix the v1.4.34 regression where moving the embedded FRR route server to `hostNetwork` made the local loopback probe succeed but caused the remote SNO public TCP/1179 probe to fail. Live 1.4.33 testing had already proved the normal-pod `hostPort` path is reachable from the remote SNO.
- Restore normal pod networking plus `hostPort: 1179`: the hosting SNO uses the ClusterIP Service and the remote SNO uses the hosting public IP.
- Fix the original local canary problem by changing the embedded FRR listener from fixed source-IP neighbors to a password-protected dynamic eBGP peer-group (`bgp listen range`). This tolerates Kubernetes Service/hostPort transport address translation while FRR-K8s still binds each session to its public VTEP `sourceaddress`.
- Preserve EVPN next hops with `attribute-unchanged next-hop`, keep VNI 5050 VXLAN direct between the public SNO VTEPs, and retain the non-disruptive canary before canonical peer replacement.
- Add loop labels to the SNO probe tasks so Ansible no longer dumps the entire Node object into normal migration logs.

## 1.4.34

- Fix the embedded EVPN BGP canary failure where SW1 dialed the route-server through a ClusterIP (`172.30.x.x:1179`) while binding the session to the public VTEP source address. The TCP health probe succeeded, but the Service path can translate the connection before it reaches bgpd, so the passive route-server neighbor does not reliably see the configured public peer identity.
- Run the embedded FRR route-server with `hostNetwork: true` on the existing SW1 SNO and use a NAT-free control-plane path: the hosting FRR-K8s speaker dials `127.0.0.1:1179`, while the remote speaker dials the hosting SNO public IP on TCP/1179. Both continue to use their public VTEP addresses as `sourceaddress`.
- Keep the ClusterIP Service only as an optional discovery/health object; it is no longer used as a BGP peer endpoint. Remove the now-redundant `hostPort` mapping because the host-networked bgpd listens directly on TCP/1179.
- Preserve the migration guard: the old third-server peer is not replaced until both non-disruptive canaries establish. Improve the canary failure message with the final BGP state/reset summary.
- Keep VXLAN VNI 5050 direct between the two public SNO VTEPs; the embedded route-server remains control-plane only.

## 1.4.33

- Fix embedded EVPN migration failing while reading the live FRRConfiguration OpenAPI schema with `object of type 'method' has no attribute 'properties'`.
- Use explicit bracket notation for nested CRD schema map keys, especially the literal OpenAPI `items` keys, so Jinja does not resolve them as Python `dict.items` methods.
- Keep the v1.4.32 architecture unchanged: the embedded AS65000 FRR route-server remains on the existing SW1 SNO, FRR-K8s uses `neighbor.port` + `neighbor.sourceaddress`, TCP/1179 carries BGP control-plane traffic, and VXLAN VNI 5050 stays direct between the two public SNO VTEPs.
- Preserve the guarded migration order and do not retire the legacy third server until embedded BGP and EVPN validation succeeds.

## 1.4.32

- Restore the embedded no-third-server EVPN route-server design after live testing proved OpenShift FRR-K8s on both SNOs has no passive TCP/179 listener, so direct leaf-to-leaf BGP cannot establish.
- Fix the FRRConfiguration capability check by reading the served CRD OpenAPI schema directly through Kubernetes instead of using `oc explain`, which returned false negatives for nested `neighbors.port` / `neighbors.sourceaddress` fields.
- Require both `neighbor.port` and `neighbor.sourceaddress` before migration, matching the live OpenShift 4.22 CRDs verified on SW1 and C1.
- Run the embedded FRR route server as a normal pod on the existing SW1 SNO, exposed locally by a ClusterIP Service and remotely by hostPort TCP/1179. Both FRR-K8s speakers explicitly source their sessions from their own public VTEP addresses.
- Keep the VXLAN VNI 5050 data path direct between the two SNO public VTEPs; the embedded FRR process remains control-plane only.
- Preserve the fail-safe migration order: deploy and probe TCP/1179, establish non-disruptive BGP canaries, replace the canonical peers, verify EVPN/remote VTEPs, then allow legacy `evpn-fr` retirement.
- Normalize stale `EVPN_FABRIC_MODE=direct-peering` and `fabric-router` values to `embedded-router`.

## 1.4.31

- Temporarily tested direct SNO-to-SNO BGP on TCP/179. The guarded live migration proved both OpenShift FRR-K8s daemons were active-only clients with no passive TCP/179 listener, so neither leaf could accept the other's session. The safety gate left the working legacy fabric untouched. This design is superseded by 1.4.32.

## 1.4.30

- Fix embedded EVPN migration on OpenShift 4.22 clusters whose live FRRConfiguration CRD does not expose `neighbor.sourceaddress`. The route-server pod now uses `hostNetwork`; the hosting FRR-K8s speaker peers to `127.0.0.1:1179` and the remote speaker peers to the hosting SNO public IP on TCP/1179.
- Require only the documented `neighbor.port` field, retain the non-disruptive BGP canary, and keep the legacy third-server fabric untouched until both embedded sessions establish.
- Run the embedded FRR route server in passive-neighbor mode so OpenShift FRR-K8s remains the active BGP client on both sites.

# 1.4.29

- Raise the default phoenixNAP automatic-selection ceiling from a strict `< $0.30/hour` to a strict `< $0.40/hour` per SNO.
- Keep the v1.4.28 all-region capacity search: PHX (US SW1), ASH (US E1), and NLD (EU W1) are all checked before capacity selection fails.
- Preserve the existing hard requirements of at least 64 GB RAM, 6 CPU cores, 2 physical storage devices, and two distinct physical regions.
- Keep live hourly-rate reporting so candidates above/below the `$0.40/hour` ceiling are visible during `make availability` and `make preflight`.

# 1.4.28

- Treat PHX (US SW1), ASH (US E1), and NLD (EU W1) as a live capacity pool for automatic phoenixNAP placement instead of hard-failing when one configured region is out of stock.
- Require the two logical SNO sites to land in at least two distinct physical regions. Existing live SNO placement is preserved and counts toward that requirement.
- Query every supported region before failing and print live HOURLY SKU prices, stock, RAM/CPU and disk counts, including hardware-minimum candidates that are above the configured hourly cap.
- Dynamically adopt the selected physical region for downstream private-network and server provisioning while keeping logical site names (`sw1`, `c1`) stable.

# 1.4.27

- Make the 1.4.26 no-third-server migration safe for existing working trees that still export `EVPN_FABRIC_MODE=fabric-router`; the legacy value is now normalized to `embedded-router` instead of failing validation.
- Fix idempotent phoenixNAP preflight capacity detection. Existing servers are still matched by configured hostname first, but if phoenixNAP reports a different hostname the role now recovers the server by the repository-owned `artifacts/servers/<site>.yml` `server_id`, only when that ID is present in the current live `/servers` response. This prevents a healthy existing SW1/C1 from being mistaken for missing capacity.
- Add sanitized diagnostics showing which live server ID/hostname is being reused during preflight.

# Changelog

## 1.4.26

- Remove provisioning of the third phoenixNAP `evpn-fr` server from the active design. The default is now `EVPN_FABRIC_MODE=embedded-router`.
- Add an embedded FRR EVPN route-server Deployment on an existing SNO (SW1 by default). The hosting FRR-K8s leaf peers through a ClusterIP Service while the remote leaf peers to TCP/1179 on the hosting SNO public IP; VXLAN UDP/4789 remains direct between the public OpenShift VTEPs.
- Preserve each leaf public VTEP as the BGP source with FRR-K8s `neighbor.sourceaddress` and use the supported custom neighbor `port`, avoiding direct FRR-K8s-to-FRR-K8s passive peering.
- Add fail-safe `make evpn-migrate`: deploy/probe the embedded listener before peer changes, require base BGP + L2VPN EVPN + remote Type-3/VTEP verification, and only then deprovision a repository-owned legacy `evpn-fr` server.
- Add `make evpn-router` and `make evpn-retire-legacy`. Remove the old third-server provisioning playbook/role so a current deployment cannot accidentally create another billable EVPN server.
- Keep the legacy fabric-router teardown helper only for ownership-verified cleanup of older deployments.
- Keep the v1.4.25 deterministic proof VMs and `cloud-user`/SSH login behavior unchanged.

# 1.4.25 - 2026-08-17

- Fix RHEL 9 EVPN proof VM administration by explicitly configuring the `cloud-user` password, enabling SSH password authentication, installing the repository public key in NoCloud user-data, and enabling `sshd` during first boot.
- Default the disposable lab console password to `redhat`; override it with `EVPN_TEST_VM_PASSWORD` before `make test-vms`.
- Add a proof-VM `bootstrap_revision` annotation and safe recreation logic. When first-boot/cloud-init behavior changes, `make test-vms` now deletes and recreates only the disposable proof VM and root DataVolume so the new cloud-init runs; EVPN CUDN, VTEP, BGP, and fabric-router resources are left untouched.
- Keep the deterministic EVPN addresses (`10.50.50.50` / `10.50.50.150`) and MACs unchanged.

# 1.4.24 - 2026-08-17

- Fix EVPN proof VM admission with the common `rhel.9` VirtualMachine preference by expressing the requested vCPU count as sockets, matching the preference CPU topology.
- This resolves `insufficient CPU resources of 0 vCPU ... preference requires 1 vCPU provided as sockets` while retaining the RHEL 9 preference and the existing 2-vCPU lab size.

# 1.4.23 - 2026-08-17

- Correct the 1.4.22 primary-CUDN regression that removed `subnets`/IPAM and caused the API 422 `Subnets is required with ipam.mode is Enabled or unset`. OpenShift 4.22 primary Layer2 CUDNs keep OVN IPAM enabled and require a subnet.
- Restore `10.50.50.0/24`, `ipam.mode: Enabled`, and `ipam.lifecycle: Persistent` on the EVPN CUDN. Preserve the site-specific gateway and infrastructure ranges.
- Make the requested proof addresses deterministic without conflicting independent cluster allocators: SW1 reserves every workload address except `10.50.50.50`; C1 reserves every workload address except `10.50.50.150`.
- Change the proof VMs to obtain the primary-UDN address with DHCP and verify that KubeVirt reports exactly the expected persistent address before declaring the VM ready.
- Harden immutable CUDN reconciliation so a missing CUDN is recreated, an old/mismatched empty CUDN is safely replaced, and an already-correct CUDN remains idempotent after proof VMs exist.
- Keep the 1.4.22 fabric-router `ip nht resolve-via-default` and EVPN next-hop preservation fixes unchanged.

# 1.4.22 - 2026-08-17

- Fix the EVPN proof path end-to-end: `make deploy` now invokes `playbooks/08a_test_vms.yml`, and `make test-vms` is available for a focused rerun.
- Replace per-cluster OVN IPAM on the stretched Layer-2 CUDN with manual static addressing. Existing legacy `evpn-vm-net` objects are detected and safely recreated only when the `evpn-vms` namespace contains no VMs/VMIs.
- Create dedicated EVPN proof VMs `rhel9-sw1` (`10.50.50.50/24`, MAC `02:50:50:00:00:11`) and `rhel9-c1` (`10.50.50.150/24`, MAC `02:50:50:00:00:21`) on the primary EVPN CUDN with KubeVirt `l2bridge` binding.
- Fix the stale proof-VM gate that referenced nonexistent `evpn.apply`; fabric-router and self-managed modes can now create proof VMs directly, while external mode still requires `EVPN_FABRIC_CONFIRMED=true`.
- Persist `ip nht resolve-via-default` in the auto-provisioned FRR fabric-router configuration so public OpenShift VTEP nexthops remain valid when reached through the default route. The fabric-router role now also reconciles and saves these critical FRR settings over SSH on an already-owned router, so an existing lab does not require a rebuild. The EVPN neighbor configuration continues to preserve the original next hop so VXLAN UDP/4789 stays direct between SNOs.
- Include the 1.4.21 FRR cleanup ordering/CRD-awareness fix so this patch applies cleanly to the unmodified 1.4.20 repository.

# 1.4.21 - 2026-08-17

- Fix `make deploy` failing in fabric-router EVPN cleanup with `Failed to find exact match for frrk8s.metallb.io/v1beta1.FRRConfiguration` on clusters where the FRR routing capability has not yet created the `FRRConfiguration` CRD.
- Reorder EVPN platform prerequisite reconciliation ahead of legacy FRR cleanup so OpenShift can enable FRR/route advertisements and publish the required CRDs before custom resources are addressed.
- Make legacy diagnostic cleanup explicitly CRD-aware: `direct-evpn-fabric` and `pnap-bgp-test` are deleted only when `frrconfigurations.frrk8s.metallb.io` is present.

# 1.4.20 - 2026-08-13

- Require at least two physical storage devices for dynamically selected SNO server SKUs when LVMS is enabled, preventing one-disk shapes such as the current C1 server from being selected for new deployments.
- Parse phoenixNAP server/product storage descriptions conservatively and expose `storageDeviceCount` in sanitized selector output and availability reports.
- Validate reusable existing phoenixNAP servers against the same disk-count policy before OpenShift/LVMS stages. A one-disk server now fails early with an explicit replacement instruction instead of reaching `make storage` and reporting zero candidates.
- Add `make replace-site SITE=<sw1|c1>` so an incompatible site can be replaced without forcing a fresh SKU decision or destructive replacement for the healthy peer site. For installed SNOs, the workflow verifies old RHACM install state is fully removed before deprovisioning hardware.
- Keep LVMS disk discovery fail-closed: the OpenShift installation disk is never wiped or shared day-2, and `forceWipeDevicesAndDestroyAllData` remains disabled.
- Add unit tests for storage-description parsing and one-disk SKU rejection.

# 1.4.19

- Fix full deployment so `playbooks/06a_lvm_storage.yml` runs on both `sw1` and `c1` before OpenShift Virtualization.
- Add the missing OpenShift 4.22 `lvm_storage` configuration using `lvms-operator` on `stable-4.22`.
- Add `make storage` for idempotent day-2 LVMS reconciliation on existing clusters.
- Use the dedicated empty secondary NVMe only; keep destructive disk wiping disabled.
- Configure `lvms-vg1` as the cluster default and OpenShift Virtualization default StorageClass.
- Document why an exact 300 GB RHCOS boot partition cannot be created non-destructively on the already-installed Assisted Installer clusters.

## 1.4.18 - 2026-08-13

- Fix EVPN fabric-router auto-provisioning failing at `Select cheapest live hourly SKU for missing EVPN fabric router` with a censored non-zero return code.
- Resolve `scripts/select_pnap_sku.py` from `role_path` instead of relying on the process working directory, matching the existing `pnap_select_sku` role and making `make deploy` safe regardless of where Ansible executes the command task.
- Validate that the selector script exists and is readable before capacity selection.
- Run the credential-bearing selector command with `failed_when: false` and `no_log: true`, then emit a sanitized assertion for command-execution failures so future path/interpreter errors report the return code and resolved script path without exposing the phoenixNAP OAuth token.
- No SNO, RHACM, private-network, or OpenShift rebuild is required. Replace the repository files and rerun `make deploy`; existing resources are reused idempotently.

## 1.4.17 - 2026-08-12

- Replace the default nested `self-managed-vxlan` fabric with an external FRR **eBGP EVPN fabric-router** design. Live testing proved the phoenixNAP BGP Peer Groups establish IPv4 BGP but return `NoNeg` for L2VPN EVPN, while OpenShift FRR-K8s runs `bgpd ... -p 0` and therefore cannot accept a direct SW1↔C1 TCP/179 peering.
- Use the existing SNO public IPv4 addresses as the unmanaged OpenShift VTEPs in fabric-router mode (`131.153.236.243/32` on SW1 and `103.67.202.133/32` on C1 in the current lab), eliminating the private dummy VTEP dependency for this single-fabric-peer topology.
- Keep the EVPN data plane direct PHX↔ASH on OpenShift's fixed VXLAN UDP/4789 / VNI5050 path. Live packet tests confirmed UDP/4789 and TCP/179 reachability in both directions between the public SNO addresses.
- Add an optional phoenixNAP fabric-router provisioning role and `make evpn-fabric-router`. Auto-provisioning is **off by default** (`EVPN_FR_AUTO_PROVISION=false`) because enabling it creates a third billable hourly server; an externally managed fabric router can instead be supplied with `EVPN_FR_ADDRESS` and `EVPN_FR_BGP_PASSWORD`.
- Configure the fabric router as AS65000 with normal eBGP re-advertisement. AS65000 is prepended to forwarded routes (so OpenShift FRR-K8s default first-AS enforcement remains valid), while `attribute-unchanged next-hop` preserves the originating public VTEP for direct VXLAN forwarding.
- Clean up the temporary `direct-evpn-fabric` / `pnap-bgp-test` diagnostics and reconcile the legacy `evpn-transit0` interface absent when fabric-router mode is selected.
- Harden EVPN verification: require base BGP Established, reject L2VPN `NoNeg`/`Connect`/`Active`, and verify direct host routing to the remote public VTEP in fabric-router mode.
- Extend `make destroy` to verify and deprovision a repository-owned auto-provisioned fabric router recorded in `artifacts/evpn/fabric-router.yml`, preventing a third hourly server from being left billable.
- Keep `external` provider-fabric mode and the old `self-managed-vxlan` mode available; the latter is now explicitly legacy/diagnostic only.

## 1.4.16

- Revert the self-managed outer carrier to UDP/4790. v1.4.15 incorrectly moved the carrier onto UDP/4789, which is the OpenShift EVPN data-plane port and caused the live `evpn-cross-site-transit` NNCP to become `Degraded/FailedToConfigure`.
- Reinstate validation that rejects UDP/4789 for the outer lab carrier so the transport cannot collide with the OpenShift EVPN VXLAN endpoint.
- Add per-node NMState enactment collection when the transit NNCP fails instead of ending with only `Unknown error`.
- Add a host-network ping probe across `192.168.254.0/30` before waiting on BGP. A failed probe now identifies the outer VXLAN carrier/provider path as the blocker; BGP is only tested after the tunnel actually carries IP traffic.
- Add `EVPN_BGP_AUTH_ENABLED` (default `true`) as a controlled diagnostic override without weakening the default configuration.

## 1.4.15 - 2026-08-12

- Fix the remaining self-managed EVPN underlay stall where FRR can resolve the remote `192.168.254.x/32` route but BGP stays `Active` / `Waiting for peer OPEN`.
- Move the lab carrier VXLAN from the non-standard UDP/4790 default to standard UDP/4789. OpenShift 4.22 EVPN itself uses UDP/4789 and does not support a custom EVPN VXLAN destination port, so using the same standard port with a separate carrier VNI (4090) removes an unnecessary non-standard firewall/provider-path dependency.
- Make the carrier destination port overrideable with `EVPN_TRANSIT_UDP_PORT`, defaulting to `4789`.
- Keep the carrier and OpenShift EVPN isolated by VNI (`4090` for the lab carrier, `5050` for the OpenShift EVPN network); the shared UDP destination port is intentional.
- Improve the BGP timeout diagnostic to distinguish route presence from actual VXLAN dataplane reachability.
- No server, RHACM, private-network, or cluster rebuild is required; rerun `make deploy` to reconcile the existing `evpn-cross-site-transit` NNCPs in place.

## 1.4.14 - 2026-08-12

- Fix the self-managed EVPN underlay stopping in FRR `BGP state = Active` with `No path to specified Neighbor`.
- Add an explicit `/32` route to the opposite `192.168.254.x` transit endpoint through `evpn-transit0` in routing table 254, so FRR-K8s has deterministic peer reachability even when NetworkManager's implicit connected route is not visible as expected.
- Enable `ebgpMultiHop` for the self-managed VXLAN BGP neighbor only; external/provider EVPN mode is unchanged.
- Verify the peer route from FRR before waiting for BGP, and replace the previous `Unknown error` timeout with a concise final BGP-state/reset diagnostic.
- No phoenixNAP server, RHACM, or cluster rebuild is required; rerun `make deploy`.

## 1.4.13 - 2026-08-12

- Hardened phoenixNAP BGP peer-group readiness polling against transient `uri` results that do not contain a JSON body.
- Refreshes the phoenixNAP OAuth token immediately before each BGP peer-group readiness wait.
- The BGP READY loop now safely retries missing/failed HTTP responses instead of crashing while evaluating `bgp_group_ready.json.status`.
- Added a sanitized post-poll assertion that reports the final HTTP/API state without exposing OAuth headers.
- No server, RHACM, private-network, or OpenShift rebuild is required; rerun `make deploy`.

## 1.4.12 - 2026-08-12

- Fixed OpenShift 4.22 FRR-K8s `FRRConfiguration` BGP authentication schema: `neighbors[].passwordSecret` is now emitted as a SecretReference object with `name`, not as a bare string.
- This resolves the API 422 `passwordSecret ... must be of type object` failure when creating `FRRConfiguration/evpn-fabric`.
- Keeps the existing `kubernetes.io/basic-auth` secret in `openshift-frr-k8s`; no RHACM or phoenixNAP resources are recreated.

## 1.4.11 - 2026-08-12

- Carry forward the v1.4.10 idempotent AgentClusterInstall fix unchanged.
- Add an explicit repository version banner to `make deploy` and `make bootstrap`, plus `make version`, so stale working-tree copies are immediately obvious.
- Add a first-task version report in `playbooks/00_validate.yml`. The reported failure logs for the previous run contained v1.4.9 task names, proving the v1.4.10 files had not actually replaced the active checkout.
- Document safe extraction/update using `rsync -a` so hidden files and revised role files are copied consistently without deleting local `.env` or `artifacts/`.

## 1.4.10 - 2026-08-12

- Fix idempotent RHACM reruns when existing `AgentClusterInstall` objects are present but their live API representation does not expose `spec.imageSetRef`. Existing ACI presence is now authoritative; catalog discovery is no longer triggered just because `imageSetRef` is absent.
- Skip `ClusterImageSet` catalog access entirely when every configured site already has an AgentClusterInstall. This allows reruns to continue even when the hub does not currently serve `/apis/hive.openshift.io/v1/clusterimagesets`.
- Preserve existing AgentClusterInstall resources exactly instead of reapplying install-spec fields on every `make deploy`; only a genuinely missing ACI is created and therefore requires an effective ClusterImageSet.
- Keep partial-rebuild safety: if one site has an ACI and another does not, only the missing site requires `OPENSHIFT_CLUSTER_IMAGE_SET` or a healthy ClusterImageSet catalog.

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
