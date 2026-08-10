# EVPN activation

The repository stages the OpenShift 4.22 EVPN objects but keeps `evpn.apply: false` initially.

Before enabling it, you need an EVPN-capable external fabric reachable from each SNO. That fabric must carry the EVPN address family and VXLAN traffic between PHX and ASH. Populate:

```yaml
evpn:
  apply: true
  fabric_confirmed: true
  peer_asn: 65000
  peers:
    sw1: 203.0.113.10
    c1: 203.0.113.20
```

The playbook then:

1. Enables the FRR routing capability and OVN route advertisements.
2. Reuses Kubernetes NMState installed by the base VM-L2 workflow.
3. Adds a dummy VTEP IP to the SNO node.
4. Creates an FRRConfiguration to the external EVPN peer.
5. Creates the unmanaged VTEP object.
6. Creates RouteAdvertisements.
7. Creates a primary Layer2 EVPN ClusterUserDefinedNetwork using `10.50.50.0/24`, VNI `5050`, RT `65000:5050`.

## IPAM warning

The two OpenShift clusters do not share an IPAM database. A common subnet therefore does not guarantee coordinated allocation. For a real cross-cluster VM mobility design, use controlled static/reserved addressing or an external/coordinated IPAM approach so the same address is never assigned independently at both sites.

## Transport warning

The VTEP range `10.255.50.0/24` is an overlay underlay-routing design choice for this lab. Your external fabric must route these VTEP addresses between sites and permit UDP/4789 as required by the EVPN/VXLAN data plane.


## Relationship to phoenixNAP private networks

The `ocp-sw1-vm-l2` and `ocp-c1-ash-vm-l2` private VLANs are site-local physical segments for
OpenShift Virtualization Localnet attachment. They do not stretch Layer2 between PHX and ASH.
The EVPN/VXLAN design is still the mechanism intended to carry the portable `10.50.50.0/24`
VM network between sites. phoenixNAP BGP peering itself remains public-IP based.
