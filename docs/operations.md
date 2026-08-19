# Operations

## Secrets

Never commit credentials. Copy `.env.example` to `.env`, fill the values
locally, and `source .env`.

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
make evpn-router      # embedded FRR route-server pod; no third server
make evpn             # also runs evpn-router before OpenShift EVPN reconciliation
make test-vms
make status
```

Or run all stages:

```bash
make deploy
```

The default is `EVPN_FABRIC_MODE=embedded-router`. The route-server function is
a pod on the existing SW1 SNO; the two OpenShift public VTEPs still exchange
VXLAN UDP/4789 directly.

## Migrate and remove an existing `evpn-fr` server

Run this **from the checkout that still has its `artifacts/` directory**:

```bash
make evpn-migrate
```

The target deploys and probes the embedded listener before changing the working
OpenShift peers. It then verifies BGP, L2VPN EVPN, the remote Type-3 route and a
remote VTEP before the repository-owned third phoenixNAP server is deleted.

If you use a fresh repo ZIP, copy your old `artifacts/` directory into it first;
without `artifacts/evpn/fabric-router.yml`, the repo deliberately refuses to
guess which server to delete.

To defer retirement:

```bash
export EVPN_RETIRE_LEGACY_FR_SERVER=false
make evpn-migrate
```

Later:

```bash
unset EVPN_RETIRE_LEGACY_FR_SERVER
make evpn-retire-legacy
```

## Destruction

```bash
make destroy
```

The normal destroy workflow removes the two SNO servers and other repository-
owned resources. The old fabric-router destroy helper is retained only so a
legacy `artifacts/evpn/fabric-router.yml` ownership record can be cleaned up
safely; current deployments never provision a third EVPN server.
