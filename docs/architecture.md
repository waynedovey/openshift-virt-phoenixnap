# Architecture

## Target

Two independent OpenShift 4.22 Single Node OpenShift clusters run on phoenixNAP Bare Metal Cloud and are managed from the existing RHACM hub. A small FRR EVPN route-server pod runs on the existing SW1 SNO, so the design needs only the two OpenShift servers.

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
          public/VTEP                      public/VTEP
          125.253.82.93                    103.67.202.133
                 |                               |
       loopback TCP/1179                 TCP/1179 to SW1
                 |                               |
          FRR route-server pod <----------------+
          on SW1 / AS65000
                 |                               |
                 +---- VXLAN VNI5050 / UDP4789--+
                         shared 10.50.50.0/24
                         RT 65000:5050
```

The embedded route server carries BGP control-plane messages only. VXLAN data remains direct between PHX and ASH.

## Network separation

The OpenShift pod and service CIDRs remain distinct between clusters. Only the EVPN VM CUDN is shared.

| Item | SW1 / PHX | C1 / ASH |
|---|---|---|
| Cluster | `sw1.digitaldovey.net` | `c1.digitaldovey.net` |
| Pod CIDR | `10.128.0.0/14` | `10.132.0.0/14` |
| Service CIDR | `172.30.0.0/16` | `172.31.0.0/16` |
| Local BGP ASN | `65011` | `65021` |
| Public/VTEP | `125.253.82.93/32` | `103.67.202.133/32` |
| EVPN gateway | `10.50.50.1` | `10.50.50.129` |
| Shared VM subnet | `10.50.50.0/24` | `10.50.50.0/24` |

## EVPN fabric boundary

The tested phoenixNAP BGP Peer Group service is not used as the OpenShift EVPN fabric because the live sessions negotiated IPv4 unicast but not L2VPN EVPN. Direct OpenShift FRR-K8s peering is also unsuitable because the managed `bgpd` process operates as an active client rather than a passive BGP listener.

The embedded FRR pod retains that passive rendezvous function without a third phoenixNAP server. Both leaves reach it directly at the hosting SNO public IP on TCP/1179. Both leaves pin their BGP source to their public VTEP address. The BGP path is NAT-free so TCP-MD5 authentication sees the same IP endpoint tuple on both ends. The embedded FRR process accepts password-protected dynamic eBGP clients only from the two known public VTEP /32s and re-advertises EVPN routes between AS65011 and AS65021 while preserving the originating public VTEP next-hop.

The previous nested VNI4090/UDP4790 carrier is retained only as a legacy diagnostic mode. The default design uses OpenShift's native VNI5050 VXLAN directly over UDP/4789 between the public SNO VTEPs.
