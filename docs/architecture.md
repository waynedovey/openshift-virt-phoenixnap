# Architecture

## Target

Two independent OpenShift 4.22 Single Node OpenShift clusters are provisioned on phoenixNAP Bare Metal Cloud and managed from the existing RHACM hub.

```text
                         RHACM / Host Inventory
                   api.acm.sandbox5165.opentlc.com
                              |        |
                        InfraEnv    InfraEnv
                           |           |
                     iPXE script   iPXE script
                           |           |
                 +---------+-----------+---------+
                 |                               |
          phoenixNAP PHX                    phoenixNAP ASH
          cluster: sw1                     cluster: c1
          SNO / OCP 4.22                   SNO / OCP 4.22
          OpenShift Virt                   OpenShift Virt
          ASN 65011                        ASN 65021
                 |                               |
                 +== VXLAN 4090 / UDP 4790 =====+
                    192.168.254.1/30 <-> .2/30
                 |                               |
          VTEP 10.255.50.11              VTEP 10.255.50.21
                 +==== MP-BGP EVPN / VNI 5050 ==+
                        shared 10.50.50.0/24
                        RT 65000:5050
```

Cloudflare publishes unproxied A records for API, API-int, wildcard ingress and the SNO node under `digitaldovey.net`.

## Network separation

The OpenShift pod and service CIDRs remain distinct between clusters. Only the EVPN VM CUDN is shared.

| Item | SW1 / PHX | C1 / ASH |
|---|---|---|
| Cluster | `sw1.digitaldovey.net` | `c1.digitaldovey.net` |
| Pod CIDR | `10.128.0.0/14` | `10.132.0.0/14` |
| Service CIDR | `172.30.0.0/16` | `172.31.0.0/16` |
| Local BGP ASN | `65011` | `65021` |
| Transit address | `192.168.254.1/30` | `192.168.254.2/30` |
| VTEP address | `10.255.50.11/32` | `10.255.50.21/32` |
| EVPN gateway | `10.50.50.1` | `10.50.50.129` |
| Shared VM subnet | `10.50.50.0/24` | `10.50.50.0/24` |

## EVPN fabric boundary

The phoenixNAP BGP Peer Group API is still automated because it is useful for standard routed BGP, but it is **not** treated as an EVPN L2VPN service. The default lab uses a self-managed carrier VXLAN over the two public SNO addresses. This gives the two FRR-K8s instances a deterministic routed adjacency without requiring phoenixNAP to provide L2VPN EVPN.

OpenShift remains responsible for the actual EVPN control plane and VNI 5050 data plane. The carrier VXLAN is a lab convenience only; production should use a real EVPN-capable provider/DC fabric or an appropriately secured routed underlay.
