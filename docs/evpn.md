# OpenShift 4.22 two-site EVPN

## Default topology: embedded route server, no third phoenixNAP server

The default lab uses the public SNO addresses as OpenShift unmanaged VTEPs and
runs a small FRR EVPN route-server pod on the existing SW1 SNO. The pod is
control-plane only. VM traffic is still direct PHX↔ASH VXLAN UDP/4789.

```text
                    SW1 / hosting SNO
                    <SW1-public-IP>
                    AS65011
                         |
                         | TCP/1179 + TCP-MD5
                         v
               FRR route-server pod / AS65000
               hostNetwork on SW1
                         ^
                         | TCP/1179 + TCP-MD5
                         |
                    C1 / remote SNO
                    <C1-public-IP>
                    AS65021

     SW1 public VTEP <======== UDP/4789 ========> C1 public VTEP
                         VNI 5050 / RT 65000:5050
```

OpenShift FRR-K8s is used as an active BGP client. Both SNOs dial the hosting
SNO public IP directly on TCP/1179, and each `FRRConfiguration` sets
`sourceaddress` to that site's public VTEP address. The BGP control path is
therefore NAT-free, which is required for the TCP-MD5 password to validate
against the same IP endpoint tuple on both sides. The route server accepts only
the two known public VTEP /32 sources and preserves the originating EVPN next
hop when it re-advertises routes.

The route-server Deployment uses `hostNetwork: true` on the selected SNO. The
ClusterIP Service is health/discovery only and is not in the BGP path.
It does **not** terminate VXLAN and it is not in the VM data path.

## Why not direct FRR-K8s ↔ FRR-K8s?

Live testing showed the OpenShift FRR-K8s `bgpd` process is run without a
passive BGP listener, so each leaf is an active dialer. Pointing the two leaves
directly at each other therefore does not provide a passive endpoint. The
embedded route-server retains the required passive rendezvous function without
paying for a third phoenixNAP server.

## Migration from the old `evpn-fr` server

Use the current working checkout so `artifacts/evpn/fabric-router.yml` is still
present. Then run:

```bash
make evpn-migrate
```

The migration is deliberately fail-safe:

1. Deploy the embedded FRR route-server pod on the configured SNO.
2. Verify the live FRR-K8s CRD supports `neighbor.port` and `neighbor.sourceaddress`.
3. Verify the route-server listener exists on the hosting SNO.
4. Establish authenticated BGP canaries from both SNO public VTEP addresses to the hosting SNO public IP on TCP/1179.
5. Only then repoint both OpenShift FRR-K8s peers to the embedded route server.
6. Require base BGP and L2VPN EVPN to establish.
7. Require the remote Type-3 VTEP route and `Remote VTEPs >= 1` on both SNOs.
8. Only after those checks pass, deprovision the repository-owned legacy
   phoenixNAP `evpn-fr` server.

If any check fails before step 8, the legacy server ownership artifact remains
and the repo does not intentionally deprovision it.

To keep the old server temporarily even after a successful migration:

```bash
export EVPN_RETIRE_LEGACY_FR_SERVER=false
make evpn-migrate
```

Later, restore the default and run:

```bash
unset EVPN_RETIRE_LEGACY_FR_SERVER
make evpn-retire-legacy
```

Automatic retirement requires the repository ownership file. If you move to a
fresh checkout, copy the existing `artifacts/` directory first. The code will
not guess a phoenixNAP server ID.

## Configuration

Defaults:

```bash
export EVPN_FABRIC_MODE='embedded-router'
export EVPN_EMBEDDED_ROUTER_SITE='sw1'
export EVPN_EMBEDDED_ROUTER_ASN='65000'
export EVPN_EMBEDDED_ROUTER_PORT='1179'
export EVPN_RETIRE_LEGACY_FR_SERVER='true'
```

The image defaults to `quay.io/frrouting/frr:10.4.1` and can be overridden with
`EVPN_EMBEDDED_ROUTER_IMAGE`.

## OpenShift objects

On the hosting SNO the repo creates:

- `Namespace/evpn-fabric-system`
- `ServiceAccount/evpn-route-server`
- privileged SCC RoleBinding
- `Secret/evpn-route-server-config`
- `Service/evpn-route-server` for the hosting leaf
- `Deployment/evpn-route-server` with hostNetwork TCP/1179 for both leaves

On each SNO the repo creates/reconciles:

- CNO FRR/RouteAdvertisements prerequisites
- `Namespace/evpn-vms`
- `NNCP/evpn-vtep` with the old dummy VTEP absent
- `VTEP/evpn-vtep` using the SNO public `/32`
- `Secret/evpn-bgp-auth`
- `FRRConfiguration/evpn-fabric`
- `ClusterUserDefinedNetwork/evpn-vm-net`
- `RouteAdvertisements/evpn-vm-routes`

## VM network and deterministic IPAM

Both sites use the same stretched `10.50.50.0/24`, VNI 5050 and RT
`65000:5050`. A primary Layer2 CUDN keeps OVN IPAM enabled with
`lifecycle: Persistent`. The independent site allocators are constrained so the
proof VMs get:

```text
SW1: rhel9-sw1 = 10.50.50.50/24  MAC 02:50:50:00:00:11
C1:  rhel9-c1  = 10.50.50.150/24 MAC 02:50:50:00:00:21
```

## External provider/DC fabric mode

A real EVPN-capable external fabric remains supported:

```bash
export EVPN_FABRIC_MODE='external'
export EVPN_FABRIC_CONFIRMED='true'
export EVPN_PEER_ASN='65000'
export EVPN_SW1_PEER='<PHX-EVPN-PEER-IP>'
export EVPN_C1_PEER='<ASH-EVPN-PEER-IP>'
make evpn
```

## Legacy nested-carrier mode

`EVPN_FABRIC_MODE=self-managed-vxlan` is retained for diagnostics only. It
creates the old `evpn-transit0` VNI4090/UDP4790 carrier. That path did not work
on the tested PHX↔ASH underlay and is not the default.

## Verification

```bash
for SITE in sw1 c1; do
  K="playbooks/artifacts/kubeconfigs/${SITE}.kubeconfig"
  FRR=$(oc --kubeconfig="$K" -n openshift-frr-k8s get pods -o name \
    | grep 'frr-k8s-' | grep -v statuscleaner | head -1 | cut -d/ -f2)

  echo "===== $SITE ====="
  oc --kubeconfig="$K" -n openshift-frr-k8s exec "$FRR" -c frr -- \
    vtysh -c 'show bgp l2vpn evpn summary'
  oc --kubeconfig="$K" -n openshift-frr-k8s exec "$FRR" -c frr -- \
    vtysh -c 'show evpn vni'
  oc --kubeconfig="$K" -n openshift-frr-k8s exec "$FRR" -c frr -- \
    vtysh -c 'show bgp l2vpn evpn route type 2'
done
```

For the proven lab, VNI 5050 should show two MACs, two ARPs and one remote VTEP
once both proof VMs are running.
