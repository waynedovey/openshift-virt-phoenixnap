# LVM Storage on the SNO nodes

Each phoenixNAP SNO has two local NVMe devices. OpenShift is installed on one NVMe; the lab uses the other **completely unused whole disk** for Red Hat LVM Storage.

The automation deliberately does not repartition or shrink the RHCOS installation disk.

## Safety model

On first apply, the `openshift_lvm_storage` role enters the host through `oc debug node/... -- chroot /host` and accepts a device only when all of the following are true:

- it is a writable whole NVMe/SCSI/virtio disk;
- it has no child partitions;
- it has no filesystem type;
- it has no partition-table type;
- it has no mount points;
- `wipefs` reports no signatures;
- it has a stable `/dev/disk/by-path/...` symlink;
- its configured thin-pool percentage yields at least 600 GiB of physical thin-pool capacity.

Exactly **one** safe candidate meeting that capacity floor must be found. If zero or more than one candidate exists, deployment stops without wiping anything.

The selected stable device path is pinned into the `LVMCluster`. Subsequent runs reuse that path instead of trying to rediscover an already-initialized LVMS disk.

`forceWipeDevicesAndDestroyAllData` is `false` by default.

## Default layout

```text
RHCOS/OpenShift disk        dedicated LVMS disk
~931 GiB                    ~931 GiB raw
                               |
                               +-- vg1
                                   |
                                   +-- thin-pool-1 (90%)
                                       ~838 GiB physical pool
                                       overprovisionRatio: 1
```

The generated storage class is:

```text
lvms-vg1
```

The device class is declared as the Kubernetes default. The automation waits for `lvms-vg1` to exist before clearing any previous Kubernetes default, avoiding a window with no default StorageClass. It also marks `lvms-vg1` as the OpenShift Virtualization default storage class for this lab.

## Run only the storage stage

```bash
make storage
```

Verify both sites:

```bash
for SITE in sw1 c1; do
  echo "===== ${SITE} ====="
  KUBECONFIG="artifacts/kubeconfigs/${SITE}.kubeconfig" \
    oc get lvmcluster -n openshift-lvm-storage
  KUBECONFIG="artifacts/kubeconfigs/${SITE}.kubeconfig" \
    oc get sc lvms-vg1
  KUBECONFIG="artifacts/kubeconfigs/${SITE}.kubeconfig" \
    oc get storageprofile lvms-vg1 -o yaml
 done
```

## SNO implication

LVMS is local, node-attached storage. It is a good fit for this single-node lab, but RWO local VM disks are not shared storage and do not provide cross-node live migration if the cluster is later expanded to multiple nodes.
