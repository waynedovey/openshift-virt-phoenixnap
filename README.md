# phoenixNAP OpenShift 4.22 Two-Site EVPN Lab

GitHub-ready Ansible automation for a two-region OpenShift Virtualization lab on phoenixNAP Bare Metal Cloud.

### Region-specific server types and availability

phoenixNAP inventory is location-specific and can change at any time. The repo now supports a different server type per site while retaining `phoenixnap.server_type` as the default.

```yaml
phoenixnap:
  server_type: s1.c1.medium

sites:
  sw1:
    location: PHX
    server_type: s1.c1.medium
  c1:
    location: CHI
    server_type: s1.c1.medium
```

Before deployment, run:

```bash
make availability
make preflight
```

`make availability` lists server product codes that the phoenixNAP Billing API currently reports as available in PHX and CHI. If the preferred SKU is out of stock in one region, change only that site's `server_type`. The automation never silently selects a more expensive fallback.

## What it builds

- **PHX / US SW1**: `sw1.digitaldovey.net`
- **CHI / US C1**: `c1.digitaldovey.net`
- phoenixNAP `s1.c1.medium` billed **HOURLY**
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

### 1. `s1.c1.medium` is the requested server shape

The project now validates `s1.c1.medium` availability in both PHX and CHI before provisioning.
Server type is immutable in BMC, so an existing `s2.c1.small` server is never silently reused.
Use the explicit one-time replacement workflow:

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

