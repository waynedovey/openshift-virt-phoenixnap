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
                 |                               |
                 +------ external EVPN ----------+
                        shared 10.50.50.0/24
                        VNI 5050 / RT 65000:5050
```

Cloudflare publishes unproxied A records for API, API-int, wildcard ingress and the SNO node under `digitaldovey.net`.

## Network separation

The OpenShift pod and service CIDRs remain distinct between clusters. Only the VM CUDN is intended to be shared through EVPN.

| Item | SW1 / PHX | C1 / ASH |
|---|---|---|
| Cluster | `sw1.digitaldovey.net` | `c1.digitaldovey.net` |
| Pod CIDR | `10.128.0.0/14` | `10.132.0.0/14` |
| Service CIDR | `172.30.0.0/16` | `172.31.0.0/16` |
| Local BGP ASN | `65011` | `65021` |
| VTEP address | `10.255.50.11/32` | `10.255.50.21/32` |
| Shared VM subnet | `10.50.50.0/24` | `10.50.50.0/24` |

## Important EVPN boundary

The phoenixNAP BGP Peer Group API is automated because it is useful for standard routed BGP. It is **not** treated as an EVPN L2VPN service. The OpenShift EVPN tasks are gated behind explicit external-fabric confirmation and peer addresses.
