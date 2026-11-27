# Operational Runbook: Payments API Database Emergency Failover

**Runbook ID:** RB-PAY-008  
**Target Service:** Payments API (`svc-payments-api`)  
**Criticality:** Tier-1  
**Author:** Liam Murphy (Staff SRE)

---

## 1. Trigger Conditions
- Database P99 query latency exceeds 5,000ms for > 3 consecutive minutes.
- Active PostgreSQL replication lag exceeds 60 seconds on primary instance.
- Storage engine corruption or hardware read-only panic state.

## 2. Emergency Failover Procedure
1. Verify replica sync health:
   ```bash
   patronictl -c /etc/patroni.yml topology
   ```
2. Trigger graceful failover to designated standby replica:
   ```bash
   patronictl -c /etc/patroni.yml failover nova-postgres-cluster --candidate nova-pg-02 --force
   ```
3. Restart local PgBouncer connection pool sidecars to refresh DNS endpoints:
   ```bash
   kubectl rollout restart deployment/payments-api -n production
   ```
4. Verify traffic resumption and error rate drop in Datadog/Grafana dashboard `Payments Core V2`.
