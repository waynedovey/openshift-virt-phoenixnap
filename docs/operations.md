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
make bgp
make provision
make dns
make install
make virt
make status
```

Or run all safe stages:

```bash
make deploy
```

`make deploy` enables the OpenShift EVPN prerequisites on both SNO clusters and, in the default `self-managed-vxlan` mode, builds the PHX↔ASH transit automatically. It then configures `FRRConfiguration`, the EVPN CUDN and `RouteAdvertisements`, waits for base BGP and MP-BGP EVPN establishment, and verifies that each site learns the remote VTEP route. Use `EVPN_FABRIC_MODE=external` only when connecting to a real provider/DC EVPN fabric.

## Destruction

```bash
make destroy
```

The destroy target requires explicit confirmation internally. It removes the two cluster namespaces/ManagedClusters, Cloudflare records, only phoenixNAP BGP peer groups recorded as created by this project, and deprovisions matching hourly servers with their automatically purchased IP blocks.

## Rerun and teardown resilience

`make deploy` is designed to recover from a partially destroyed lab. If the RHACM hub no longer has an OpenShift 4.22 `ClusterImageSet`, it automatically creates `openshift-4.22.0-auto` using `quay.io/openshift-release-dev/ocp-release:4.22.0-x86_64`. Set `OPENSHIFT_RELEASE_IMAGE` to override that pullspec.

`make destroy` deletes the cluster-scoped RHACM `ManagedCluster` before deleting the per-cluster namespace and uses `oc` for that cluster-scoped deletion to avoid Python dynamic-client discovery failures. Missing servers, DNS records, namespaces, and ManagedCluster resources are treated idempotently.
