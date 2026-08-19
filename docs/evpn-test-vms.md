# RHEL 9 EVPN proof VMs

The lab creates one RHEL 9 VM per site to prove the shared EVPN Layer-2 segment once the selected EVPN fabric is active.

## VMs

```text
PHX / sw1                     ASH / c1
rhel9-sw1                     rhel9-c1
10.50.50.50/24                10.50.50.150/24
02:50:50:00:00:11             02:50:50:00:00:21
       \                         /
        +---- EVPN VNI 5050 ----+
              10.50.50.0/24
```

The EVPN CUDN is a **primary** OpenShift 4.22 Layer2 network, so OVN IPAM remains enabled with `lifecycle: Persistent` and the shared `10.50.50.0/24` subnet. Because SW1 and C1 have independent IPAM databases, each site reserves every workload address except its proof-VM address. SW1 therefore has only `10.50.50.50` available and C1 only `10.50.50.150`. The VM uses DHCP on the primary `l2bridge` interface; OVN supplies that deterministic address and persists the allocation across VM reboots and migration.

Each VM has:

- one and only one network interface;
- the primary EVPN `ClusterUserDefinedNetwork` using KubeVirt `l2bridge` binding;
- a deterministic static guest IP and MAC;
- a 40 GiB RHEL 9 root DataVolume on `lvms-vg1`;
- 2 vCPU and 4 GiB RAM by default;
- the Red Hat `rhel9` DataSource from `openshift-virtualization-os-images`;
- a small systemd service that continuously pings the peer VM and writes the result to the serial console;
- an explicitly enabled `sshd`;
- console/password login for `cloud-user`, with lab default password `redhat`;
- the repository SSH public key installed for `cloud-user`.

For a non-default lab password, set it before creating/recreating the proof VMs:

```bash
export EVPN_TEST_VM_PASSWORD='choose-a-lab-password'
make test-vms
```

The password is intentionally a lab convenience and becomes part of NoCloud user-data. Do not reuse a production credential.

## Important gate

The two phoenixNAP private Localnet VLANs are separate site-local broadcast domains. They cannot prove `10.50.50.0/24` cross-site connectivity.

In the default `embedded-router` mode, the proof VMs are created when EVPN and `evpn_test_vms` are enabled. For an externally managed fabric, `EVPN_FABRIC_CONFIRMED=true` is additionally required.

The proof VMs attach only to the primary `evpn-vm-net` CUDN; they do not use `pnap-vm-localnet`.

## Run

After the embedded EVPN control plane is ready:

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
  KUBECONFIG="playbooks/artifacts/kubeconfigs/${SITE}.kubeconfig" \
    oc get vm,vmi,dv -n evpn-vms
 done
```

The proof VMs are automatically recreated when the repository's `bootstrap_revision` changes, because cloud-init first-boot settings such as the account password and `sshd` enablement must run against a fresh proof root disk. This recreation touches only the disposable proof VM/DataVolume, not the EVPN CUDN or embedded FRR route server.

Open either serial console:

```bash
KUBECONFIG=playbooks/artifacts/kubeconfigs/sw1.kubeconfig \
  virtctl console -n evpn-vms rhel9-sw1
```

or:

```bash
KUBECONFIG=playbooks/artifacts/kubeconfigs/c1.kubeconfig \
  virtctl console -n evpn-vms rhel9-c1
```

Console credentials:

```text
login: cloud-user
password: redhat
```

If `EVPN_TEST_VM_PASSWORD` was set when `make test-vms` ran, use that value instead. SSH key authentication for `cloud-user` is also configured, and `sshd` is explicitly enabled.

The VM writes a line every 15 seconds similar to:

```text
[EVPN-PROOF] ... rhel9-sw1 (10.50.50.50) -> 10.50.50.150
64 bytes from 10.50.50.150: icmp_seq=1 ...
```

That is the intended simple demonstration that the same Layer-2 VM network is reachable between the two OpenShift clusters.
