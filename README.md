# phoenixNAP OpenShift 4.22 Two-Site EVPN Lab


> **Updating an existing checkout:** unpack the new ZIP beside the checkout, then run `rsync -a openshift-virt-phoenixnap-main/ ./` and verify with `make version`. Do not use a stale extracted directory from an earlier revision.

GitHub-ready Ansible automation for a two-region OpenShift Virtualization lab on phoenixNAP Bare Metal Cloud.

### Dynamic server selection under $0.40/hour

The lab now selects the server shape at runtime instead of hard-coding a SKU. It combines
phoenixNAP's live product catalog, hourly pricing and live stock for PHX and ASH.

Default policy:

```yaml
phoenixnap:
  pricing_model: HOURLY
  auto_select:
    enabled: true
    max_hourly_price: 0.40   # strict: selected price must be < $0.40/h
    min_ram_gb: 64
    min_cores: 6
    min_storage_devices: 2  # boot disk + dedicated LVMS disk
    preferred_ram_gb: 128
    preferred_cores: 8
    prefer_common_sku: true
    require_common_sku: false
```

Selection order is deliberately cost-aware:

1. Must have live stock in the target region.
2. Must use a `HOURLY` / `HOUR` pricing plan strictly below the configured cap.
3. Must satisfy the hard RAM/core minimums.
4. Must expose at least two physical storage devices when LVMS is enabled.
5. Prefer a SKU closest to the preferred 128 GB / 8-core lab target.
6. Among equally suitable shapes, choose the lower hourly price.
7. Prefer the same SKU in PHX and ASH. If no common SKU qualifies, select independently per site unless `require_common_sku: true`.

Run:

```bash
make availability
make preflight
```

The output shows the top qualifying choices and the selected SKU/price for each site. A concrete
SKU can still be used by setting `phoenixnap.auto_select.enabled: false` and configuring
`sites.<site>.server_type`.

## What it builds

- **PHX / US SW1**: `sw1.digitaldovey.net`
- **ASH / US C1**: `c1.digitaldovey.net`

> **phoenixNAP native-iPXE location note (v1.4.6):** The live BMC provisioning API
> rejected `os: ipxe` in CHI and reported native iPXE support in PHX, ASH, and NLD.
> The default second site is therefore ASH. The logical cluster remains `c1` with the same
> DNS name, ASN, VTEP, and OpenShift networks. Exact CHI placement requires a different
> bootstrap path (for example a RAM-resident Ubuntu/kexec workflow) and is intentionally
> not guessed by this production-style path.
- dynamically selected phoenixNAP server below **$0.40/hour per site**, billed **HOURLY**
- RHACM Host Inventory / Assisted Installer `InfraEnv` per site
- phoenixNAP iPXE boot directly from the RHACM InfraEnv boot artifact
- OpenShift Container Platform **4.22** Single Node OpenShift at each site
- Cloudflare DNS for API, API-int and wildcard ingress
- OpenShift Virtualization on each SNO
- phoenixNAP dual-NIC LACP bond for the SNO native/public network
- phoenixNAP private Layer-2 VLAN in each region for OpenShift Virtualization VMs
- secondary OVN-Kubernetes Localnet CUDN backed by that private VLAN
- optional phoenixNAP IPv4 BGP Peer Group creation (disabled by default; not used for EVPN)
- complete two-site OpenShift 4.22 EVPN lab using an embedded FRR route-server pod on an existing SNO

> **RHACM release-image self-heal:** if the hub does not currently contain an OpenShift 4.22 `ClusterImageSet`, `make deploy` creates `openshift-4.22.0-auto` automatically. Set `OPENSHIFT_RELEASE_IMAGE` only if you need a mirrored registry or a different 4.22.z payload.

- embedded FRR eBGP/MP-BGP EVPN control plane with **no third phoenixNAP server**
- explicit, guarded teardown of hourly resources

## Deliberate safety decisions

### 1. Server shape is selected dynamically within a hard hourly budget

The project selects a live SKU under the configured hourly cap and sizing policy immediately before
provisioning. Existing incompatible servers are never silently resized or destroyed. Use the explicit
replacement workflow when you intentionally want the selected shape to replace an existing server:

```bash
make private-networks
make replace-site SITE=c1   # replace only the incompatible site
make deploy
```

`make deploy` is safe to rerun against already-installed SW1/C1 clusters. The RHACM/Hive stage preserves an existing `ClusterDeployment.spec.installed: true` value rather than attempting to reset the cluster to an uninstalled state.

For an existing compatible phoenixNAP server, `make deploy` also reconciles a missing site-local private Layer-2 network membership in place through the BMC API instead of incorrectly asking for a server replacement. It never removes an existing private-network membership automatically.

### 2. Private Layer2 is site-local, not a PHX-to-ASH VLAN stretch

Each SNO gets public management/iPXE connectivity plus a phoenixNAP private VLAN for VMs.
The OpenShift side maps that VLAN into a secondary OVN Localnet CUDN. PHX and ASH private
networks are separate L2 broadcast domains; the EVPN layer remains responsible for the shared
`10.50.50.0/24` cross-site VM subnet. See `docs/private-l2.md`.

### 3. `make deploy` builds EVPN without a third phoenixNAP server

Live testing showed that phoenixNAP BGP Peer Groups negotiate ordinary IPv4 BGP but not the required L2VPN EVPN AFI/SAFI. OpenShift FRR-K8s also operates as an active BGP client rather than providing the passive listener required for a simple two-leaf direct session.

Version 1.4.38 defaults to `EVPN_FABRIC_MODE=embedded-router` and transparently maps the removed legacy values `fabric-router` and `direct-peering` to `embedded-router`. A small FRR route-server pod (AS65000) runs with host networking on the existing hosting SNO. Both FRR-K8s speakers peer to the hosting SNO public IP on TCP/1179 and explicitly source BGP from their own public VTEP addresses, keeping TCP-MD5 NAT-free. Because the hosting leaf advertises an EVPN next-hop that is also local to the host-network route-server, the embedded FRR enables `bgp allow-martian-nexthop`; this permits that control-plane route while `attribute-unchanged next-hop` preserves the originating VTEP for the opposite leaf. The route server accepts dynamic eBGP clients only from the two known public VTEP /32s, and the public SNO addresses remain the VXLAN VTEPs.

```text
                  SW1 / PHX SNO
                  AS65011 / public VTEP
                         |
                 public-IP TCP/1179
                         |
                 FRR route-server pod
                       AS65000
                         |
          C1 -> SW1 public TCP/1179
                         |
                  C1 / ASH SNO
                  AS65021 / public VTEP

        SW1 <======== VXLAN UDP/4789 ========> C1
                    VNI 5050 / 10.50.50.0/24
```

The pod is control-plane only; it is not in the VM data path. On an existing 1.4.25 lab, `make evpn-migrate` deploys and verifies this replacement first and only then deprovisions the repository-owned legacy `evpn-fr` server. See `docs/evpn.md`.

### 4. phoenixNAP dual NICs are bonded before installation

The first iPXE discovery can expose the same native/public DHCP address on both physical 10 Gb NICs. The automation uses that first Agent inventory to create an RHACM `NMStateConfig`, builds `bond0` in `802.3ad` mode, clones the active physical NIC MAC for DHCP, adds explicit NTP sources, regenerates the InfraEnv image and reboots iPXE. The OpenShift machine/default route then lives on `bond0`; private VLANs are consumed as tagged VLANs on the same bond.

## Prerequisites

Local workstation:

- Python 3
- Ansible Core
- `kubernetes.core` Ansible collection
- access to the existing RHACM hub
- phoenixNAP OAuth client ID/secret
- Cloudflare API token with Zone Read + DNS Write for `digitaldovey.net`
- Red Hat pull secret
- SSH public key at `~/.ssh/id_ed25519.pub`

Hub configured in this project:

```text
https://api.acm.sandbox5165.opentlc.com:6443
```

The API URL is informational; authentication uses `RHACM_KUBECONFIG`.

## Quick start

```bash
cp .env.example .env
# edit .env
source .env

# Default EVPN mode uses an embedded FRR route-server pod on SW1.
# No third phoenixNAP server is provisioned.
export EVPN_FABRIC_MODE=embedded-router

make bootstrap
make preflight
make deploy
```

For step-by-step execution:

```bash
make prepare-hub
make private-networks
make bgp
make provision
make dns
make install
make virt
make nmstate
make vm-l2
make evpn-router          # embedded FRR route-server on existing SNO
make evpn
make status
```

## DNS created

For SW1:

```text
api.sw1.digitaldovey.net
api-int.sw1.digitaldovey.net
*.apps.sw1.digitaldovey.net
sno-sw1.digitaldovey.net
```

For C1:

```text
api.c1.digitaldovey.net
api-int.c1.digitaldovey.net
*.apps.c1.digitaldovey.net
sno-c1.digitaldovey.net
```

All are unproxied Cloudflare A records pointing at the SNO public IP for this lab.

## Site-local VM Layer2

```text
PHX / SW1                             ASH / C1
public management                     public management
       |                                     |
OCP SNO + private VLAN                OCP SNO + private VLAN
       | 10.60.10.0/24                       | 10.60.20.0/24
       +-- pnap-vm-localnet                   +-- pnap-vm-localnet
             |                                      |
            VMs                                    VMs
```

The private VLAN ID is assigned by phoenixNAP and consumed as `bond0.<VLAN>` by an NMState NNCP.
The public/native VLAN and tagged private VM VLAN therefore share the phoenixNAP dual-NIC LACP
bond, while remaining separate Layer-2 segments through 802.1Q tagging. This matches phoenixNAP's
iPXE redundancy guidance; the API does not expose a supported "private VLAN only on NIC2" model.
See `docs/private-l2.md`.

## EVPN target

```text
PHX / SW1                                                ASH / C1
125.253.82.93                                            103.67.202.133
FRR-K8s AS65011                                          FRR-K8s AS65021
public VTEP                                              public VTEP
      |                                                        |
      | public-IP TCP/1179                                    |
      v                                                        |
FRR route-server pod / AS65000 <--------- TCP/1179 ------------+
(on the existing SW1 SNO)

      +========== OpenShift EVPN VNI 5050 / UDP 4789 ==========+
                              10.50.50.0/24
                              RT 65000:5050
```

The embedded route server exchanges EVPN reachability only. VXLAN traffic does **not** hairpin through it; data flows directly PHX↔ASH over UDP/4789. Automatic IP allocation is split by site so the two independent OVN IPAM databases cannot hand out the same VM address.

## Publish to GitHub

The downloaded project is already initialized as a Git repository with an initial commit. With the GitHub CLI authenticated:

```bash
./scripts/publish-github.sh phoenixnap-ocp422-evpn private
```

Use `public` instead of `private` only if you are comfortable publishing the infrastructure design. Secrets and runtime kubeconfigs are gitignored.

## Teardown

Hourly infrastructure costs money. Tear the lab down when finished:

```bash
make destroy
```

The destroy playbook deprovisions the two configured SNO servers. The legacy fabric-router teardown helper remains only to remove an older repository-owned `evpn-fr` server when `artifacts/evpn/fabric-router.yml` proves ownership; current deployments never provision a third EVPN server. It deletes a BGP peer group only when this repository recorded that it created that group; pre-existing regional peer groups are left intact. Review `playbooks/99_destroy.yml` before first use in a shared phoenixNAP account. Destroy is safe to rerun: phoenixNAP `deleting` state and temporary HTTP 409 lifecycle conflicts are retried/waited through, and teardown waits for BMC server objects to disappear before continuing.

## Repository layout

```text
inventories/lab/group_vars/all.yml   # lab definition
playbooks/                            # lifecycle entry points
roles/                                # idempotent implementation
artifacts/                            # generated runtime state, gitignored
docs/                                 # design and operations notes
```

## EVPN deployment behavior

`make deploy` uses `EVPN_FABRIC_MODE=embedded-router` by default. It deploys a small FRR route-server pod on the existing SW1 SNO, validates that both SNOs can reach its BGP listener, configures the public SNO IPv4 addresses as unmanaged VTEPs, reconciles the OpenShift `FRRConfiguration`, CUDN and `RouteAdvertisements`, and requires base BGP plus MP-BGP L2VPN EVPN to negotiate successfully.

For an existing checkout that still owns the old third server:

```bash
make evpn-migrate
```

The migration does not delete the legacy server until the embedded path has BGP Established, the remote Type-3 VTEP route is present, and VNI 5050 has a remote VTEP on both clusters. Keep the existing `artifacts/` directory so the repo can prove which phoenixNAP server it owns.

## macOS / Python interpreter note

All Make targets intentionally run Ansible from the project `.venv`. The inventory also pins
`localhost` modules to `{{ ansible_playbook_python }}` so modules such as
`kubernetes.core.k8s_info` execute with the same Python environment that launched Ansible.

If an older checkout reports `Failed to import the required Python library (kubernetes)`, rebuild
the project environment:

```bash
rm -rf .venv
make bootstrap
make preflight
```

Useful verification:

```bash
.venv/bin/ansible-playbook --version
.venv/bin/python -c 'import kubernetes; print(kubernetes.__version__)'
```

## Troubleshooting

### SNO Assisted Installer platform

For these PhoenixNAP SNO clusters the `AgentClusterInstall` intentionally uses `platformType: None` with `userManagedNetworking: true`. The `ClusterDeployment` still uses `platform.agentBareMetal.agentSelector` to bind Host Inventory Agents. Do not change the ACI to `BareMetal`: current Assisted Service rejects `BareMetal + userManagedNetworking=true`, while SNO requires user-managed networking.



### phoenixNAP iPXE dual-NIC overlap

If the first discovery reports the same native/public subnet on both physical NICs, do not override the Assisted Installer validation. The `pnap_servers` role creates a discovery-time `NMStateConfig` for `bond0`, reboots the host through iPXE, and waits for both `non-overlapping-subnets` and `ntp-synced` to pass before approval.

### Private VM Layer 2

Each site gets a phoenixNAP private **NO-CIDR** VLAN. The OpenShift host does not consume an IP on this VLAN; NMState/OVS exposes `bond0.<VLAN>` as an OVN Localnet secondary network for VMs. Inventory `private_l2.cidr` values are guest-addressing conventions only.

## Direct RHCOS rootfs bypass

The PhoenixNAP iPXE flow keeps the RHACM-generated discovery kernel/initrd, but
appends the `AgentServiceConfig` OpenShift 4.22 x86_64 `rootFSUrl` as an
`InfraEnv` kernel argument. This avoids streaming the ~1.2 GiB rootfs through
the hub ingress route when that path truncates large responses. Set
`rhacm.direct_rootfs.enabled: false` to disable the workaround.

### phoenixNAP LACP discovery bootstrap

For phoenixNAP iPXE hosts, the first DHCP discovery is used only to learn the two physical NIC names and MAC addresses. The automation then creates the per-host `NMStateConfig`, recreates the `InfraEnv` with that selector present from creation, updates the phoenixNAP iPXE URL, and reboots. This avoids relying on an in-place InfraEnv image refresh when advanced networking is added after the first discovery.

The resulting public network is DHCP on `bond0` in `802.3ad` mode. Site-local private VLANs are consumed later on the bond for OpenShift Virtualization localnet networking.


## Two-site EVPN lab fabric

Version 1.4.38 defaults to `EVPN_FABRIC_MODE=embedded-router` and transparently maps the removed legacy values `fabric-router` and `direct-peering` to `embedded-router`. Both OpenShift FRR-K8s speakers actively dial the host-network route server on the hosting public IP at TCP/1179. The route server enables `bgp allow-martian-nexthop` so the hosting leaf's public VTEP next-hop is accepted even though that address is local to the route-server host, then re-advertises L2VPN EVPN routes with AS65000 prepended and the originating VTEP next-hop unchanged; VNI5050 VXLAN stays direct over UDP/4789.

The old `self-managed-vxlan` VNI4090/UDP4790 design is retained only as an explicit diagnostic mode because the tested PHX↔ASH carrier did not pass traffic. See `docs/evpn.md` for the no-third-server topology and guarded migration workflow.

### phoenixNAP OAuth token refresh

phoenixNAP access tokens are short-lived. Long `make deploy` runs automatically refresh the bearer token before each site and again before the LACP reboot phase, so SW1 discovery time cannot cause C1 provisioning to fail with HTTP 401. No manual token handling is required.

### Legacy self-managed transit mode

`EVPN_FABRIC_MODE=self-managed-vxlan` is retained for diagnostics only. It still creates `evpn-transit0` and validates the remote `192.168.254.x` route before BGP, but it is not recommended for the tested PHX/ASH path. The default embedded-router design removes this nested carrier entirely.


## LVM Storage

`make deploy` installs Red Hat LVM Storage on both `sw1` and `c1` using a dedicated unused secondary device. Dynamic SNO SKU selection now requires at least two physical storage devices, and existing one-disk servers are rejected before the LVMS stage. To reconcile storage only on existing clusters, run:

```bash
make storage
```

The resulting default StorageClass is `lvms-vg1`. If an existing site was created with only one physical disk, use `make replace-site SITE=<site>` after reviewing the replacement action. See `docs/lvm-storage.md` for the disk-safety model.
