# SAP HANA High Availability Test Cases

## Supported Topologies

All test cases support the following HANA System Replication topologies:

| Topology | Description | Configuration |
|----------|-------------|---------------|
| **Scale-Up** | Classic two-node HSR with a single primary and secondary node. Each node runs one HANA instance. | `database_scale_out: false` (default) |
| **Scale-Out HSR** | Multi-node HSR with primary and secondary sites. Each site contains multiple worker nodes. A majority maker node provides quorum without running HANA. | `database_scale_out: true` |

### Scale-Up Topology

In a scale-up deployment, the cluster consists of two nodes:

- **Primary node**: Runs the active HANA instance serving application requests.
- **Secondary node**: Runs a standby HANA instance receiving system replication data.

Validation checks use exact node identity (e.g., `new_primary == old_secondary`).

### Scale-Out HSR Topology

In a scale-out HSR deployment, the cluster consists of multiple nodes organized into two sites plus a majority maker:

- **Primary site nodes**: List of worker nodes on the primary site (includes the master nameserver node).
- **Secondary site nodes**: List of worker nodes on the secondary site.
- **Majority maker node**: A lightweight node that participates in quorum voting but does not run HANA. Required for odd-node-count fencing decisions.

Validation checks use **site membership** instead of exact node identity (e.g., `new_primary in old_secondary_site_nodes`). This is because any worker node on the promoted site can become the new master nameserver after failover.




---

## Test Case Overview

The framework supports both shared HA scenarios and scale-out-only scenarios. For scale-out HSR, failover validation uses site membership checks instead of exact node identity, and worker-node scenarios validate site-level stability without requiring a site promotion.

| Test Case | Type | Description | More Info |
|-----------|-----------|-------------| --------- |
| HA Parameters Validation | Configuration | The HA parameter validation test validates HA configuration including Corosync settings, Pacemaker resources, SBD device configuration, and HANA system replication setup. Supports topology-aware validation via SAPHanaSR, SAPHanaSR-angi, and SAPHanaSR-ScaleOut providers. | [ha-config.yml](../../src/roles/ha_db_hana/tasks/ha-config.yml) |
| Azure Load Balancer | Configuration | The Azure LB configuration test validates Azure Load Balancer setup including health probe configuration, backend pool settings, load balancing rules, and frontend IP configuration. | [azure-lb.yml](../../src/roles/ha_db_hana/tasks/azure-lb.yml) |
| Resource Migration | Failover | The Resource Migration test validates planned failover scenarios by executing controlled resource movement between HANA nodes. It performs a graceful migration of the primary HANA resources to the secondary node, verifies proper role changes, ensures cluster stability throughout the transition, and validates complete data synchronization after migration. In scale-out HSR, validates that the new primary belongs to the former secondary site. | [resource-migration.md](./pseudocode/resource-migration.md) |
| Primary Node Crash | Failover | The Primary Node Crash test simulates cluster behavior when the HANA database is stopped on the primary node. It verifies automatic failover to the secondary node, monitors system replication status, and confirms service recovery without data loss. In scale-out HSR, validates that a node from the secondary site is promoted to primary. | [node-crash.md](./pseudocode/node-crash.md) |
| Block Network | Network | The Block Network test validates cluster behavior during network partition scenarios originating from the primary master node by implementing iptables rules to block communication between primary and secondary HANA nodes. In scale-out HSR, this scenario no longer depends on `PRIORITY_FENCING_DELAY` and validates site-level outcomes with membership checks. | [block-network.md](./pseudocode/block-network.md) |
| Secondary Block Network | Network | Scale-out-only scenario that blocks communication from the secondary master node. It validates that the primary site retains the primary role, the secondary site is isolated correctly, and the cluster returns to a stable replicated state after network restoration. | [block-network.md](./pseudocode/block-network.md) |
| Primary Index Server Crash | Service | The Primary Index Server Crash test validates high availability behavior by forcefully terminating the HANA index server process on the primary node. This simulates a critical service failure, triggering automatic failover to the secondary node. In scale-out HSR, validates that the new primary is from the secondary site. | [crash-index.md](./pseudocode/crash-index.md) |
| Primary Worker Index Server Crash | Service | Scale-out-only scenario that forcefully terminates `hdbindexserver` on a non-master worker in the primary site. It validates that the site-level master roles remain stable while the worker failure is absorbed and the cluster returns to a healthy replicated state. | [crash-index.md](./pseudocode/crash-index.md) |
| Primary Node Kill | Process | The Primary Node Kill test validates cluster behavior by forcefully terminating all HANA processes on the primary node using SIGKILL signal. This simulates an abrupt service failure, triggering automatic failover to the secondary node. In scale-out HSR, validates site-level promotion rather than exact node swap. | [node-kill.md](./pseudocode/node-kill.md) |
| Primary Worker Node Kill | Process | Scale-out-only scenario that forcefully terminates HANA processes on a non-master worker in the primary site. It validates that primary and secondary master roles remain stable while the worker node recovers. | [node-kill.md](./pseudocode/node-kill.md) |
| Primary Echo B | System | The Primary Echo B test simulates an immediate system crash on the primary HANA node by executing the 'echo b' command to trigger an abrupt reboot without proper shutdown. In scale-out HSR, validates that a secondary site node takes over as primary. | [echo-b.md](./pseudocode/echo-b.md) |
| Primary Worker Echo B | System | Scale-out-only scenario that simulates an immediate system crash on a non-master worker in the primary site. It validates that site-level master roles remain stable and that the cluster returns to a healthy replicated state after worker recovery. | [echo-b.md](./pseudocode/echo-b.md) |
| Secondary Index Server Crash | Service | The Secondary Index Server Crash test simulates failure of the HANA index server process on the secondary node. It validates that the primary node continues normal operation while verifying the cluster's ability to handle secondary failures, tests automatic recovery mechanisms, and ensures system replication resumes properly after service restoration. In scale-out HSR, validates that the primary site retains its role. | [crash-index.md](./pseudocode/crash-index.md) |
| Secondary Worker Index Server Crash | Service | Scale-out-only scenario that forcefully terminates `hdbindexserver` on a non-master worker in the secondary site. It validates that the primary site retains the primary role and that the cluster returns to a stable replicated state after worker recovery. | [crash-index.md](./pseudocode/crash-index.md) |
| Secondary Node Kill | Process | The Secondary Node Kill test examines cluster resilience by forcefully terminating HANA processes on the secondary node using the kill -9 signal. The test validates that the primary node maintains normal operation while the secondary node undergoes recovery. In scale-out HSR, validates site-level stability. | [node-kill.md](./pseudocode/node-kill.md) |
| Secondary Worker Node Kill | Process | Scale-out-only scenario that forcefully terminates HANA processes on a non-master worker in the secondary site. It validates that the primary site retains the primary role and that the cluster recovers without a site promotion. | [node-kill.md](./pseudocode/node-kill.md) |
| Secondary Echo B | System | The Secondary Echo B test simulates an uncontrolled system crash on the secondary HANA node by executing the 'echo b' command. The test validates that the primary node maintains operation and system replication resumes correctly. In scale-out HSR, validates that primary site nodes retain their role. | [echo-b.md](./pseudocode/echo-b.md) |
| Secondary Worker Echo B | System | Scale-out-only scenario that simulates an uncontrolled system crash on a non-master worker in the secondary site. It validates that the primary site remains primary and the cluster returns to a stable replicated state after worker recovery. | [echo-b.md](./pseudocode/echo-b.md) |
| Filesystem Freeze | Storage | The Filesystem Freeze test validates cluster behavior when the primary node's filesystem becomes unresponsive. It simulates a storage issue by freezing the ANF filesystem on the primary node, triggering automatic failover. In scale-out HSR, validates that a secondary site node is promoted. | [fs-freeze.md](./pseudocode/fs-freeze.md) |
| SBD Fencing | Fencing | Validates cluster fencing mechanism by killing the SBD inquisitor process on the primary node. Tests proper fence detection, node isolation, and automated failover. In scale-out HSR, validates site-level failover behavior. | [sbd-fencing.md](./pseudocode/sbd-fencing.md) |
| Block NFS IP on Primary Master Node | Storage | Scale-out-only scenario that blocks the `/hana/shared` NFS server IP from the primary master node. This causes the HANA resource monitor to fail and validates failover to the secondary site. | [block-hana-shared.yml](../../src/roles/ha_db_hana/tasks/block-hana-shared.yml) |
