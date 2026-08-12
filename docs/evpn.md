# EVPN activation

`make deploy` owns the complete OpenShift-side EVPN lifecycle and, by default,
builds a deterministic two-site lab underlay between PHX and ASH.

## Default lab fabric: self-managed VXLAN transit

phoenixNAP's normal BGP Peer Group is retained for standard IP BGP but is not
assumed to provide MP-BGP L2VPN EVPN. The lab therefore creates a routed carrier
directly between the two existing SNO nodes:

```text
PHX / SW1                                              ASH / C1
public IP                                                public IP
   |                                                        |
   +==== transport VXLAN VNI 4090 / UDP 4790 ===============+
   |          192.168.254.1/30 <-> 192.168.254.2/30          |
   |                                                        |
FRR-K8s ASN 65011  <========= eBGP / MP-BGP =========> FRR-K8s ASN 65021
   |                                                        |
VTEP 10.255.50.11/32                               VTEP 10.255.50.21/32
   |                                                        |
   +========== OpenShift EVPN VNI 5050 / UDP 4789 ==========+
                         10.50.50.0/24
```

The outer transport VXLAN is only a **lab underlay shim**. OpenShift still owns
the EVPN control plane and the real VNI 5050 VXLAN data plane. The OpenShift
VTEPs remain on dummy interfaces and OVN-Kubernetes advertises their `/32`
routes through the BGP underlay.

The MTUs are intentionally nested:

- phoenixNAP bond: 1500
- lab transit VXLAN: 1450
- EVPN CUDN: 1400

This leaves 50 bytes for each IPv4 VXLAN layer and does not require jumbo frames.

Run:

```bash
make deploy
```

No `EVPN_SW1_PEER`, `EVPN_C1_PEER` or fabric confirmation is required in the
default mode. The deployment derives the public outer addresses from
`artifacts/servers/sw1.yml` and `artifacts/servers/c1.yml`.

The provider path between PHX and ASH must permit **UDP/4790** between the two
SNO public IPs. TCP/179 and OpenShift EVPN UDP/4789 are carried inside the lab
transit rather than exposed directly as the inter-site transport.

## Bootstrap order

A fresh two-site deployment is deliberately phased:

1. Enable FRR-K8s, route advertisements and required gateway settings on both clusters.
2. Create `evpn-vtep0` and `VTEP/evpn-vtep` on both clusters.
3. Create `evpn-transit0` on **both** sites.
4. Create `FRRConfiguration/evpn-fabric` on **both** sites.
5. Only then wait for the base eBGP sessions to become `Established`.
6. Create `evpn-vm-net` and `evpn-vm-routes` on both clusters.
7. Wait for `EVPNTransportAccepted`, RouteAdvertisements `Accepted`, MP-BGP L2VPN EVPN establishment and the remote VTEP `/32` route.

This ordering is important: waiting for SW1 BGP before C1's `FRRConfiguration`
exists would deadlock a clean deployment.

## Objects created on each cluster

`make deploy` creates and verifies:

1. FRR-K8s and route advertisements in the Cluster Network Operator.
2. `gatewayConfig.routingViaHost: true` and `ipForwarding: Global`.
3. `Namespace/evpn-vms` with the primary UDN label.
4. `NNCP/evpn-vtep` with the private dummy VTEP address.
5. `VTEP/evpn-vtep` for `10.255.50.0/24`.
6. `NNCP/evpn-cross-site-transit` for the routed PHX-ASH VXLAN carrier.
7. `FRRConfiguration/evpn-fabric` with the remote transit address as neighbor.
8. `ClusterUserDefinedNetwork/evpn-vm-net` using EVPN MAC-VRF VNI 5050.
9. `RouteAdvertisements/evpn-vm-routes`.
10. Base BGP, MP-BGP EVPN and remote-VTEP route verification.

The BGP password is generated once and retained locally at
`artifacts/secrets/evpn-bgp-password`; matching Kubernetes basic-auth secrets are
created on both managed clusters.

## Cross-cluster IPAM split

The two OpenShift clusters do not share an OVN IPAM database, so letting both
automatically allocate from the whole `/24` can create duplicate addresses. The
same EVPN segment is therefore presented on both clusters, but the automatic
allocation and infrastructure ranges are split:

```text
SW1: gateway 10.50.50.1
     infrastructure 10.50.50.0/28
     reserves 10.50.50.128/25 from automatic allocation

C1:  gateway 10.50.50.129
     infrastructure 10.50.50.128/28
     reserves 10.50.50.0/25 from automatic allocation
```

Both clusters still advertise the same MAC-VRF VNI 5050 / RT 65000:5050 and use
the same `10.50.50.0/24` Layer-2 subnet.

## Production/external fabric mode

The self-managed transit is for this lab. A production deployment should use a
real EVPN-capable provider/DC fabric. Switch modes with:

```bash
export EVPN_FABRIC_MODE='external'
export EVPN_FABRIC_CONFIRMED='true'
export EVPN_PEER_ASN='65000'
export EVPN_SW1_PEER='<PHX-EVPN-PEER-IP>'
export EVPN_C1_PEER='<C1-EVPN-PEER-IP>'
make deploy
```

## VM network

The EVPN network is a primary CUDN:

```text
namespace:    evpn-vms
CUDN:         evpn-vm-net
subnet:       10.50.50.0/24
MTU:          1400
VNI:          5050
route target: 65000:5050
```

VMs created only on `pnap-vm-localnet` remain site-local. Cross-site test VMs
must be created in `evpn-vms` and use the namespace primary UDN.

## Verification

After `make deploy` succeeds, on either managed cluster:

```bash
oc get nncp evpn-vtep evpn-cross-site-transit
oc get vtep evpn-vtep
oc get frrconfiguration -n openshift-frr-k8s
oc get routeadvertisements
oc get clusteruserdefinednetwork evpn-vm-net

FRR_POD=$(oc get pod -n openshift-frr-k8s -o name | grep 'pod/frr-k8s-' | grep -v statuscleaner | head -1 | cut -d/ -f2)
oc exec -n openshift-frr-k8s "$FRR_POD" -c frr -- vtysh -c 'show bgp l2vpn evpn summary'
oc exec -n openshift-frr-k8s "$FRR_POD" -c frr -- vtysh -c 'show bgp l2vpn evpn route type 2'
```

Type-2 MAC/IP routes appear once EVPN workloads are running.

## Security note

The self-managed carrier VXLAN is not encrypted. It is suitable for this
controlled lab but should not be treated as a production WAN security design.
Use an encrypted underlay or a provider EVPN service for production traffic.
