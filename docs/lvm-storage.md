# LVM Storage on both phoenixNAP SNO clusters

The full `make deploy` workflow installs Red Hat LVM Storage on both managed SNO clusters (`sw1` and `c1`) after the managed kubeconfigs are exported and before OpenShift Virtualization is configured.

The generated StorageClass is:

```text
lvms-vg1
```

It is configured as both the Kubernetes default StorageClass and the OpenShift Virtualization default StorageClass for this lab.

## Required physical disk layout

Version 1.4.20 makes the storage requirement explicit: every dynamically selected SNO SKU must expose at least **two physical storage devices**.

```text
Disk 0                              Disk 1
RHCOS / OpenShift                   Red Hat LVM Storage
                                        |
                                        +-- vg1
                                            |
                                            +-- thin-pool-1 (90%)
```

The first device is owned by the RHACM Assisted Installer/RHCOS installation. LVMS is allowed to consume only a separate, completely unused whole device.

The current SW1 server satisfies this design and already created `lvms-vg1`. The previously selected C1 `s1.c1.small` exposed only one physical NVMe, so there was no safe second device for LVMS. Version 1.4.20 prevents that one-disk shape from being selected for a new SNO and rejects an existing one-disk server during preflight/reuse checks.

## Dynamic SKU safety policy

The default inventory now includes:

```yaml
phoenixnap:
  auto_select:
    min_ram_gb: 64
    min_cores: 6
    min_storage_devices: 2
```

`select_pnap_sku.py` parses the phoenixNAP storage description, for example:

```text
1x 1TB NVMe  -> 1 device -> rejected
2x 1TB NVMe  -> 2 devices -> accepted
```

The selector fails closed when a storage description cannot be parsed reliably.

## Replacing only an incompatible site

Do not replace a healthy peer cluster simply because another site has the wrong immutable server shape. Use the targeted workflow:

```bash
make private-networks
make replace-site SITE=c1
make deploy
```

`make replace-site SITE=c1` performs fresh capacity selection only for C1. SW1 remains a reusable existing server and is not forced onto whatever SKU happens to be in stock at replacement time.

Server replacement is destructive for the selected site. For an already-installed SNO, the workflow first deletes and waits for the old RHACM ManagedCluster namespace/install state to disappear. Only after that reset succeeds does it deprovision the phoenixNAP hardware. This ordering prevents a replacement server from inheriting a stale `ClusterDeployment.spec.installed=true` state. Run `make deploy` afterwards to perform the fresh installation.

## LVMS device discovery safety model

On first apply, `openshift_lvm_storage` enters each node using `oc debug node/... -- chroot /host` and accepts a device only when all of the following are true:

- it is a writable whole NVMe/SCSI/virtio disk;
- it has no child partitions;
- it has no filesystem type;
- it has no partition-table type;
- it has no mount points;
- `wipefs` reports no signatures;
- it has a stable `/dev/disk/by-path/...` symlink;
- its configured thin-pool percentage yields at least 600 GiB of physical thin-pool capacity.

Exactly one safe candidate must be present. If zero or multiple candidates exist, deployment stops without wiping anything.

`forceWipeDevicesAndDestroyAllData` remains `false`.

## About the earlier 300 GB OS assumption

The code does **not** attempt a day-2 shrink or repartition of the RHCOS installation disk. The safe design for this lab is a dedicated OpenShift installation device plus a separate LVMS device. If a future greenfield design needs a fixed-size root partition on the boot device, treat that as an install-time disk-layout requirement rather than modifying an installed RHCOS filesystem.

## Full deployment

```bash
make deploy
```

The storage stage is part of `site.yml`:

```text
06_wait_and_export.yml
06a_lvm_storage.yml
07_virtualization.yml
```

## Install/fix storage only on existing compatible clusters

```bash
make storage
```

## Verify

```bash
for SITE in sw1 c1; do
  echo "===== ${SITE} ====="
  KUBECONFIG="artifacts/kubeconfigs/${SITE}.kubeconfig" \
    oc get subscription,csv -n openshift-lvm-storage
  KUBECONFIG="artifacts/kubeconfigs/${SITE}.kubeconfig" \
    oc get lvmcluster -n openshift-lvm-storage
  KUBECONFIG="artifacts/kubeconfigs/${SITE}.kubeconfig" \
    oc get sc lvms-vg1
 done
```

## SNO implication

LVMS is node-local storage. It is a good fit for this SNO lab, but it does not replicate data across nodes and does not provide shared storage for cross-node live migration if the cluster is later expanded.
