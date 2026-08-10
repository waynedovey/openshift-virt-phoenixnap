# phoenixNAP OpenShift 4.22 Two-Site EVPN Lab

GitHub-ready Ansible automation for a two-region OpenShift Virtualization lab on phoenixNAP Bare Metal Cloud.

### Dynamic server selection under $0.30/hour

The lab now selects the server shape at runtime instead of hard-coding a SKU. It combines
phoenixNAP's live product catalog, hourly pricing and live stock for PHX and CHI.

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
6. Prefer the same SKU in PHX and CHI. If no common SKU qualifies, select independently per site unless `require_common_sku: true`.

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
- **CHI / US C1**: `c1.digitaldovey.net`
- dynamically selected phoenixNAP server below **$0.30/hour per site**, billed **HOURLY**
- RHACM Host Inventory / Assisted Installer `InfraEnv` per site
- phoenixNAP iPXE boot directly from the RHACM InfraEnv boot artifact
- OpenShift Container Platform **4.22** Single Node OpenShift at each site
- Cloudflare DNS for API, API-int and wildcard ingress
- OpenShift Virtualization on each SNO
- phoenixNAP private Layer-2 VLAN in each region for OpenShift Virtualization VMs
- secondary OVN-Kubernetes Localnet CUDN backed by that private VLAN
- phoenixNAP BGP Peer Group creation in both regions
- staged OpenShift 4.22 BGP EVPN configuration for a shared VM network
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

### 2. Private Layer2 is site-local, not a PHX-to-CHI VLAN stretch

Each SNO gets public management/iPXE connectivity plus a phoenixNAP private VLAN for VMs.
The OpenShift side maps that VLAN into a secondary OVN Localnet CUDN. PHX and CHI private
networks are separate L2 broadcast domains; the EVPN layer remains responsible for the shared
`10.50.50.0/24` cross-site VM subnet. See `docs/private-l2.md`.

### 3. phoenixNAP BGP is not assumed to be an EVPN fabric

The playbooks create phoenixNAP BGP Peer Groups, but **do not equate normal BGP peering with EVPN L2VPN transport**. `evpn.apply` defaults to `false`.

After you provide actual external EVPN peers reachable from the SNO nodes, set:

```yaml
evpn:
  apply: true
  fabric_confirmed: true
  peer_asn: 65000
  peers:
    sw1: <PHX-EVPN-PEER-IP>
    c1: <CHI-EVPN-PEER-IP>
```

See `docs/evpn.md`.

### 4. Machine network is learned from phoenixNAP DHCP

The repository does not invent a private `machineNetwork` for the SNOs. phoenixNAP assigns the iPXE/native public address and the Assisted Installer discovers the host network. Pod and service ranges remain site-specific.

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
PHX / SW1                             CHI / C1
public management                     public management
       |                                     |
OCP SNO + private VLAN                OCP SNO + private VLAN
       | 10.60.10.0/24                       | 10.60.20.0/24
       +-- pnap-vm-localnet                   +-- pnap-vm-localnet
             |                                      |
            VMs                                    VMs
```

The private VLAN ID is assigned by phoenixNAP and consumed by an NMState NNCP. For this lab,
the automation deliberately selects an UP Ethernet interface other than the SNO's IPv4
default-route interface as the private-L2 uplink; it fails safely if no such interface is
visible. phoenixNAP itself attaches VLANs at the server/fabric level rather than exposing a
per-network "NIC2" selector in the API, and recommends LACP for production. See
`docs/private-l2.md`.

## EVPN target

```text
PHX / SW1                               CHI / C1
+------------------+                   +------------------+
| OCP 4.22 SNO     |                   | OCP 4.22 SNO     |
| OpenShift Virt   |                   | OpenShift Virt   |
| ASN 65011        |                   | ASN 65021        |
| VTEP 10.255.50.11|                   | VTEP 10.255.50.21|
+---------+--------+                   +--------+---------+
          |                                     |
          +------ external BGP EVPN/VXLAN ------+
                    VM: 10.50.50.0/24
                    VNI: 5050
                    RT: 65000:5050
```

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

The destroy playbook deprovisions only servers matching the configured node hostnames. It deletes a BGP peer group only when this repository recorded that it created that group; pre-existing regional peer groups are left intact. Review `playbooks/99_destroy.yml` before first use in a shared phoenixNAP account.

## Repository layout

```text
inventories/lab/group_vars/all.yml   # lab definition
playbooks/                            # lifecycle entry points
roles/                                # idempotent implementation
artifacts/                            # generated runtime state, gitignored
docs/                                 # design and operations notes
```

## First thing to review

Open `inventories/lab/group_vars/all.yml`. The remaining unresolved design input is the **actual external EVPN peer address at each site**. Everything before EVPN can be automated now.

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



### Private VM Layer 2

Each site gets a phoenixNAP private **NO-CIDR** VLAN. The OpenShift host does not consume an IP on this VLAN; NMState/OVS exposes it as an OVN Localnet secondary network for VMs. Inventory `private_l2.cidr` values are guest-addressing conventions only.
