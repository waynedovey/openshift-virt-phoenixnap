# Operations

## Secrets

Never commit credentials. Copy `.env.example` to `.env`, fill the values locally, and `source .env`.

Required:

- `PNAP_CLIENT_ID`
- `PNAP_CLIENT_SECRET`
- `CLOUDFLARE_API_TOKEN`
- `RHACM_KUBECONFIG`
- `OPENSHIFT_PULL_SECRET_FILE`

The SSH public key defaults to `~/.ssh/id_ed25519.pub`.

## Deployment order

```bash
make bootstrap
source .env
make validate
make preflight
make prepare-hub
make private-networks
make bgp              # optional phoenixNAP IPv4 BGP only
make provision
make dns
make install
make virt
make nmstate
make vm-l2
make evpn-fabric-router          # only provisions when EVPN_FR_AUTO_PROVISION=true
make evpn
make status
```

Or run all safe stages:

```bash
make deploy
```

`make deploy` uses `EVPN_FABRIC_MODE=fabric-router` by default. It points both OpenShift FRR-K8s instances at an external FRR EVPN fabric router, reconciles the public SNO IPv4 addresses as unmanaged VTEPs, creates the EVPN CUDN and `RouteAdvertisements`, waits for base BGP and L2VPN EVPN negotiation, and verifies direct routing to the remote public VTEP.

Automatic fabric-router provisioning is opt-in because it adds a third billable hourly server:

```bash
export EVPN_FR_AUTO_PROVISION=true
make deploy
```

Alternatively keep `EVPN_FR_AUTO_PROVISION=false` and supply `EVPN_FR_ADDRESS` plus `EVPN_FR_BGP_PASSWORD`.

## Destruction

```bash
make destroy
```

The destroy target requires explicit confirmation internally. It removes the two cluster namespaces/ManagedClusters, Cloudflare records, only phoenixNAP BGP peer groups recorded as created by this project, and deprovisions matching hourly servers. If `artifacts/evpn/fabric-router.yml` records a repository-owned auto-provisioned fabric router, destroy verifies the server ID/hostname and removes that third hourly server too.

## Rerun and teardown resilience

`make deploy` is designed to recover from a partially destroyed lab. If the RHACM hub no longer has an OpenShift 4.22 `ClusterImageSet`, it automatically creates `openshift-4.22.0-auto` using `quay.io/openshift-release-dev/ocp-release:4.22.0-x86_64`. Set `OPENSHIFT_RELEASE_IMAGE` to override that pullspec.

`make destroy` deletes the cluster-scoped RHACM `ManagedCluster` before deleting the per-cluster namespace and uses `oc` for that cluster-scoped deletion to avoid Python dynamic-client discovery failures. Missing servers, DNS records, namespaces, and ManagedCluster resources are treated idempotently.
