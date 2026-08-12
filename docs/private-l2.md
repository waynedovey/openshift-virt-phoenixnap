# Site-local private Layer2 network for OpenShift Virtualization

Each phoenixNAP SNO uses the provider's dual-NIC network model:

1. The two physical data NICs form `bond0` using LACP (`802.3ad`).
2. The iPXE/native public VLAN provides DHCP, the OpenShift API/Ingress path and management on `bond0`.
3. A phoenixNAP **Private Network** is trunked as an additional tagged VLAN on the same bond and is exposed to VMs through OVN Localnet.

The automation creates:

| Site | phoenixNAP location | Private network | Guest CIDR | Purpose |
|---|---|---|---|---|
| SW1 | PHX | `ocp-sw1-vm-l2` | `10.60.10.0/24` | site-local VM L2 |
| C1 | ASH | `ocp-c1-vm-l2` | `10.60.20.0/24` | site-local VM L2 |

The provider VLANs themselves are created with **NO-CIDR**. The CIDRs above are guest VM addressing conventions only.

## Why the LACP bootstrap is required

phoenixNAP iPXE initially exposes the dual NICs without OS-level redundancy. During discovery, both physical NICs can obtain the same DHCP address on the native public VLAN. Assisted Installer correctly rejects that as overlapping networking.

The provisioning role therefore performs a two-stage discovery:

1. Boot the RHACM InfraEnv normally and wait for the Agent inventory.
2. Discover the two physical NIC MAC addresses and the interface carrying the preferred/default route.
3. Create an RHACM `NMStateConfig` that builds `bond0` in `802.3ad` mode.
4. Clone the preferred physical NIC MAC onto the bond so phoenixNAP DHCP can continue using its reservation.
5. Attach the NMStateConfig to the InfraEnv, add explicit NTP sources and wait for the discovery image to regenerate.
6. Reboot the server using iPXE and wait until the Agent reports the bond plus passing `non-overlapping-subnets` and `ntp-synced` validations.
7. Approve the Agent for SNO installation.

This avoids overriding a real Assisted Installer validation failure.

## Private VLAN placement

phoenixNAP attaches VLANs to the server network fabric rather than exposing a supported per-VLAN physical-port selector such as "put this private VLAN only on NIC2". Once LACP is established, VLANs should be consumed on the bond.

The OpenShift post-install networking therefore creates:

```text
physical NIC 0 ----\
                    +-- bond0 -- native/public DHCP
physical NIC 1 ----/       \
                            +-- bond0.<private VLAN> -- br-pnap-vm -- OVN Localnet -- VMs
```

The private VLAN subinterface has no host IPv4 or IPv6 address. It is only a Layer-2 transport into the OVS/OVN Localnet bridge.

## OpenShift mapping

After installation the automation installs Kubernetes NMState and verifies `bond0` exists. It then creates:

- tagged VLAN subinterface `bond0.<phoenixNAP VLAN ID>`;
- OVS bridge `br-pnap-vm`;
- OVN bridge mapping `pnap-vm-l2 -> br-pnap-vm`;
- secondary Localnet `ClusterUserDefinedNetwork` named `pnap-vm-localnet`;
- namespace `vm-workloads` selected by that CUDN.

The Localnet CUDN has IPAM disabled. Guest addresses are controlled by the VM or external DHCP/IPAM.

Suggested lab ranges:

- SW1 VMs: `10.60.10.20-10.60.10.250/24`
- C1 VMs: `10.60.20.20-10.60.20.250/24`

Do not use those ranges as a cross-site portable subnet. The PHX and ASH private networks are independent L2 broadcast domains.

## Cross-site boundary

The separate EVPN design remains responsible for the portable `10.50.50.0/24` VM network:

```text
PHX local private VLAN                      ASH local private VLAN
10.60.10.0/24                               10.60.20.0/24
       |                                           |
       +--- OCP SNO --- OpenShift EVPN/VXLAN --- OCP SNO ---+
                               |
                     shared 10.50.50.0/24
                     VNI 5050 / RT 65000:5050
```

phoenixNAP standard BGP peer groups remain ordinary IP BGP and are not treated as an EVPN fabric by this project.

## Pure Layer-2 provider network

The phoenixNAP private networks are created with no provider CIDR (`force=true`). The SNO host receives no IP address on the private VLAN. OpenShift NMState creates the tagged VLAN and OVS bridge with IPv4/IPv6 disabled.

### First private network in a location

phoenixNAP requires the first private network owned by an account in a location to be marked as that location's default private network. The automation detects this and sets `locationDefault: true` only for the first network. Servers still attach the VLAN explicitly through `USER_DEFINED` networking.
