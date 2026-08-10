# Site-local private Layer2 network for OpenShift Virtualization

Each phoenixNAP SNO is provisioned with two network roles:

1. Public/IP-block connectivity for iPXE, OpenShift API/Ingress and management.
2. A phoenixNAP **Private Network** VLAN used as a physical Layer2 segment for VMs.

The automation creates:

| Site | phoenixNAP location | Private network | CIDR | Purpose |
|---|---|---|---|---|
| SW1 | PHX | `ocp-sw1-vm-l2` | `10.60.10.0/24 (guest addressing; provider VLAN is NO-CIDR)` | site-local VM L2 |
| C1 | CHI | `ocp-c1-vm-l2` | `10.60.20.0/24 (guest addressing; provider VLAN is NO-CIDR)` | site-local VM L2 |

phoenixNAP dynamically assigns the VLAN IDs. The server is attached at provisioning with
`networkType: PUBLIC_AND_PRIVATE`, a purchased public IP block, and the site private network.
Private-network DHCP is disabled because the server also has public connectivity.

## Physical NIC behaviour on phoenixNAP

phoenixNAP attaches VLANs to the server networking fabric; its API does **not** provide a
per-private-network switch-port selector such as "put this VLAN only on NIC2". BMC servers
have dual NICs, and phoenixNAP recommends an LACP bond for production, with VLANs consumed
on the bond.

For this **lab**, the OpenShift role implements the requested second-uplink pattern after SNO
is installed: it discovers the IPv4 default-route NIC and uses another UP Ethernet NIC as the
VM-L2 VLAN uplink. It only adds a tagged VLAN subinterface; it does not move the OpenShift
machine/default route. If it cannot identify a safe non-management interface, it stops instead
of changing networking.

This gives VMs a second vNIC backed by the site-local private L2. For a long-lived production
design, switch `uplink_interface` to an explicitly validated bond/VLAN design rather than
leaving the host single-homed.

## OpenShift mapping

After installation the automation installs Kubernetes NMState and discovers the SNO's IPv4
default-route interface. With `uplink_interface: auto`, it selects an UP Ethernet interface
that is **not** the management/default-route interface. It then creates:

- a tagged VLAN subinterface using the phoenixNAP-assigned VLAN ID;
- OVS bridge `br-pnap-vm`;
- OVN bridge mapping `pnap-vm-l2 -> br-pnap-vm`;
- secondary Localnet `ClusterUserDefinedNetwork` named `pnap-vm-localnet`;
- namespace `vm-workloads` selected by that CUDN.

The Localnet CUDN has IPAM disabled for VMs. Guest addresses are therefore controlled by the
VM/your external IPAM rather than independently allocated by each OpenShift cluster.

## Safety

The role will not deliberately repurpose the interface carrying the default route. If no spare
UP Ethernet NIC can be identified, it fails before applying the NNCP. Set
`sites.<site>.private_l2.uplink_interface` explicitly only after verifying the correct NIC.

## VM attachment and guest addressing

The CUDN is secondary and has IPAM disabled, as required for this OpenShift Virtualization
Localnet pattern. Attach `pnap-vm-localnet` as a second VM network and set the guest address
from the site subnet (or provide external DHCP/IPAM). Example static guest ranges can be kept
away from the reserved node address:

- SW1 VMs: `10.60.10.20-10.60.10.250/24`
- C1 VMs: `10.60.20.20-10.60.20.250/24`

Do not use those addresses as a cross-site portable range; the two private networks are
independent L2 broadcast domains.

A VM interface/network snippet is included at `examples/vm-localnet-network-snippet.yaml`.

## Cross-site boundary

A phoenixNAP private network is location-scoped. The PHX VLAN and CHI VLAN are separate Layer2
broadcast domains. They give each site a physical VM network, but they do **not** create the
shared cross-site subnet.

The separate EVPN design remains responsible for the portable `10.50.50.0/24` VM network:

```text
PHX local private VLAN                      CHI local private VLAN
10.60.10.0/24 (guest addressing; provider VLAN is NO-CIDR)                               10.60.20.0/24 (guest addressing; provider VLAN is NO-CIDR)
       |                                           |
       +--- OCP SNO --- external EVPN/VXLAN --- OCP SNO ---+
                               |
                     shared 10.50.50.0/24
                     VNI 5050 / RT 65000:5050
```

phoenixNAP standard BGP peering remains on public addresses; BMC does not support BGP peering
over private IP addresses.


## Pure Layer 2 provider network

The phoenixNAP private networks are created with no provider CIDR (`force=true`). This is intentional. The SNO host receives no IP address on the private VLAN. OpenShift NMState creates the VLAN subinterface and OVS bridge with IPv4/IPv6 disabled, and OVN Localnet passes Layer-2 traffic to VM interfaces. The `private_l2.cidr` values in inventory are guest addressing conventions only.
