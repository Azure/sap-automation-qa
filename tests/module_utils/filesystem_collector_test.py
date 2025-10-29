# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the FileSystemCollector module.

This test suite provides comprehensive coverage for filesystem data collection,
LVM volume parsing, Azure disk correlation, and NFS storage (ANF/AFS) integration.
Tests use pytest with monkeypatch for mocking, avoiding unittest entirely.
"""

import pytest
from typing import Any, Dict
from src.module_utils.filesystem_collector import FileSystemCollector


class MockParent:
    """
    Mock SapAutomationQA parent for testing FileSystemCollector.

    Provides logging, error handling, and command execution interfaces
    that FileSystemCollector depends on.
    """

    def __init__(self):
        self.logs = []
        self.errors = []

    def log(self, level: int, message: str) -> None:
        """Mock log method to capture log messages"""
        self.logs.append({"level": level, "message": message})

    def handle_error(self, error: Exception) -> None:
        """Mock handle_error method to capture errors"""
        self.errors.append(error)

    def execute_command_subprocess(self, command: str, shell_command: bool = True) -> str:
        """Mock execute_command_subprocess method"""
        return "mock_output"


class MockCheck:
    """
    Mock Check object for testing collectors.

    Simulates configuration check objects with collector arguments.
    """

    def __init__(self, collector_args: Dict[str, Any] | None = None):
        self.collector_args = collector_args or {}


@pytest.fixture
def mock_parent():
    """Fixture to provide a fresh MockParent instance for each test"""
    return MockParent()


@pytest.fixture
def collector(mock_parent):
    """Fixture to provide a FileSystemCollector instance"""
    return FileSystemCollector(mock_parent)


class TestFileSystemCollectorInit:
    """Test suite for FileSystemCollector initialization"""

    def test_initialization(self, mock_parent):
        """Test FileSystemCollector initializes properly with parent"""
        collector = FileSystemCollector(mock_parent)
        assert collector.parent == mock_parent


class TestParseFilesystemData:
    """Test suite for _parse_filesystem_data method"""

    def test_parse_filesystem_basic(self, collector):
        """Test basic filesystem parsing with findmnt and df outputs"""
        findmnt_output = (
            "/hana/data /dev/mapper/datavg-datalv xfs rw,relatime,attr2\n"
            "/hana/log /dev/sdc ext4 rw,relatime\n"
        )
        df_output = (
            "Filesystem 1K-blocks Used Available Use% Mounted\n"
            "/dev/mapper/datavg-datalv 524288000 104857600 419430400 20% /hana/data\n"
            "/dev/sdc 104857600 10485760 94371840 10% /hana/log\n"
        )
        lvm_volume = {
            "datalv": {
                "dm_path": "/dev/mapper/datavg-datalv",
                "vg_name": "datavg",
                "stripe_size": "256k",
            }
        }
        result = collector._parse_filesystem_data(
            findmnt_output, df_output, lvm_volume, {}, [], [], []
        )
        assert len(result) == 2
        assert result[0]["target"] == "/hana/data"
        assert result[0]["vg"] == "datavg"
        assert result[0]["stripe_size"] == "256k"
        assert result[1]["target"] == "/hana/log"
        assert result[1]["vg"] == ""

    def test_parse_filesystem_with_nfs_anf(self, collector):
        """Test NFS filesystem parsing with ANF storage correlation"""
        findmnt_output = "/hana/shared 10.0.0.5:/volume1 nfs4 rw,relatime\n"
        df_output = (
            "Filesystem 1K-blocks Used Available Use% Mounted\n"
            "10.0.0.5:/volume1 1048576000 104857600 943718400 10% /hana/shared\n"
        )
        anf_storage_data = [
            {
                "ip": "10.0.0.5",
                "throughputMibps": 1024,
                "serviceLevel": "Premium",
            }
        ]
        result = collector._parse_filesystem_data(
            findmnt_output, df_output, {}, {}, [], anf_storage_data, []
        )
        assert len(result) == 1
        assert result[0]["target"] == "/hana/shared"
        assert result[0]["max_mbps"] == 1024
        assert result[0]["max_iops"] == "-"
        assert result[0]["nfs_type"] == "ANF"

    def test_parse_filesystem_with_nfs_afs(self, collector):
        """Test NFS filesystem parsing with AFS storage correlation"""
        findmnt_output = "/hana/backup 10.0.1.10:/share nfs rw,relatime\n"
        df_output = (
            "Filesystem 1K-blocks Used Available Use% Mounted\n"
            "10.0.1.10:/share 2097152000 209715200 1887436800 10% /hana/backup\n"
        )
        afs_storage_data = [
            {
                "NFSAddress": "10.0.1.10:/share",
                "ThroughputMibps": 512,
                "IOPS": 50000,
            }
        ]
        result = collector._parse_filesystem_data(
            findmnt_output, df_output, {}, {}, [], [], afs_storage_data
        )
        assert len(result) == 1
        assert result[0]["max_mbps"] == 512
        assert result[0]["max_iops"] == 50000
        assert result[0]["nfs_type"] == "AFS"

    def test_parse_filesystem_with_azure_disk(self, collector):
        """Test filesystem parsing with direct Azure disk correlation"""
        findmnt_output = "/datadisk /dev/sdc xfs rw,relatime\n"
        df_output = (
            "Filesystem 1K-blocks Used Available Use% Mounted\n"
            "/dev/sdc 524288000 52428800 471859200 10% /datadisk\n"
        )
        azure_disk_data = [
            {
                "name": "sdc",
                "mbps": 750,
                "iops": 20000,
            }
        ]
        result = collector._parse_filesystem_data(
            findmnt_output, df_output, {}, {}, azure_disk_data, [], []
        )
        assert len(result) == 1
        assert result[0]["max_mbps"] == 750
        assert result[0]["max_iops"] == 20000

    def test_parse_filesystem_with_lvm_mapping(self, collector, mock_parent):
        """Test filesystem parsing with LVM volume group to disk mapping"""
        findmnt_output = "/hana/data /dev/mapper/datavg-datalv xfs rw,relatime\n"
        df_output = (
            "Filesystem 1K-blocks Used Available Use% Mounted\n"
            "/dev/mapper/datavg-datalv 1048576000 104857600 943718400 10% /hana/data\n"
        )
        lvm_volume = {
            "datalv": {
                "dm_path": "/dev/mapper/datavg-datalv",
                "vg_name": "datavg",
                "stripe_size": "256k",
            }
        }
        vg_to_disk_names = {"datavg": ["disk1", "disk2"]}
        result = collector._parse_filesystem_data(
            findmnt_output,
            df_output,
            lvm_volume,
            {},
            [],
            [],
            [],
            vg_to_disk_names,
        )
        assert len(result) == 1
        assert result[0]["vg"] == "datavg"
        assert result[0]["azure_disk_names"] == ["disk1", "disk2"]
        assert any("Mapped VG" in log["message"] for log in mock_parent.logs)


class TestMapVgToDiskNames:
    """Test suite for _map_vg_to_disk_names method"""

    def test_map_vg_to_disk_names_success(self, collector, mock_parent):
        """Test successful VG to disk name mapping with complete data"""
        lvm_fullreport = {
            "report": [
                {
                    "pv": [{"pv_name": "/dev/sdc"}, {"pv_name": "/dev/sdd"}],
                    "vg": [{"vg_name": "datavg"}],
                }
            ]
        }
        imds_metadata = [
            {"lun": "0", "name": "disk1"},
            {"lun": "1", "name": "disk2"},
        ]
        device_lun_map = {"sdc": "0", "sdd": "1"}
        result = collector._map_vg_to_disk_names(lvm_fullreport, imds_metadata, device_lun_map)
        assert "datavg" in result
        assert sorted(result["datavg"]) == ["disk1", "disk2"]
        assert any("Found 1 LVM reports" in log["message"] for log in mock_parent.logs)

    def test_map_vg_to_disk_names_error_cases(self, collector, mock_parent):
        """Test VG mapping handles various error conditions: missing LUN, missing IMDS, no VG names, exceptions"""
        mock_parent.logs.clear()
        lvm_fullreport = {
            "report": [{"pv": [{"pv_name": "/dev/sdc"}], "vg": [{"vg_name": "datavg"}]}]
        }
        result = collector._map_vg_to_disk_names(
            lvm_fullreport, [{"lun": "0", "name": "disk1"}], {}
        )
        assert result == {} or result.get("datavg") == []
        assert any("No LUN mapping found" in log["message"] for log in mock_parent.logs)

        mock_parent.logs.clear()
        result = collector._map_vg_to_disk_names(lvm_fullreport, [], {"sdc": "0"})
        assert result.get("datavg", []) == []
        assert any("No IMDS entry for LUN" in log["message"] for log in mock_parent.logs)

        mock_parent.logs.clear()
        lvm_fullreport_no_vg = {"report": [{"pv": [{"pv_name": "/dev/sdc"}], "vg": []}]}
        result = collector._map_vg_to_disk_names(lvm_fullreport_no_vg, {}, {})
        assert result == {}
        assert any("no VG names found" in log["message"] for log in mock_parent.logs)

        mock_parent.logs.clear()
        result = collector._map_vg_to_disk_names(None, [], {})
        assert result == {}
        assert any("Failed to map VG" in log["message"] for log in mock_parent.logs)


class TestCollectLvmVolumes:
    """Test suite for collect_lvm_volumes method"""

    def test_collect_lvm_volumes_success_and_edge_cases(self, collector):
        """Test LVM volume collection: success cases, rootvg filtering, and invalid pv_count handling"""
        lvm_fullreport = {
            "report": [
                {
                    "vg": [
                        {"vg_name": "datavg", "pv_count": "2", "lv_count": "1", "vg_size": "1024g"}
                    ],
                    "lv": [
                        {
                            "lv_name": "datalv",
                            "lv_full_name": "datavg/datalv",
                            "lv_path": "/dev/datavg/datalv",
                            "lv_dm_path": "/dev/mapper/datavg-datalv",
                            "lv_layout": "linear",
                            "lv_size": "512g",
                            "lv_uuid": "uuid123",
                        }
                    ],
                    "seg": [{"lv_uuid": "uuid123", "stripes": "2", "stripe_size": "256k"}],
                }
            ]
        }
        lvm_volumes, lvm_groups = collector.collect_lvm_volumes(lvm_fullreport)
        assert "datalv" in lvm_volumes
        assert lvm_volumes["datalv"]["vg_name"] == "datavg"
        assert lvm_volumes["datalv"]["stripe_size"] == "256k"
        assert "datavg" in lvm_groups
        assert lvm_groups["datavg"]["disks"] == 2

        lvm_fullreport_vgname = {
            "report": [
                {
                    "vg": [
                        {"vg_name": "logvg", "pv_count": "1", "lv_count": "1", "vg_size": "256g"}
                    ],
                    "lv": [{"lv_name": "loglv", "vg_name": "logvg", "lv_uuid": "uuid456"}],
                    "seg": [],
                }
            ]
        }
        lvm_volumes, lvm_groups = collector.collect_lvm_volumes(lvm_fullreport_vgname)
        assert "loglv" in lvm_volumes
        assert lvm_volumes["loglv"]["vg_name"] == "logvg"
        lvm_fullreport_rootvg = {
            "report": [
                {
                    "vg": [{"vg_name": "rootvg", "pv_count": "1"}],
                    "lv": [
                        {"lv_name": "rootlv", "lv_full_name": "rootvg/rootlv", "lv_uuid": "uuid789"}
                    ],
                    "seg": [],
                }
            ]
        }
        lvm_volumes, _ = collector.collect_lvm_volumes(lvm_fullreport_rootvg)
        assert "rootlv" not in lvm_volumes
        lvm_fullreport_invalid = {
            "report": [
                {
                    "vg": [{"vg_name": "testvg", "pv_count": "invalid", "lv_count": "1"}],
                    "lv": [],
                    "seg": [],
                }
            ]
        }
        _, lvm_groups = collector.collect_lvm_volumes(lvm_fullreport_invalid)
        assert lvm_groups["testvg"]["disks"] == 0

    def test_collect_lvm_volumes_exception(self, collector):
        """Test LVM collection handles exceptions and returns error message"""
        result = collector.collect_lvm_volumes(None)
        assert isinstance(result, str)
        assert "ERROR: LVM volume collection failed" in result


class TestParseMetadata:
    """Test suite for _parse_metadata method"""

    def test_parse_metadata_various_formats(self, collector, mock_parent):
        """Test parsing metadata in various formats: lists, dicts, JSON strings, newline-delimited JSON"""
        raw_data = [{"name": "disk1", "size": "512"}, {"name": "disk2", "size": "1024"}]
        result = collector._parse_metadata(raw_data, "test")
        assert len(result) == 2
        assert result[0]["name"] == "disk1"
        assert any("Successfully parsed 2 test items" in log["message"] for log in mock_parent.logs)
        mock_parent.logs.clear()
        raw_data = ['{"name": "disk1", "size": "512"}', {"name": "disk2"}]
        result = collector._parse_metadata(raw_data, "test")
        assert len(result) == 2
        assert result[0]["name"] == "disk1"
        assert result[1]["name"] == "disk2"
        raw_data = {"name": "disk1", "size": "512"}
        result = collector._parse_metadata(raw_data, "test")
        assert len(result) == 1
        assert result[0]["name"] == "disk1"
        raw_data = '[{"name": "disk1"}, {"name": "disk2"}]'
        result = collector._parse_metadata(raw_data, "test")
        assert len(result) == 2
        mock_parent.logs.clear()
        raw_data = '{"name": "disk1"}\n{"name": "disk2"}\n'
        result = collector._parse_metadata(raw_data, "test")
        assert len(result) == 2
        assert result[0]["name"] == "disk1"

    def test_parse_metadata_error_cases(self, collector, mock_parent):
        """Test metadata parsing handles empty inputs, invalid JSON, and non-dict items"""
        assert collector._parse_metadata(None, "test") == []
        assert collector._parse_metadata("", "test") == []
        assert collector._parse_metadata([], "test") == []
        assert any("empty or None" in log["message"] for log in mock_parent.logs)
        mock_parent.logs.clear()
        raw_data = ["invalid json {", '{"valid": "json"}']
        result = collector._parse_metadata(raw_data, "test")
        assert len(result) == 1
        assert result[0]["valid"] == "json"
        assert any("Failed to parse" in log["message"] for log in mock_parent.logs)
        raw_data = [{"name": "disk1"}, "string_item", 12345, None]
        result = collector._parse_metadata(raw_data, "test")
        assert len(result) == 1
        assert result[0]["name"] == "disk1"


class TestGatherAllFilesystemInfo:
    """Test suite for gather_all_filesystem_info method"""

    def test_gather_all_filesystem_info_complete(self, collector, mock_parent):
        """Test comprehensive filesystem info gathering with all data types"""
        context = {
            "lvm_fullreport": {"report": [{"vg": [], "lv": [], "seg": []}]},
            "azure_disks_metadata": [
                {"name": "disk1", "mbps": 500, "iops": 10000},
                {"name": "disk2", "mbps": 500, "iops": 10000},
            ],
            "anf_storage_metadata": [],
            "afs_storage_metadata": [],
        }
        filesystems = [
            {
                "target": "/hana/data",
                "source": "/dev/mapper/datavg-datalv",
                "fstype": "xfs",
                "vg": "datavg",
                "options": "rw,relatime",
                "size": "1T",
                "free": "800G",
                "used": "200G",
                "used_percent": "20%",
            }
        ]
        lvm_volumes = {
            "datalv": {
                "dm_path": "/dev/mapper/datavg-datalv",
                "stripe_size": "256k",
                "stripes": "2",
                "size": "1024g",
            }
        }
        vg_to_disk_names = {"datavg": ["disk1", "disk2"]}
        result = collector.gather_all_filesystem_info(
            context, filesystems, lvm_volumes, vg_to_disk_names
        )
        assert len(result) == 1
        assert result[0]["target"] == "/hana/data"
        assert result[0]["max_mbps"] == 1000
        assert result[0]["max_iops"] == 20000
        assert result[0]["stripe_size"] == "256k"
        assert result[0]["disk_count"] == 2

    def test_gather_all_filesystem_info_nfs_anf(self, collector, mock_parent):
        """Test filesystem info gathering for ANF NFS mounts"""
        context = {
            "lvm_fullreport": {"report": []},
            "azure_disks_metadata": [],
            "anf_storage_metadata": [
                {
                    "ip": "10.0.0.5",
                    "throughputMibps": 2048,
                    "serviceLevel": "Ultra",
                }
            ],
            "afs_storage_metadata": [],
        }
        filesystems = [
            {
                "target": "/hana/shared",
                "source": "10.0.0.5:/volume1",
                "fstype": "nfs4",
                "vg": "",
                "options": "rw",
                "size": "2T",
                "free": "1.5T",
                "used": "500G",
                "used_percent": "25%",
            }
        ]
        result = collector.gather_all_filesystem_info(context, filesystems, {}, {})
        assert len(result) == 1
        assert result[0]["max_mbps"] == 2048
        assert result[0]["max_iops"] == "-"
        assert any("Correlated NFS" in log["message"] for log in mock_parent.logs)

    def test_gather_all_filesystem_info_direct_disk(self, collector, mock_parent):
        """Test filesystem info gathering for direct Azure disk mounts"""
        context = {
            "lvm_fullreport": {"report": []},
            "azure_disks_metadata": [{"name": "sdc", "mbps": 750, "iops": 20000}],
            "anf_storage_metadata": [],
            "afs_storage_metadata": [],
        }
        filesystems = [
            {
                "target": "/datadisk",
                "source": "/dev/sdc",
                "fstype": "ext4",
                "vg": "",
                "options": "rw",
                "size": "512G",
                "free": "400G",
                "used": "112G",
                "used_percent": "22%",
            }
        ]
        result = collector.gather_all_filesystem_info(context, filesystems, {}, {})
        assert len(result) == 1
        assert result[0]["max_mbps"] == 750
        assert result[0]["max_iops"] == 20000
        assert result[0]["disk_count"] == 1

    def test_gather_all_filesystem_info_error_cases(self, collector, mock_parent):
        context = {"lvm_fullreport": ""}
        result = collector.gather_all_filesystem_info(context, [], {}, {})
        assert result == []
        assert any("lvm_fullreport is empty" in log["message"] for log in mock_parent.logs)
        mock_parent.logs.clear()
        mock_parent.errors.clear()
        result = collector.gather_all_filesystem_info(None, [], {}, {})
        assert result == []
        assert len(mock_parent.errors) == 1


class TestGatherAzureDisksInfo:
    """Test suite for gather_azure_disks_info method"""

    def test_gather_azure_disks_info_complete(self, collector, mock_parent):
        """Test Azure disk info gathering with complete metadata"""
        context = {
            "imds_disks_metadata": [
                {
                    "lun": "0",
                    "name": "disk1",
                    "diskSizeGB": "512",
                    "storageProfile": {"sku": "Premium_LRS"},
                    "caching": "ReadWrite",
                    "writeAcceleratorEnabled": True,
                }
            ],
            "azure_disks_metadata": [
                {
                    "name": "disk1",
                    "size": "512",
                    "sku": "Premium_LRS",
                    "iops": 20000,
                    "mbps": 750,
                    "tier": "P30",
                    "encryption": "EncryptionAtRestWithPlatformKey",
                }
            ],
        }
        lvm_fullreport = {
            "report": [
                {
                    "pv": [{"pv_name": "/dev/sdc"}],
                    "vg": [{"vg_name": "datavg"}],
                }
            ]
        }
        device_lun_map = {"sdc": "0"}
        result = collector.gather_azure_disks_info(context, lvm_fullreport, device_lun_map)
        assert len(result) == 1
        assert result[0]["LUNID"] == "0"
        assert result[0]["Name"] == "disk1"
        assert result[0]["VolumeGroup"] == "datavg"
        assert result[0]["IOPS"] == 20000
        assert result[0]["MBPS"] == 750

    def test_gather_azure_disks_info_edge_cases(self, collector, mock_parent):
        """Test Azure disk info gathering for disks not in VG and exception handling"""
        context = {
            "imds_disks_metadata": [{"lun": "0", "name": "disk1"}],
            "azure_disks_metadata": [{"name": "disk1", "iops": 10000, "mbps": 500}],
        }
        device_lun_map = {"sdc": "0"}
        result = collector.gather_azure_disks_info(context, {"report": []}, device_lun_map)
        assert len(result) == 1
        assert result[0]["VolumeGroup"] == ""
        context_invalid = {"imds_disks_metadata": None, "azure_disks_metadata": None}
        result = collector.gather_azure_disks_info(context_invalid, {}, {})
        assert result == []
        assert isinstance(result, list)


class TestGatherLvmGroupsInfo:
    """Test suite for gather_lvm_groups_info method"""

    def test_gather_lvm_groups_info_success_and_errors(self, collector, mock_parent):
        """Test LVM groups info gathering: success, no disk mapping, and exception handling"""
        lvm_groups = {
            "datavg": {"name": "datavg", "disks": 2, "logical_volumes": 1, "total_size": "1024g"}
        }
        vg_to_disk_names = {"datavg": ["disk1", "disk2"]}
        azure_disk_data = [
            {"name": "disk1", "iops": 10000, "mbps": 500},
            {"name": "disk2", "iops": 10000, "mbps": 500},
        ]
        result = collector.gather_lvm_groups_info(lvm_groups, vg_to_disk_names, azure_disk_data)
        assert len(result) == 1
        assert result[0]["Name"] == "datavg"
        assert result[0]["TotalIOPS"] == 20000
        assert result[0]["TotalMBPS"] == 1000
        assert result[0]["TotalSize"] == "1024GiB"
        lvm_groups_no_mapping = {"testvg": {"name": "testvg", "disks": 1, "total_size": "512g"}}
        result = collector.gather_lvm_groups_info(lvm_groups_no_mapping, {}, [])
        assert len(result) == 1
        assert result[0]["TotalIOPS"] == 0
        mock_parent.logs.clear()
        result = collector.gather_lvm_groups_info(None, {}, [])
        assert result == []
        assert any("Failed to gather LVM group" in log["message"] for log in mock_parent.logs)


class TestGatherLvmVolumesInfo:
    """Test suite for gather_lvm_volumes_info method"""

    def test_gather_lvm_volumes_info_success_and_errors(self, collector, mock_parent):
        """Test LVM volumes info gathering: success, size conversion, and exception handling"""
        lvm_volumes = {
            "datalv": {
                "name": "datalv",
                "vg_name": "datavg",
                "path": "/dev/datavg/datalv",
                "dm_path": "/dev/mapper/datavg-datalv",
                "layout": "linear",
                "size": "512g",
                "stripe_size": "256k",
                "stripes": "2",
            }
        }
        result = collector.gather_lvm_volumes_info(lvm_volumes)
        assert len(result) == 1
        assert result[0]["Name"] == "datalv"
        assert result[0]["Size"] == "512GiB"
        assert result[0]["StripeSize"] == "256k"
        assert any(
            "Successfully correlated LVM volume" in log["message"] for log in mock_parent.logs
        )
        lvm_volumes_tb = {
            "loglv": {
                "name": "loglv",
                "vg_name": "logvg",
                "size": "2t",
                "stripe_size": "",
                "stripes": "",
            }
        }
        result = collector.gather_lvm_volumes_info(lvm_volumes_tb)
        assert result[0]["Size"] == "2TiB"
        mock_parent.logs.clear()
        result = collector.gather_lvm_volumes_info(None)
        assert result == []
        assert any("Failed to gather LVM volume" in log["message"] for log in mock_parent.logs)


class TestGatherAnfVolumesInfo:
    """Test suite for gather_anf_volumes_info method"""

    def test_gather_anf_volumes_info_mounted_only(self, collector, mock_parent):
        """Test ANF volumes info only includes mounted volumes"""
        filesystems = [
            {
                "target": "/hana/shared",
                "source": "10.0.0.5:/volume1",
                "fstype": "nfs4",
                "nfs_type": "ANF",
            }
        ]
        anf_storage_data = [
            {
                "ip": "10.0.0.5",
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.NetApp/"
                "netAppAccounts/account1/capacityPools/pool1/volumes/vol1",
                "serviceLevel": "Premium",
                "throughputMibps": 1024,
                "protocolTypes": ["NFSv4.1"],
            },
            {
                "ip": "10.0.0.6",
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.NetApp/"
                "netAppAccounts/account1/capacityPools/pool1/volumes/vol2",
                "serviceLevel": "Standard",
                "throughputMibps": 512,
                "protocolTypes": ["NFSv3"],
            },
        ]
        result = collector.gather_anf_volumes_info(filesystems, anf_storage_data)
        assert len(result) == 1
        assert result[0]["VolumeName"] == "vol1"
        assert result[0]["PoolName"] == "pool1"
        assert result[0]["ThroughputMibps"] == 1024
        assert any("mounted ANF IPs" in log["message"] for log in mock_parent.logs)

    def test_gather_anf_volumes_info_name_fallback(self, collector):
        """Test ANF volumes info uses name field as fallback"""
        filesystems = [
            {
                "target": "/hana/shared",
                "source": "10.0.0.5:/volume1",
                "fstype": "nfs4",
                "nfs_type": "ANF",
            }
        ]
        anf_storage_data = [
            {
                "ip": "10.0.0.5",
                "name": "account1/pool1/vol1",
                "serviceLevel": "Premium",
                "throughputMibps": 1024,
                "protocolTypes": ["NFSv4.1", "NFSv3"],
            }
        ]
        result = collector.gather_anf_volumes_info(filesystems, anf_storage_data)
        assert len(result) == 1
        assert result[0]["VolumeName"] == "vol1"
        assert result[0]["PoolName"] == "pool1"
        assert "NFSv4.1, NFSv3" in result[0]["ProtocolTypes"]

    def test_gather_anf_volumes_info_edge_cases(self, collector, mock_parent):
        """Test ANF volumes info: non-ANF filesystems filtering and exception handling"""
        filesystems = [{"target": "/data", "source": "/dev/sdc", "fstype": "xfs"}]
        anf_storage_data = [{"ip": "10.0.0.5", "name": "vol1"}]
        result = collector.gather_anf_volumes_info(filesystems, anf_storage_data)
        assert len(result) == 0
        result = collector.gather_anf_volumes_info(None, [])
        assert result == []
        assert any("Failed to gather ANF volume" in log["message"] for log in mock_parent.logs)


class TestCollectMethod:
    """Test suite for the main collect method"""

    def test_collect_complete_success(self, collector, mock_parent):
        """Test complete collection workflow with all data types"""
        context = {
            "lvm_fullreport": {
                "report": [
                    {
                        "vg": [
                            {
                                "vg_name": "datavg",
                                "pv_count": "1",
                                "lv_count": "1",
                                "vg_size": "512g",
                            }
                        ],
                        "lv": [
                            {
                                "lv_name": "datalv",
                                "vg_name": "datavg",
                                "lv_path": "/dev/datavg/datalv",
                                "lv_dm_path": "/dev/mapper/datavg-datalv",
                                "lv_layout": "linear",
                                "lv_size": "512g",
                                "lv_uuid": "uuid1",
                            }
                        ],
                        "seg": [{"lv_uuid": "uuid1", "stripes": "1", "stripe_size": "64k"}],
                    }
                ]
            },
            "mount_info": "/hana/data /dev/mapper/datavg-datalv xfs rw,relatime",
            "df_info": (
                "Filesystem 1K-blocks Used Available Use% Mounted\n"
                "/dev/mapper/datavg-datalv 524288000 52428800 471859200 10% /hana/data"
            ),
            "azure_disks_metadata": [{"name": "disk1", "mbps": 500, "iops": 10000}],
            "anf_storage_metadata": [],
            "afs_storage_metadata": [],
            "imds_disks_metadata": [{"lun": "0", "name": "disk1"}],
            "device_lun_map": {"sdc": "0"},
        }
        result = collector.collect(MockCheck(), context)
        assert isinstance(result, dict)
        assert "filesystems" in result
        assert "lvm_volumes" in result
        assert "lvm_groups" in result
        assert "formatted_filesystem_info" in result
        assert "azure_disks_info" in result
        assert "lvm_groups_info" in result
        assert "lvm_volumes_info" in result
        assert "anf_volumes_info" in result
        assert len(result["filesystems"]) > 0

    def test_collect_empty_lvm_fullreport(self, collector, mock_parent):
        """Test collect handles empty lvm_fullreport"""
        context = {
            "lvm_fullreport": "",
            "mount_info": "/data /dev/sdc xfs rw",
            "df_info": "Filesystem 1K-blocks Used Available Use% Mounted\n/dev/sdc 524288000 52428800 471859200 10% /data",
        }
        collector.collect(MockCheck(), context)
        assert any(
            "lvm_fullreport is empty or invalid" in log["message"] for log in mock_parent.logs
        )

    def test_collect_error_and_logging_scenarios(self, collector, mock_parent):
        """Test collect handles various error scenarios and provides comprehensive logging"""
        context = {
            "lvm_fullreport": {"report": []},
            "mount_info": "",
            "df_info": "Filesystem 1K-blocks Used Available Use% Mounted",
            "imds_disks_metadata": [{"lun": "0", "name": "disk1"}],
        }
        result = collector.collect(MockCheck(), context)
        assert any("device_lun_map not found" in log["message"] for log in mock_parent.logs)
        mock_parent.logs.clear()
        mock_parent.errors.clear()
        result = collector.collect(MockCheck(), None)
        assert isinstance(result, dict)
        assert any("ERROR:" in key for key in result.keys())
        assert len(mock_parent.errors) == 1
        mock_parent.logs.clear()
        context_anf = {
            "lvm_fullreport": {"report": []},
            "mount_info": "",
            "df_info": "Filesystem 1K-blocks Used Available Use% Mounted",
            "anf_storage_metadata": [{"ip": "10.0.0.5"}],
        }
        result = collector.collect(MockCheck(), context_anf)
        assert any("Raw ANF data type" in log["message"] for log in mock_parent.logs)
        mock_parent.logs.clear()
        context_full = {
            "lvm_fullreport": {"report": []},
            "mount_info": "/data /dev/sdc xfs rw",
            "df_info": "Filesystem 1K-blocks Used Available Use% Mounted\n/dev/sdc 1024000 102400 921600 10% /data",
            "azure_disks_metadata": [],
            "anf_storage_metadata": [],
            "afs_storage_metadata": [],
            "imds_disks_metadata": [],
        }
        result = collector.collect(MockCheck(), context_full)
        logged_messages = [log["message"] for log in mock_parent.logs]
        assert any("findmnt_output" in msg for msg in logged_messages)
        assert any("df_output" in msg for msg in logged_messages)
        assert any("Azure disk data type" in msg for msg in logged_messages)
