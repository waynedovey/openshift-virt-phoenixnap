# EVPN activation

OpenShift 4.22 EVPN expects `FRRConfiguration` peers toward an external EVPN-capable fabric. `RouteAdvertisements` selects those peers, and OVN-Kubernetes activates the L2VPN EVPN address family for the selected primary CUDN.

## Default lab fabric: external FRR fabric router

The tested phoenixNAP BGP Peer Groups successfully established IPv4 BGP, but did not negotiate L2VPN EVPN. A second live test showed that OpenShift FRR-K8s runs `bgpd` with `-p 0`: it actively dials configured peers but does not listen on TCP/179, so SW1 and C1 cannot act as each other's provider-facing passive peer.

The default v1.4.17 topology is therefore:

```text
                              FRR fabric router
                                  AS65000
                               listens TCP/179
                              /              \
                      MP-BGP EVPN          MP-BGP EVPN
                          /                    \
PHX / SW1                /                      \              ASH / C1
131.153.236.243 AS65011                         103.67.202.133 AS65021
VTEP 131.153.236.243/32                         VTEP 103.67.202.133/32
             \                                      /
              +======= VXLAN VNI 5050 / UDP 4789 ==+
                         10.50.50.0/24
                         RT 65000:5050
```

The fabric router is **control-plane only**. It uses ordinary eBGP to re-advertise routes between AS65011 and AS65021. The router prepends its own AS65000, which satisfies the clients' default eBGP first-AS validation, while FRR `attribute-unchanged next-hop` preserves the originating public VTEP as the EVPN next-hop. VM traffic therefore never hairpins through the fabric router.

The PHX↔ASH public path was tested bidirectionally for UDP/4789, so OpenShift's native VXLAN data plane can travel directly between the two SNO public VTEPs.

## Fabric-router choices

### Option A: let the repository provision it

Auto-provisioning is deliberately disabled by default because it creates a third billable phoenixNAP hourly server.

```bash
export EVPN_FABRIC_MODE='fabric-router'
export EVPN_FR_AUTO_PROVISION='true'
export EVPN_FR_LOCATION='PHX'
export EVPN_FR_ASN='65000'
export EVPN_FR_MAX_HOURLY_PRICE='0.30'
make deploy
```

The fabric-router role:

1. reads the current SW1/C1 public IPs from repository server artifacts;
2. selects a small live hourly SKU below the configured cap;
3. reports the selected SKU/price before the billable API call;
4. provisions Ubuntu with cloud-init;
5. installs FRR and configures AS65000;
6. defines SW1 AS65011 and C1 AS65021 as ordinary eBGP peers under IPv4 unicast and L2VPN EVPN, preserving the originating next-hop on re-advertisement;
7. stores only non-secret ownership state in `artifacts/evpn/fabric-router.yml`;
8. stores the generated BGP password separately in `artifacts/secrets/evpn-fabric-router-password`.

`make destroy` checks that ownership artifact and deprovisions the fabric router as well, so a repository-created third hourly server is not silently left behind.

### Option B: use an existing fabric router

```bash
export EVPN_FABRIC_MODE='fabric-router'
export EVPN_FR_AUTO_PROVISION='false'
export EVPN_FR_ADDRESS='<FABRIC-ROUTER-PUBLIC-IP>'
export EVPN_FR_ASN='65000'
export EVPN_FR_BGP_PASSWORD='<SHARED-TCP-MD5-PASSWORD>'
make deploy
```

The external fabric router must listen on TCP/179 and activate both clients under `address-family l2vpn evpn`. For the lab ASNs, its logical FRR configuration is equivalent to:

```text
router bgp 65000
 bgp router-id <FABRIC_ROUTER_ID>
 no bgp default ipv4-unicast
 no bgp ebgp-requires-policy
 neighbor 131.153.236.243 remote-as 65011
 neighbor 103.67.202.133 remote-as 65021
 ! optional shared TCP-MD5 password on both peers
 address-family ipv4 unicast
  neighbor 131.153.236.243 activate
  neighbor 131.153.236.243 attribute-unchanged next-hop
  neighbor 103.67.202.133 activate
  neighbor 103.67.202.133 attribute-unchanged next-hop
 exit-address-family
 address-family l2vpn evpn
  neighbor 131.153.236.243 activate
  neighbor 131.153.236.243 attribute-unchanged next-hop
  neighbor 103.67.202.133 activate
  neighbor 103.67.202.133 attribute-unchanged next-hop
 exit-address-family
```

## OpenShift VTEPs

In fabric-router mode the existing SNO public IPv4 address is used as the unmanaged VTEP:

```text
SW1: 131.153.236.243/32
C1:  103.67.202.133/32
```

The automation removes the old `evpn-vtep0` dummy interface and reconciles `VTEP/evpn-vtep` to the public `/32`. OpenShift discovers the primary IPv4 address already present on the node interface and uses it as the VTEP. Because this lab has one fabric-router peer per SNO, the redundant-peering recommendation to use a dummy VTEP interface does not apply to the default topology.

## Bootstrap order

A fabric-router deployment is deliberately phased:

1. Provision/reuse SW1 and C1 and capture their current public IPs.
2. If explicitly enabled, provision the external FRR fabric router.
3. Remove temporary diagnostic direct peers and the legacy `evpn-transit0` carrier.
4. Enable FRR-K8s, route advertisements, `routingViaHost: true`, and `ipForwarding: Global`.
5. Reconcile each unmanaged VTEP to the SNO public IPv4 address.
6. Create `FRRConfiguration/evpn-fabric` pointing at the fabric router.
7. Wait for base eBGP to become `Established`.
8. Create/reconcile the EVPN CUDN and `RouteAdvertisements`.
9. Wait for `EVPNTransportAccepted`, `RouteAdvertisements Accepted`, and successful L2VPN EVPN negotiation.
10. Verify that the remote public VTEP is directly routable; Type-2 routes appear when workloads are attached.

## Objects created on each cluster

The OpenShift side creates/reconciles:

1. CNO FRR and route-advertisement prerequisites.
2. `Namespace/evpn-vms` with the primary UDN label.
3. `NNCP/evpn-vtep` with the legacy dummy interface absent in fabric-router mode.
4. `VTEP/evpn-vtep` using the local public `/32`.
5. `Secret/evpn-bgp-auth` when BGP authentication is enabled.
6. `FRRConfiguration/evpn-fabric` toward the fabric router.
7. `ClusterUserDefinedNetwork/evpn-vm-net` using MAC-VRF VNI 5050.
8. `RouteAdvertisements/evpn-vm-routes`.
9. Base BGP, L2VPN EVPN and remote-VTEP reachability verification.

## Cross-cluster IPAM split

The two OpenShift clusters do not share an OVN IPAM database, so automatic allocations are split while both sides still participate in one MAC-VRF:

```text
SW1: gateway 10.50.50.1
     infrastructure 10.50.50.0/28
     reserves 10.50.50.128/25

C1:  gateway 10.50.50.129
     infrastructure 10.50.50.128/28
     reserves 10.50.50.0/25
```

Both clusters use `10.50.50.0/24`, VNI 5050 and RT `65000:5050`.

## External provider/DC fabric mode

A real EVPN-capable provider or DC fabric remains supported:

```bash
export EVPN_FABRIC_MODE='external'
export EVPN_FABRIC_CONFIRMED='true'
export EVPN_PEER_ASN='65000'
export EVPN_SW1_PEER='<PHX-EVPN-PEER-IP>'
export EVPN_C1_PEER='<ASH-EVPN-PEER-IP>'
make deploy
```

This mode retains the inventory-defined private dummy VTEPs because the external fabric is expected to route that VTEP CIDR.

## Legacy nested-carrier mode

`EVPN_FABRIC_MODE=self-managed-vxlan` is retained only for diagnostics. It creates `evpn-transit0`, VNI4090 and UDP/4790. The tested PHX↔ASH path did not carry that outer tunnel, so this mode is not the default and should not be selected for the current lab without a network change.

## Verification

After a successful deployment:

```bash
oc get vtep evpn-vtep
oc get frrconfiguration -n openshift-frr-k8s
oc get routeadvertisements evpn-vm-routes
oc get clusteruserdefinednetwork evpn-vm-net

FRR_POD=$(oc get pod -n openshift-frr-k8s -o name | grep 'pod/frr-k8s-' | grep -v statuscleaner | head -1 | cut -d/ -f2)
oc exec -n openshift-frr-k8s "$FRR_POD" -c frr -- vtysh -c 'show bgp summary'
oc exec -n openshift-frr-k8s "$FRR_POD" -c frr -- vtysh -c 'show bgp l2vpn evpn summary'
oc exec -n openshift-frr-k8s "$FRR_POD" -c frr -- vtysh -c 'show bgp l2vpn evpn route type 2'
```

The EVPN peer must be negotiated, not `NoNeg`, `Connect`, or `Active`.

## Security

BGP TCP-MD5 is enabled by default for the lab-managed fabric-router sessions. The fabric-router password is never written to the non-secret fabric-router ownership artifact. VXLAN UDP/4789 itself is not encrypted; use a secured underlay for production WAN deployments.
