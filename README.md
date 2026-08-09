# phoenixNAP OpenShift 4.22 Two-Site EVPN Lab

GitHub-ready Ansible automation for a two-region OpenShift Virtualization lab on phoenixNAP Bare Metal Cloud.

## What it builds

- **PHX / US SW1**: `sw1.digitaldovey.net`
- **CHI / US C1**: `c1.digitaldovey.net`
- phoenixNAP `s2.c1.small` billed **HOURLY**
- RHACM Host Inventory / Assisted Installer `InfraEnv` per site
- phoenixNAP iPXE boot directly from the RHACM InfraEnv boot artifact
- OpenShift Container Platform **4.22** Single Node OpenShift at each site
- Cloudflare DNS for API, API-int and wildcard ingress
- OpenShift Virtualization on each SNO
- phoenixNAP BGP Peer Group creation in both regions
- staged OpenShift 4.22 BGP EVPN configuration for a shared VM network
- explicit, guarded teardown of hourly resources

## Deliberate safety decisions

### 1. `s2.c1.small` is allowed, with a warning

The requested SKU is preserved. OpenShift 4.22 supports a smaller SNO minimum than older releases, but 8 vCPU remains the recommended topology. For heavier VM demos, change:

```yaml
phoenixnap:
  server_type: s2.c2.small
```

### 2. phoenixNAP BGP is not assumed to be an EVPN fabric

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

### 3. Machine network is learned from phoenixNAP DHCP

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
make bgp
make provision
make dns
make install
make virt
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

