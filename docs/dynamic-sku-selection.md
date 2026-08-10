# Dynamic phoenixNAP SKU selection

The selector is intentionally policy-driven instead of using a fixed server type.

It queries the phoenixNAP Billing API at runtime:

- `/billing/v1/products?productCategory=SERVER&location=<SITE>` for server metadata and pricing plans.
- `/billing/v1/product-availability?productCategory=SERVER&location=<SITE>&minQuantity=1&showOnlyMinQuantityAvailable=true` for live stock.

A candidate must have a `HOURLY` plan with `priceUnit=HOUR`, a price strictly below the configured
`max_hourly_price`, live stock, and enough RAM/cores. The selector calculates physical cores as
`metadata.cpuCount * metadata.coresPerCpu`.

The default policy is 64 GB / 6 cores minimum and 128 GB / 8 cores preferred, with a strict
`< $0.30/hour` per-server cap. The preferred target is used to avoid picking a tiny server simply
because it is cheapest. Once candidates have equivalent sizing suitability, lower hourly cost wins.

A common SKU across PHX and CHI is preferred for repeatable lab behavior. If there is no common SKU,
per-site selections are allowed by default. Set `require_common_sku: true` to make asymmetry a hard
failure.

The selector reads the OAuth bearer token only from its process environment. It outputs sanitized JSON
containing product code, hourly price, RAM, core count and live stock; the token is never emitted.
