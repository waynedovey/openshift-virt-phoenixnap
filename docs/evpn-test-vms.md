# RHEL 9 EVPN proof VMs

The lab stages one RHEL 9 VM per site to prove the shared EVPN Layer-2 segment once the external EVPN fabric is real and enabled.

## VMs

```text
PHX / sw1                     ASH / c1
rhel9-sw1                     rhel9-c1
10.50.50.11/24                10.50.50.21/24
02:50:50:00:00:11             02:50:50:00:00:21
       \                         /
        +---- EVPN VNI 5050 ----+
              10.50.50.0/24
```

The EVPN CUDN uses the OpenShift 4.22 Layer2 mode with `subnets` omitted. That makes addressing manual rather than allowing each independent cluster to allocate from the same pool. The VM therefore receives its site-specific `10.50.50.x/24` address through cloud-init.

Each VM has:

- one and only one network interface;
- the primary EVPN `ClusterUserDefinedNetwork` using KubeVirt `l2bridge` binding;
- a deterministic static guest IP and MAC;
- a 40 GiB RHEL 9 root DataVolume on `lvms-vg1`;
- 2 vCPU and 4 GiB RAM by default;
- the Red Hat `rhel9` DataSource from `openshift-virtualization-os-images`;
- a small systemd service that continuously pings the peer VM and writes the result to the serial console.

## Important gate

The two phoenixNAP private Localnet VLANs are separate site-local broadcast domains. They cannot prove `10.50.50.0/24` cross-site connectivity.

Therefore the proof VMs are created only when all of these are true:

```yaml
evpn:
  apply: true
  fabric_confirmed: true
  peer_asn: 65000
  peers:
    sw1: <PHX-EVPN-PEER-IP>
    c1: <ASH-EVPN-PEER-IP>

evpn_test_vms:
  apply: true
```

With EVPN disabled, `make deploy` prints an explanation and safely skips the proof VMs.

## Run

After the external fabric is configured:

```bash
make evpn
make test-vms
```

or simply:

```bash
make deploy
```

## Verify

```bash
for SITE in sw1 c1; do
  KUBECONFIG="artifacts/kubeconfigs/${SITE}.kubeconfig" \
    oc get vm,vmi,dv -n evpn-vms
 done
```

Open either serial console:

```bash
KUBECONFIG=artifacts/kubeconfigs/sw1.kubeconfig \
  virtctl console -n evpn-vms rhel9-sw1
```

or:

```bash
KUBECONFIG=artifacts/kubeconfigs/c1.kubeconfig \
  virtctl console -n evpn-vms rhel9-c1
```

The VM writes a line every 15 seconds similar to:

```text
[EVPN-PROOF] ... rhel9-sw1 (10.50.50.11) -> 10.50.50.21
64 bytes from 10.50.50.21: icmp_seq=1 ...
```

That is the intended simple demonstration that the same Layer-2 VM network is reachable between the two OpenShift clusters.
