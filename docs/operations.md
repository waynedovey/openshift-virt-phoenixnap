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
make storage
make virt
make nmstate
make vm-l2
make evpn
make test-vms
make status
```

Or run all safe stages:

```bash
make deploy
```

`make deploy` configures LVM Storage before OpenShift Virtualization. It stages but skips EVPN and the RHEL 9 cross-site proof VMs until `evpn.apply=true` and the external fabric is confirmed.

## Destruction

```bash
make destroy
```

The destroy target requires explicit confirmation internally. It removes the two cluster namespaces/ManagedClusters, Cloudflare records, only phoenixNAP BGP peer groups recorded as created by this project, and deprovisions matching hourly servers with their automatically purchased IP blocks.
