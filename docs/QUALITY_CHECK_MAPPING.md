# Quality Check ID Mapping: Legacy QualityCheck → STAF Configuration Checks

> Mapping of every check ID from the legacy
> [`SAP-on-Azure-Scripts-and-Utilities/QualityCheck`](https://github.com/Azure/SAP-on-Azure-Scripts-and-Utilities/tree/main/QualityCheck)
> to its corresponding check ID in STAF's Configuration Checks
> (`src/roles/configuration_checks/tasks/files/*.yml`).
>
> **Legend**: ✅ Direct match | 🔄 Covered by composite check | ⚠️ Approximate | ❌ No equivalent


## Table of Contents

1. [QualityCheck.json — Checks](#1-qualitycheckjson--checks-162-entries)
2. [QualityCheck.json — CheckFeatures](#2-qualitycheckjson--checkfeatures-7-entries)
3. [QualityCheck.json — VMCollectInformation](#3-qualitycheckjson--vmcollectinformation-25-entries)
4. [QualityCheck.json — VMCollectInformationAdditional](#4-qualitycheckjson--vmcollectinformationadditional-22-entries)
5. [QualityCheck.ps1 — Hard-coded Checks](#5-qualitycheckps1--hard-coded-checks-26-entries)
6. [Net-New in STAF](#6-net-new-in-staf)

## 1. QualityCheck.json — Checks (162 entries)

These are the primary validation checks from the legacy tool.

### VM / SAP General

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `DB-NET-0001` | Load Balancer timestamps | `HA-LB-001` | Load Balancer Name | 🔄 |
| `VM-0001` | Supported VM with supplied VM Role and Database | `SAP-0001` | Supported VM with supplied VM Role and Database | ✅ |
| `VM-0002` | Supported HANA scenario on VM type | `SAP-0001` | Supported VM with supplied VM Role and Database | 🔄 |
| `VM-0003` | OS/DB combination supported | `SAP-0002` | OS/DB combination supported | ✅ |
| `VM-0005` | Is Microsoft Defender installed on the VM. | `FC-0001` | EndpointProtection-DefenderLinux | 🔄 |
| `VM-0004` | Accelerated Networking Enabled | `NET-0005` | Accelerated Networking | ✅ |

### Windows HA (ASCS/DB)

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `ASCS-HA-WIN-001` | KeepAliveTime | `SAP-0019` | TCP KeepAliveTime | ✅ |
| `ASCS-HA-WIN-002` | KeepAliveInterval | `SAP-0020` | TCP KeepAliveInterval | ✅ |
| `ASCS-HA-WIN-003` | KeepAliveTime | `SAP-0019` | TCP KeepAliveTime | 🔄 |
| `ASCS-HA-WIN-004` | DisableCARetryOnInitialConnect | `SAP-0021` | DisableCARetryOnInitialConnect | ✅ |
| `ASCS-HA-WIN-004` | CrossSubNetDelay | `SAP-0022` | WSFC CrossSubNetDelay (ASCS) | ✅ |
| `ASCS-HA-WIN-005` | CrossSubNetThreshold | `SAP-0023` | WSFC CrossSubNetThreshold (ASCS) | ✅ |
| `ASCS-HA-WIN-006` | SameSubNetDelay | `SAP-0024` | WSFC SameSubNetDelay (ASCS) | ✅ |
| `ASCS-HA-WIN-007` | SameSubNetThreshold | `SAP-0025` | WSFC SameSubNetThreshold (ASCS) | ✅ |
| `ASCS-HA-WIN-008` | RouteHistoryLength | `SAP-0026` | WSFC RouteHistoryLength (ASCS) | ✅ |
| `DB-HA-WIN-004` | CrossSubNetDelay | `SAP-0027` | WSFC CrossSubNetDelay (DB) | ✅ |
| `ASCS-DB-WIN-005` | CrossSubNetThreshold | `SAP-0028` | WSFC CrossSubNetThreshold (DB) | ✅ |
| `DB-HA-WIN-006` | SameSubNetDelay | `SAP-0029` | WSFC SameSubNetDelay (DB) | ✅ |
| `DB-HA-WIN-007` | SameSubNetThreshold | `SAP-0030` | WSFC SameSubNetThreshold (DB) | ✅ |
| `DB-HA-WIN-008` | RouteHistoryLength | `SAP-0031` | WSFC RouteHistoryLength (DB) | ✅ |

### Oracle on Oracle Linux

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `ORA-OEL-0001` | Oracle Hardware Check | `DB-ORA-0001` | Oracle Hardware Check | ✅ |
| `ORA-OEL-0002` | Oracle Linux installation & system language | `DB-ORA-0002` | Linux installation & system language | ✅ |
| `ORA-OEL-0003` | SELinux settings | `DB-ORA-0003` | SELinux settings | ✅ |
| `ORA-OEL-0004` | vm.max_map_count | `DB-ORA-0004` | vm.max_map_count setting for Oracle | ✅ |
| `ORA-OEL-0005` | kernel.sem | `DB-ORA-0005` | kernel.sem settings for Oracle | ✅ |
| `ORA-OEL-0006` | Transparent Huge Pages | `DB-ORA-0006` | Transparent Huge Pages disabled | ✅ |
| `ORA-OEL-0008` | Automatic Storage Management (ASM) | `DB-ORA-0007` | ASM process running | ✅ |

### IBM Db2

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `Db2-OS-0001` | Db2 Hardware Check | `DB-Db2-0001` | Db2 Hardware Check | ✅ |
| `Db2-OS-0002` | Linux installation & system language | `DB-Db2-0002` | Linux installation & system language | ✅ |
| `Db2-OS-0003` | SELinux settings | `DB-Db2-0003` | SELinux settings | ✅ |
| `Db2-OS-0004` | vm.max_map_count | `DB-Db2-0004` | vm.max_map_count should be MemTotal/4096 | ✅ |
| `Db2-OS-0005` | kernel.sem | `DB-Db2-0009` | kernel.sem (SEMMSL) | ✅ |
| `Db2-OS-0006` | VM Swapiness | `DB-Db2-0005` | VM Swappiness setting | ✅ |
| `Db2-OS-0007` | VM Overcommit recovery | `DB-Db2-0006` | VM Overcommit recovery setting | ✅ |
| `Db2-OS-0008` | Randomize VA Space | `DB-Db2-0007` | Randomize VA Space setting | ✅ |
| `Db2-OS-0009` | Kernel out of process | `DB-Db2-0010` | Kernel out of process | ✅ |
| `Db2-OS-0010` | Max File Handles | `DB-Db2-0011` | Max File Handles | ✅ |
| `Db2-OS-0011` | Max Async I/O | `DB-Db2-0008` | Max Async I/O | ✅ |
| `Db2-OS-0012` | Transparent Huge Pages | `DB-Db2-0012` | Transparent Huge Pages | ✅ |
| `DB2-OS-0013` | HADR TIMEOUT | `DB-Db2-0013 / DB-Db2-0014` | HADR TIMEOUT / HADR TIMEOUT | ✅ |
| `DB2-OS-0013` | HADR TIMEOUT | `DB-Db2-0013 / DB-Db2-0014` | HADR TIMEOUT / HADR TIMEOUT | ✅ |
| `DB2-OS-0014` | PEER WINDOW (seconds) | `DB-Db2-0015 / DB-Db2-0016 / DB-Db2-0017` | PEER WINDOW (seconds) / PEER WINDOW (seconds) / PEER WINDOW (seconds) | ✅ |
| `DB2-OS-0014` | PEER WINDOW (seconds) | `DB-Db2-0015 / DB-Db2-0016 / DB-Db2-0017` | PEER WINDOW (seconds) / PEER WINDOW (seconds) / PEER WINDOW (seconds) | ✅ |
| `DB2-OS-0014` | PEER WINDOW (seconds) | `DB-Db2-0015 / DB-Db2-0016 / DB-Db2-0017` | PEER WINDOW (seconds) / PEER WINDOW (seconds) / PEER WINDOW (seconds) | ✅ |
| `DB2-OS-0015` | Instance Memory Size | `DB-Db2-0019` | Instance Memory size | ✅ |
| `Db2-OS-0016` | Maximum shared memory segments | `DB-Db2-0018` | Maximum shared memory segments | ✅ |

### HANA ANF / sysctl

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `HDB-ANF-0001` | sysctl net.core.rmem_max | `DB-HANA-0004 / DB-HANA-0005` | sysctl net.core.rmem_max / sysctl net.core.rmem_max | ✅ |
| `HDB-ANF-0002` | sysctl net.core.wmem_max | `DB-HANA-0006 / DB-HANA-0007` | sysctl net.core.wmem_max / sysctl net.core.wmem_max | ✅ |
| `HDB-ANF-0006` | sysctl net.ipv4.tcp_rmem | `DB-HANA-0008 / DB-HANA-0009` | sysctl net.ipv4.tcp_rmem / sysctl net.ipv4.tcp_rmem | ✅ |
| `HDB-ANF-0007` | sysctl net.ipv4.tcp_wmem | `DB-HANA-0010 / DB-HANA-0011` | sysctl net.ipv4.tcp_wmem / sysctl net.ipv4.tcp_wmem | ✅ |
| `HDB-ANF-0008` | sysctl net.core.netdev_max_backlog | `DB-HANA-0012` | sysctl net.core.netdev_max_backlog | ✅ |
| `HDB-ANF-0009` | sysctl net.ipv4.tcp_slow_start_after_idle | `DB-HANA-0013` | sysctl net.ipv4.tcp_slow_start_after_idle | ✅ |
| `HDB-ANF-0010` | sysctl net.ipv4.tcp_moderate_rcvbuf | `DB-HANA-0014` | sysctl net.ipv4.tcp_moderate_rcvbuf | ✅ |
| `HDB-ANF-0011` | sysctl net.ipv4.tcp_window_scaling | `DB-HANA-0015` | sysctl net.ipv4.tcp_window_scaling | ✅ |
| `HDB-ANF-0012` | sysctl net.ipv4.tcp_timestamps | `DB-HANA-0016` | sysctl net.ipv4.tcp_timestamps | ✅ |
| `HDB-ANF-0013` | sysctl net.ipv4.tcp_timestamps | `DB-HANA-0017` | sysctl net.ipv4.tcp_timestamps | ✅ |
| `HDB-ANF-0014` | sysctl net.ipv4.tcp_sack | `DB-HANA-0018` | sysctl net.ipv4.tcp_sack | ✅ |
| `HDB-ANF-0015` | sysctl net.ipv6.conf.all.disable_ipv6 | `DB-HANA-0019` | sysctl net.ipv6.conf.all.disable_ipv6 | ✅ |
| `HDB-ANF-0016` | sysctl net.ipv4.tcp_max_syn_backlog | `DB-HANA-0020` | sysctl net.ipv4.tcp_max_syn_backlog | ✅ |
| `HDB-ANF-0017` | sysctl net.ipv4.ip_local_port_range | `DB-HANA-0021` | sysctl net.ipv4.ip_local_port_range | ✅ |
| `HDB-ANF-0018` | sysctl net.ipv4.conf.all.rp_filter | `DB-HANA-0022` | sysctl net.ipv4.conf.all.rp_filter | ✅ |
| `HDB-ANF-0019` | sysctl sunrpc.tcp_slot_table_entries | `DB-HANA-0023` | sysctl sunrpc.tcp_slot_table_entries | ✅ |
| `HDB-ANF-0020` | sysctl vm.swappiness | `DB-HANA-0024` | sysctl vm.swappiness | ✅ |
| `HDB-ANF-0021` | ANF tcp_max_slot_table_entries | `DB-HANA-0065` | Static ANF tcp_max_slot_table_entries persistence | ✅ |

### HANA Red Hat

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `HDB-RH-0001` | Red Hat tuned-adm profile | `DB-HANA-0025` | Red Hat tuned-adm profile | ✅ |

### HANA HA Pacemaker (SLES)

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `HDB-HA-SLE-0001` | SAP HANA Automatic Site Takeover | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0002` | SAP HANA Automated Register | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0003` | Pacemaker Stonith enabled | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0004` | Pacemaker Stonith timeout | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0005` | Pacemaker corosync token | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0006` | Pacemaker totem.token_retransmits_before_loss_const | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0007` | Pacemaker corosync join | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0008` | Pacemaker corosync consensus | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0009` | Pacemaker corosync max_messages | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0010` | Pacemaker corosync expected_votes | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0011` | Pacemaker corosync two_node | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0012` | Pacemaker watchdog timeout | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0013` | Pacemaker msgwait timeout | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0014` | Pacemaker concurrent fencing | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0015` | Pacemaker number of fence_azure_arm instances | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0016` | Pacemaker Stonith timeout | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0017` | Pacemaker softdog config file | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-SLE-0018` | Pacemaker softdog module loaded | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |

### HANA HA Pacemaker (RHEL)

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `HDB-HA-RH-0001` | SAP HANA Automatic Site Takeover | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-RH-0002` | SAP HANA Automated Register | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-RH-0003` | Pacemaker Stonith | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-RH-0004` | Pacemaker corosync token | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-RH-0005` | Pacemaker expected_votes | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-RH-0006` | Pacemaker concurrent-fencing | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-RH-0007` | Pacemaker optional fence_kdump | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |
| `HDB-HA-RH-0008` | Priority fencing delay | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |

### HANA HA Load Balancer

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `HDB-HA-LB-0001` | Load Balancer Idle Timeout | `HA-LB-002 / HA-LB-003` | Load Balancer Configuration / Load Balancer Configuration | 🔄 |
| `HDB-HA-LB-0002` | Load Balancer Floating IP | `HA-LB-002 / HA-LB-003` | Load Balancer Configuration / Load Balancer Configuration | 🔄 |
| `HDB-HA-LB-0003` | Load Balancer HA Ports | `HA-LB-002 / HA-LB-003` | Load Balancer Configuration / Load Balancer Configuration | 🔄 |
| `HA-LB-0004` | Load Balancer Probe Interval | `HA-LB-002 / HA-LB-003` | Load Balancer Configuration / Load Balancer Configuration | 🔄 |
| `HA-LB-0005` | Load Balancer probeThreshold | `HA-LB-002 / HA-LB-003` | Load Balancer Configuration / Load Balancer Configuration | 🔄 |

### HANA OS / Kernel (SLES)

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `HDB-OS-SLES-0001` | SAP HANA Backup fails on Azure - SLES 12.4 | `DB-HANA-0052` | Kernel version higher than 4.12.14-95.37.1 | ✅ |
| `HDB-OS-SLES-0002` | SAP HANA Backup fails on Azure - SLES 12.5 | `DB-HANA-0027` | Kernel version higher than 4.12.14-122.7.1 | ✅ |
| `HDB-OS-SLES-0003` | SAP HANA Backup fails on Azure - SLES 15 | `DB-HANA-0028` | Kernel version higher than 4.12.14-150.38.1 | ✅ |
| `HDB-OS-SLES-0004` | SAP HANA Backup fails on Azure - SLES 15.1 | `DB-HANA-0029` | Kernel version higher than 4.12.14-197.21.1 | ✅ |
| `HDB-OS-SLES-0005` | Mellanox TX timeout - CPU soft lockup | `DB-HANA-0026` | Mellanox TX timeout - CPU soft lockup | ✅ |
| `HDB-OS-SLES-0006` | Mellanox Driver can cause Kernel panic on SLES 12 SP4 | `DB-HANA-0052` | Kernel version higher than 4.12.14-95.37.1 | ⚠️ |
| `HDB-OS-SLES-0007` | Mellanox Driver can cause Kernel panic on SLES 12 SP5 | `DB-HANA-0027` | Kernel version higher than 4.12.14-122.7.1 | ⚠️ |
| `HDB-OS-SLES-0008` | Mellanox Driver can cause Kernel panic on SLES 15 SP1 | `DB-HANA-0028` | Kernel version higher than 4.12.14-150.38.1 | ⚠️ |
| `HDB-OS-SLES-0009` | Mellanox Driver can cause Kernel panic on SLES 15 SP2 | `DB-HANA-0073` | TSC clocksource risk for SLES 12 | ⚠️ |
| `HDB-OS-SLES-0010` | Mellanox Driver can cause Kernel panic on SLES 15 SP3 | `DB-HANA-0073` | TSC clocksource risk for SLES 12 | ⚠️ |
| `HDB-OS-SLES-0011` | Mellanox Driver can cause Kernel panic on SLES 15 SP4 | `DB-HANA-0073` | TSC clocksource risk for SLES 12 | ⚠️ |
| `HDB-OS-SLES-0012` | Pacemaker stonith pcmk_delay_max | `HA-HANA-001` | Database HA Cluster Configuration | 🔄 |

### HANA OS / Kernel (RHEL)

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `HDB-OS-RHEL-TEMP` | Azure Fence Agent Configuration | `DB-HANA-0030` | Azure Fence Agent Configuration | ✅ |
| `HDB-OS-RHEL-0001` | Mellanox Driver can cause Kernel panic on RHEL 8.2 | `DB-HANA-0067` | Minimum safe kernel for RHEL 8.2 (Mellanox) | ✅ |
| `HDB-OS-RHEL-0002` | Mellanox Driver can cause Kernel panic on RHEL 8.4 | `DB-HANA-0068` | Minimum safe kernel for RHEL 8.4 (Mellanox) | ✅ |
| `HDB-OS-RHEL-0003` | Mellanox Driver can cause Kernel panic on RHEL 8.6 | `DB-HANA-0069` | Minimum safe kernel for RHEL 8.6 (Mellanox) | ✅ |
| `HDB-OS-RHEL-0004` | Mellanox Driver can cause Kernel panic on RHEL 8.8 | `DB-HANA-0070` | Minimum safe kernel for RHEL 8.8 (Mellanox) | ✅ |
| `HDB-OS-RHEL-0005` | Mellanox Driver can cause Kernel panic on RHEL 9.0 | `DB-HANA-0071` | Minimum safe kernel for RHEL 9.0 (Mellanox) | ✅ |
| `HDB-OS-RHEL-0006` | Mellanox Driver can cause Kernel panic on RHEL 9.2 | `DB-HANA-0072` | Minimum safe kernel for RHEL 9.2 (Mellanox) | ✅ |
| `HDB-OS-RHEL-0007` | Mellanox Driver can cause Kernel panic on RHEL 7.9 | `DB-HANA-0066` | Minimum safe kernel for RHEL 7.9 (Mellanox) | ✅ |

### ASCS HA Pacemaker (SLES)

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `ASCS-HA-SLE-0001` | Pacemaker Stonith enabled | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0002` | Pacemaker Stonith timeout | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0003` | Pacemaker corosync token | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0004` | Pacemaker totem.token_retransmits_before_loss_const | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0005` | Pacemaker corosync join | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0006` | Pacemaker corosync consensus | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0007` | Pacemaker corosync max_messages | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0008` | Pacemaker corosync expected_votes | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0009` | Pacemaker corosync two_node | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0010` | Pacemaker watchdog timeout | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0011` | Pacemaker msgwait timeout | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0012` | Pacemaker concurrent fencing | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0013` | Pacemaker number of fence_azure_arm instances | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0014` | Pacemaker Stonith timeout | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0015` | Pacemaker softdog config file | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-SLE-0018` | Pacemaker softdog module loaded | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |

### ASCS HA Pacemaker (RHEL)

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `ASCS-HA-RH-0001` | Pacemaker Stonith | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-RH-0002` | Pacemaker corosync token | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-RH-0003` | Pacemaker expected_votes | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-RH-0004` | Pacemaker concurrent-fencing | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |
| `ASCS-HA-RH-0005` | Pacemaker optional fence_kdump | `HA-SCS-001` | SCS/ERS HA Cluster Configuration | 🔄 |

### ASCS HA Load Balancer

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `ASCS-HA-LB-0001` | Load Balancer Idle Timeout | `HA-LB-002 / HA-LB-003` | Load Balancer Configuration / Load Balancer Configuration | 🔄 |
| `ASCS-HA-LB-0002` | Load Balancer Floating IP | `HA-LB-002 / HA-LB-003` | Load Balancer Configuration / Load Balancer Configuration | 🔄 |
| `ASCS-HA-LB-0003` | Load Balancer HA Ports | `HA-LB-002 / HA-LB-003` | Load Balancer Configuration / Load Balancer Configuration | 🔄 |

### ASCS Network

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `ASCS-NET-0001` | Load Balancer timestamps | `ASCS-0001` | Load Balancer timestamps | ✅ |

### App Server

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `APP-OS-0001` | IPv4 keepalive time | `APP-0001` | IPv4 keepalive time | ✅ |
| `APP-OS-0002` | IPv4 tcp_retries2 | `APP-0002` | IPv4 tcp_retries2 | ✅ |
| `APP-OS-0003` | IPv4 keepalive interval | `APP-0003` | IPv4 keepalive interval | ✅ |
| `APP-OS-0004` | IPv4 keepalive probes | `APP-0004` | IPv4 keepalive probes | ✅ |
| `APP-OS-0005` | IPv4 tcp_tw_recycle | `APP-0005` | IPv4 tcp_tw_recycle | ✅ |
| `APP-OS-0006` | IPv4 tcp_tw_reuse | `APP-0006` | IPv4 tcp_tw_reuse | ✅ |
| `APP-OS-0007` | IPv4 tcp_retries1 | `APP-0007` | IPv4 tcp_retries1 | ✅ |

### OS General

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `OS-0001` | fstrim disabled | `DB-HANA-0031` | fstrim disabled | ✅ |
| `HDB-OS-0002` | swap space | `DB-HANA-0032` | Swap space | ✅ |

### TSC Clocksource

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `OS-SLES-0001` | TSC Clocksource during High I/O load | `DB-HANA-0073` | TSC clocksource risk for SLES 12 | ✅ |
| `OS-SLES-0002` | TSC Clocksource during High I/O load | `DB-HANA-0073` | TSC clocksource risk for SLES 12 | 🔄 |
| `OS-SLES-0003` | TSC Clocksource during High I/O load | `DB-HANA-0073` | TSC clocksource risk for SLES 12 | 🔄 |

### Endpoint Protection / Defender

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `AV-GEN-0001` | Detect installed Endpoint Protections | `FC-0001 to FC-0007` | FC-0001 to FC-0007 | 🔄 |
| `AV-MDE-0001` | Microsoft Defender Health | `FC-0008` | Microsoft Defender Health | ✅ |
| `AV-MDE-0002` | Microsoft Defender Release Ring | `FC-0009` | Microsoft Defender Release Ring | ✅ |
| `AV-MDE-0003` | Microsoft Defender Realtime Protection | `FC-0010` | Microsoft Defender Realtime Protection | ✅ |
| `AV-MDE-0004` | Microsoft Defender Automatic Definition Update | `FC-0011` | Microsoft Defender Automatic Definition Update | ✅ |
| `AV-MDE-0005` | Microsoft Defender Definition Status | `FC-0012` | Microsoft Defender Definition Status | ✅ |
| `AV-MDE-0006` | Microsoft Defender EDR Early Preview | `FC-0013` | Microsoft Defender EDR Early Preview | ✅ |
| `AV-MDE-0007` | Microsoft Defender Conflicting Applications | `FC-0014` | Microsoft Defender Conflicting Applications | ✅ |
| `AV-MDE-0008` | Microsoft Defender Supplementary Events Subsystem | `FC-0015` | Microsoft Defender Supplementary Events Subsystem | ✅ |

## 2. QualityCheck.json — CheckFeatures (7 entries)

Feature detection checks for endpoint protection products.

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `FC-0001` | EndpointProtection-DefenderLinux - Microsoft Defender Linux | `FC-0001` | EndpointProtection-DefenderLinux | ✅ |
| `FC-0002` | EndpointProtection-CrowdstrikeFalcon - Crownstrike Falcon | `FC-0002` | EndpointProtection-CrowdstrikeFalcon | ✅ |
| `FC-0003` | EndpointProtection-SentinelOne - Sentinel One | `FC-0003` | EndpointProtection-SentinelOne | ✅ |
| `FC-0004` | EndpointProtection-Trendmicro - Trendmicro Deep Security | `FC-0004` | EndpointProtection-Trendmicro | ✅ |
| `FC-0005` | EndpointProtection-Sophos - Sophos Server Protection | `FC-0005` | EndpointProtection-Sophos | ✅ |
| `FC-0006` | EndpointProtection-Trellix - Trellix Endpoint Security (McAfee) | `FC-0006` | EndpointProtection-Trellix | ✅ |
| `FC-0007` | EndpointProtection-ClamAV - ClamAV | `FC-0007` | EndpointProtection-ClamAV | ✅ |

## 3. QualityCheck.json — VMCollectInformation (25 entries)

Information collection checks that gather system metadata (not validation).

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `IC-0001` | Hostname | `IC-0005 / IC-0006` | Hostname / Hostname | 🔄 |
| `IC-0001W` | Hostname | `IC-0006` | Hostname | ✅ |
| `IC-0002` | Kernel | `IC-0008` | Kernel Version | ✅ |
| `IC-0002W` | Server Time Zone | `IC-0042` | Windows Server Time Zone | ✅ |
| `IC-0003` | Azure Hypervisor Host | `IC-0009` | Azure Hypervisor Host | ✅ |
| `IC-0003W` | OS Product | `IC-0043` | Windows OS Product | ✅ |
| `IC-0006` | Availability Set | `IC-0031` | Availability Set | ✅ |
| `IC-0007` | Linux Release File | `IC-0010` | Linux Release File | ✅ |
| `IC-0007W` | OS Product | `IC-0043` | Windows OS Product | 🔄 |
| `IC-0008` | Linux Major and Minor Relase | `IC-0011 / IC-0012` | Linux Major and Minor Release / Linux Major and Minor Release | ✅ |
| `IC-0008W` | OS Product Name | `IC-0043` | Windows OS Product | 🔄 |
| `IC-0008WE` | OS Edition | `IC-0044` | Windows OS Edition | ✅ |
| `IC-0009` | Proximity Placement Group (PPG) | `IC-0032` | Proximity Placement Group (PPG) | ✅ |
| `IC-0010` | Proximity Placement Group (PPG) - VMs associated | `IC-0033` | Proximity Placement Group (PPG) VMs Associated | ✅ |
| `IC-0010W` | OS Version | `IC-0045` | Windows OS Version | ✅ |
| `IC-0010WD` | OS Domain Name | `IC-0046` | Windows Domain Name | ✅ |
| `IC-0011` | VM Generation | `IC-0034` | VM Generation | ✅ |
| `IC-0012` | Extensions installed on VM | `IC-0035` | Extensions & Applications Installed | ✅ |
| `IC-0013` | Secondary IP enabled on VM | `IC-0036` | Secondary IP Configuration | ✅ |
| `IC-0014` | VM Security Type | `IC-0037` | Security Type | ✅ |
| `IC-0015` | VMSS Flex ID | `IC-0039` | VMSS Flex ID | ✅ |
| `IC-0016` | OS Timezone | `IC-0013` | OS Timezone | ✅ |
| `IC-0017` | OS KDUMP Configuration | `IC-0041` | OS KDUMP Configuration | ✅ |
| `IC-0018` | Oracle gclib version | `IC-0014` | Oracle gclib version | ✅ |
| `IC-0019` | HugePages_Total | `IC-0049` | HugePages Total | ✅ |

## 4. QualityCheck.json — VMCollectInformationAdditional (22 entries)

Additional system information collection checks.

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `IC-9001` | hosts | `IC-0007` | Hosts | ✅ |
| `IC-9001W` | hosts | `IC-0047` | Windows Hosts File | ✅ |
| `IC-9002` | sysctl | `IC-0015` | Sysctl | ✅ |
| `IC-9003` | fstab | `IC-0016` | fstab | ✅ |
| `IC-9004` | systemctl | `IC-0017` | systemctl | ✅ |
| `IC-9005` | chkconfig | `IC-0018` | chkconfig | ✅ |
| `IC-9006` | installed packages | `IC-0019` | Installed Packages | ✅ |
| `IC-9007` | SBDconfig | `IC-0021` | SBD Configuration | ✅ |
| `IC-9008` | crm configure show | `IC-0022` | Cluster Configuration | ✅ |
| `IC-9009` | crm status | `IC-0023` | Cluster Status | ✅ |
| `IC-9010` | pcs config show | `IC-0040` | Cluster Configuration | ✅ |
| `IC-9011` | pcs status | `IC-0023` | Cluster Status | 🔄 |
| `IC-9012` | lsscsi | `IC-0024` | lsscsi | ✅ |
| `IC-9013` | storage-metadata | `IC-0025` | storage-metadata | ✅ |
| `IC-9014` | AzDisk | `IC-0038` | Azure Disks | ✅ |
| `IC-9015` | lvm fullreport | `IC-0026` | lvm fullreport | ✅ |
| `IC-9016` | MiniFilter Driver | `IC-0048` | Windows MiniFilter Drivers | ✅ |
| `IC-9017` | SrHook Configuration | `IC-0027` | SrHook Configuration | ✅ |
| `IC-9018` | HADR Dump | `IC-0028` | HADR Dump | ✅ |
| `IC-9019` | DB2 user dump | `DB-Db2-0027` | DB2 user dump | ✅ |
| `IC-9020` | Microsoft Defender Exclusion List | `IC-0029` | Microsoft Defender Exclusion List | ✅ |
| `IC-9021` | Microsoft Defender Health | `IC-0020` | Microsoft Defender Health | ✅ |

## 5. QualityCheck.ps1 — Hard-coded Checks (26 entries)

Checks defined only in the PowerShell script (not in QualityCheck.json).
These include HANA storage/filesystem validation and DB2 stripe size checks.

| Legacy ID | Legacy Description | Config Check ID | Config Check Name | Status |
|-----------|-------------------|-----------------|-------------------|--------|
| `HDB-FS-0001` | SAP HANA Data: File System | `DB-HANA-0033` | Filesystem type for /hana/data | ✅ |
| `HDB-FS-0002` | SAP HANA Data: Disk Performance | `DB-HANA-0041` | Disk performance for /hana/data (MBPS) | ✅ |
| `HDB-FS-0003` | SAP HANA Data: Disk Performance | `DB-HANA-0042` | Disk performance for /hana/data (IOPS) | ✅ |
| `HDB-FS-0004` | SAP HANA Data: stripe size | `DB-HANA-0034` | Stripe size for /hana/data | ✅ |
| `HDB-FS-0005` | SAP HANA Data: same disk type | `DB-HANA-0058` | Same disk type for /hana/data | ✅ |
| `HDB-FS-0006` | SAP HANA Data: same disk performance type | `DB-HANA-0060` | Same performance tier for /hana/data | ✅ |
| `HDB-FS-0015` | SAP HANA Data: storage type supported | `DB-HANA-0063` | Storage type supported for /hana/data | ✅ |
| `HDB-FS-0017` | SAP HANA Data: sector size Premium SSD V2 | `DB-HANA-0039` | Sector size for /hana/data Premium SSD V2 | ✅ |
| `HDB-FS-0007` | SAP HANA Log: File System | `DB-HANA-0035` | Filesystem type for /hana/log | ✅ |
| `HDB-FS-0008` | SAP HANA Log: Disk Performance | `DB-HANA-0043` | Disk performance for /hana/log (MBPS) | ✅ |
| `HDB-FS-0009` | SAP HANA Log: Disk Performance | `DB-HANA-0044` | Disk performance for /hana/log (IOPS) | ✅ |
| `HDB-FS-0010` | SAP HANA Log: stripe size | `DB-HANA-0036` | Stripe size for /hana/log | ✅ |
| `HDB-FS-0011` | SAP HANA Log: same disk type | `DB-HANA-0059` | Same disk type for /hana/log | ✅ |
| `HDB-FS-0012` | SAP HANA Log: same disk performance type | `DB-HANA-0061` | Same performance tier for /hana/log | ✅ |
| `HDB-FS-0013` | SAP HANA Log: Write Accelerator enabled | `DB-HANA-0062` | Write Accelerator enabled for /hana/log | ✅ |
| `HDB-FS-0016` | SAP HANA Log: storage type supported | `DB-HANA-0064` | Storage type supported for /hana/log | ✅ |
| `HDB-FS-0018` | SAP HANA Log: sector size Premium SSD V2 | `DB-HANA-0040` | Sector size for /hana/log Premium SSD V2 | ✅ |
| `HDB-FS-0014` | SAP HANA Shared: File System | `DB-HANA-0037` | Filesystem type for /hana/shared | ✅ |
| `DB2-RHEL-0001` | IBM DB2 Log: stripe size | `DB-Db2-0026` | Stripe size for /db2/log | ✅ |
| `DB2-RHEL-0002` | IBM DB2 Data: stripe size | `DB-Db2-0025` | Stripe size for /db2/data | ✅ |
| `IC-VMType` | (hard-coded in PS1) | `IC-0001` | Virtual Machine Name | 🔄 |
| `IC-vmId` | (hard-coded in PS1) | `—` | — | ❌ |
| `IC-vmlocation` | (hard-coded in PS1) | `IC-0003` | Region | 🔄 |
| `IC-vmname` | (hard-coded in PS1) | `IC-0001` | Virtual Machine Name | 🔄 |
| `IC-vmzone` | (hard-coded in PS1) | `IC-0004` | Availability Zone | ✅ |
| `IC-Controller` | (hard-coded in PS1) | `—` | — | ❌ |

## Architecture Notes

### Composite Checks

STAF uses **composite checks** that validate multiple parameters in a single execution.
These map many legacy 1:1 checks into fewer but more thorough validations:

| Composite Check | Validates | Legacy Equivalents | Configuration Source |
|-----------------|-----------|-------------------|----------------------|
| `HA-HANA-001` | 300+ DB HA/Pacemaker parameters (CIB XML) | HDB-HA-SLE-0001 to 0018, HDB-HA-RH-0001 to 0008, HDB-OS-SLES-0012 | [HA Cluster Parameter](../src/roles/ha_db_hana/tasks/files/constants.yaml) |
| `HA-SCS-001` | 300+ SCS/ERS HA/Pacemaker parameters (CIB XML) | ASCS-HA-SLE-0001 to 0018, ASCS-HA-RH-0001 to 0005 | [HA Cluster Parameter](../src/roles/ha_scs/tasks/files/constants.yaml) |
| `HA-LB-002 / HA-LB-003` | All Load Balancer properties (Azure API) | HDB-HA-LB-0001 to 0003, ASCS-HA-LB-0001 to 0003, HA-LB-0004, HA-LB-0005 | [Load Balancer Parameter](../src/roles/ha_db_hana/tasks/files/constants.yaml) |

### ID Scheme Differences

| Legacy Pattern | STAF Pattern | Example |
|---------------|-------------|---------|
| `HDB-ANF-NNNN` | `DB-HANA-NNNN` | `HDB-ANF-0001` → `DB-HANA-0004` |
| `Db2-OS-NNNN` | `DB-Db2-NNNN` | `Db2-OS-0001` → `DB-Db2-0001` |
| `ORA-OEL-NNNN` | `DB-ORA-NNNN` | `ORA-OEL-0001` → `DB-ORA-0001` |
| `APP-OS-NNNN` | `APP-NNNN` | `APP-OS-0001` → `APP-0001` |
| `HDB-HA-SLE/RH-NNNN` | `HA-HANA-001` (composite) | Multiple → single |
| `HDB-FS-NNNN` (PS1) | `DB-HANA-NNNN` | `HDB-FS-0001` → `DB-HANA-0033` |
| `ASCS-HA-WIN-NNN` | `SAP-NNNN` | `ASCS-HA-WIN-001` → `SAP-0019` |
| `DB-HA-WIN-NNN` | `SAP-NNNN` | `DB-HA-WIN-004` → `SAP-0027` |
| `IC-NNNNW` / `IC-NNNNWD` | `IC-NNNN` | `IC-0002W` → `IC-0042` |
