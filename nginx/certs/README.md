# TLS certificates (production)

Place certificate files here for `docker-compose.prod.yml`:

- `fullchain.pem`
- `privkey.pem`

Do not commit private keys. For local TLS testing, use self-signed certs or terminate TLS at a load balancer and use development `nginx.conf` on port 80 only.
