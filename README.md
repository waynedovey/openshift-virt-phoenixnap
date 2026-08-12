# phoenixNAP OpenShift 4.22 Two-Site EVPN Lab


> **Updating an existing checkout:** unpack the new ZIP beside the checkout, then run `rsync -a openshift-virt-phoenixnap-main/ ./` and verify with `make version`. Do not use a stale extracted directory from an earlier revision.

GitHub-ready Ansible automation for a two-region OpenShift Virtualization lab on phoenixNAP Bare Metal Cloud.

### Dynamic server selection under $0.30/hour

The lab now selects the server shape at runtime instead of hard-coding a SKU. It combines
phoenixNAP's live product catalog, hourly pricing and live stock for PHX and ASH.

Default policy:

```yaml
phoenixnap:
  pricing_model: HOURLY
  auto_select:
    enabled: true
    max_hourly_price: 0.30   # strict: selected price must be < $0.30/h
    min_ram_gb: 64
    min_cores: 6
    preferred_ram_gb: 128
    preferred_cores: 8
    prefer_common_sku: true
    require_common_sku: false
```

Selection order is deliberately cost-aware:

1. Must have live stock in the target region.
2. Must use a `HOURLY` / `HOUR` pricing plan strictly below the configured cap.
3. Must satisfy the hard RAM/core minimums.
4. Prefer a SKU closest to the preferred 128 GB / 8-core lab target.
5. Among equally suitable shapes, choose the lower hourly price.
6. Prefer the same SKU in PHX and ASH. If no common SKU qualifies, select independently per site unless `require_common_sku: true`.

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
- dynamically selected phoenixNAP server below **$0.30/hour per site**, billed **HOURLY**
- RHACM Host Inventory / Assisted Installer `InfraEnv` per site
- phoenixNAP iPXE boot directly from the RHACM InfraEnv boot artifact
- OpenShift Container Platform **4.22** Single Node OpenShift at each site
- Cloudflare DNS for API, API-int and wildcard ingress
- OpenShift Virtualization on each SNO
- phoenixNAP dual-NIC LACP bond for the SNO native/public network
- phoenixNAP private Layer-2 VLAN in each region for OpenShift Virtualization VMs
- secondary OVN-Kubernetes Localnet CUDN backed by that private VLAN
- phoenixNAP BGP Peer Group creation in both regions
- complete two-site OpenShift 4.22 EVPN lab fabric built automatically by `make deploy`

> **RHACM release-image self-heal:** if the hub does not currently contain an OpenShift 4.22 `ClusterImageSet`, `make deploy` creates `openshift-4.22.0-auto` automatically. Set `OPENSHIFT_RELEASE_IMAGE` only if you need a mirrored registry or a different 4.22.z payload.

- self-managed PHX↔ASH routed VXLAN transit for MP-BGP EVPN, with optional external-provider mode
- explicit, guarded teardown of hourly resources

## Deliberate safety decisions

### 1. Server shape is selected dynamically within a hard hourly budget

The project selects a live SKU under the configured hourly cap and sizing policy immediately before
provisioning. Existing incompatible servers are never silently resized or destroyed. Use the explicit
replacement workflow when you intentionally want the selected shape to replace an existing server:

```bash
make private-networks
make replace-servers
make deploy
```

`make deploy` is safe to rerun against already-installed SW1/C1 clusters. The RHACM/Hive stage preserves an existing `ClusterDeployment.spec.installed: true` value rather than attempting to reset the cluster to an uninstalled state.

For an existing compatible phoenixNAP server, `make deploy` also reconciles a missing site-local private Layer-2 network membership in place through the BMC API instead of incorrectly asking for a server replacement. It never removes an existing private-network membership automatically.

### 2. Private Layer2 is site-local, not a PHX-to-ASH VLAN stretch

Each SNO gets public management/iPXE connectivity plus a phoenixNAP private VLAN for VMs.
The OpenShift side maps that VLAN into a secondary OVN Localnet CUDN. PHX and ASH private
networks are separate L2 broadcast domains; the EVPN layer remains responsible for the shared
`10.50.50.0/24` cross-site VM subnet. See `docs/private-l2.md`.

### 3. `make deploy` now builds the PHX↔ASH EVPN lab fabric end to end

The phoenixNAP BGP Peer Groups remain standard IP-BGP resources and are **not** treated as an L2VPN EVPN provider fabric. Instead, the default `self-managed-vxlan` mode builds a deterministic routed transit directly between the two existing SNO nodes.

`make deploy` derives each SNO public address from the generated server artifacts, creates `evpn-transit0` with VXLAN VNI 4090 / UDP 4790, assigns `192.168.254.1/30` and `192.168.254.2/30`, and then establishes direct eBGP between FRR-K8s ASN 65011 and ASN 65021. OpenShift uses that underlay to exchange the VTEP routes and the MP-BGP L2VPN EVPN address family for VNI 5050.

The lab keeps the real OpenShift EVPN data plane distinct from the carrier tunnel:

```text
physical bond MTU 1500
  └─ transit VXLAN VNI 4090 / UDP 4790, MTU 1450
       └─ OpenShift EVPN VXLAN VNI 5050 / UDP 4789, CUDN MTU 1400
```

Only UDP/4790 needs to pass between the two public SNO addresses in the default lab mode. The carrier is intentionally a lab shim, not a production provider-fabric design. For a real EVPN-capable DC/provider fabric, set `EVPN_FABRIC_MODE=external` and provide the external peer addresses/ASN. See `docs/evpn.md`.

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
PHX / SW1                                             ASH / C1
public IP                                               public IP
   |                                                       |
   +==== lab carrier VXLAN VNI 4090 / UDP 4790 ============+
   |        192.168.254.1/30 <-> 192.168.254.2/30           |
   |                                                       |
FRR-K8s ASN 65011 <========== MP-BGP EVPN =========> FRR-K8s ASN 65021
   |                                                       |
VTEP 10.255.50.11/32                              VTEP 10.255.50.21/32
   |                                                       |
   +========= OpenShift EVPN VNI 5050 / UDP 4789 ==========+
                         10.50.50.0/24
```

Automatic IP allocation is split by site so the two independent cluster IPAM databases cannot hand out the same VM address: SW1 uses the lower half of the `/24` and C1 uses the upper half, while both still participate in the same MAC-VRF.

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

The destroy playbook deprovisions only servers matching the configured node hostnames. It deletes a BGP peer group only when this repository recorded that it created that group; pre-existing regional peer groups are left intact. Review `playbooks/99_destroy.yml` before first use in a shared phoenixNAP account. Destroy is safe to rerun: phoenixNAP `deleting` state and temporary HTTP 409 lifecycle conflicts are retried/waited through, and teardown waits for the BMC server object to disappear before continuing.

## Repository layout

```text
inventories/lab/group_vars/all.yml   # lab definition
playbooks/                            # lifecycle entry points
roles/                                # idempotent implementation
artifacts/                            # generated runtime state, gitignored
docs/                                 # design and operations notes
```

## EVPN deployment behavior

`make deploy` now completes the two-site lab EVPN fabric automatically in the default `self-managed-vxlan` mode. It builds the PHX↔ASH carrier, establishes base eBGP, creates the EVPN CUDN and RouteAdvertisements, and does not return success until MP-BGP L2VPN EVPN is established and each cluster has learned the remote VTEP `/32`. External EVPN peer inputs are required only when `EVPN_FABRIC_MODE=external`.

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

Version 1.4 defaults to `EVPN_FABRIC_MODE=self-managed-vxlan`. `make deploy`
automatically creates a routed PHX<->ASH VXLAN transit and runs MP-BGP EVPN
between the two OpenShift 4.22 SNO clusters. See `docs/evpn.md` for the topology,
MTU design, validation steps, and the external-provider mode.

### phoenixNAP OAuth token refresh

phoenixNAP access tokens are short-lived. Long `make deploy` runs automatically refresh the bearer token before each site and again before the LACP reboot phase, so SW1 discovery time cannot cause C1 provisioning to fail with HTTP 401. No manual token handling is required.
