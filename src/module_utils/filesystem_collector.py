# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Collectors for data collection in SAP Automation QA
"""
import json
import logging
from typing import Any

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA
    from ansible.module_utils.collector import Collector
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA
    from src.module_utils.collector import Collector


class FileSystemCollector(Collector):
    """
    Collects filesystem information
    """

    def __init__(self, parent: SapAutomationQA):
        super().__init__(parent)

    def _parse_filesystem_data(
        self,
        findmnt_output,
        df_output,
        lvm_volume,
        lvm_group,
        azure_disk_data,
        anf_storage_data,
        afs_storage_data,
        vg_to_disk_names=None,
    ):
        """
        Parse filesystem data.

        :param vg_to_disk_names: Pre-computed mapping of VG names to Azure disk names
        :type vg_to_disk_names: Dict[str, List[str]]
        """
        if vg_to_disk_names is None:
            vg_to_disk_names = {}
        filesystems = []
        findmnt_data = {}
        df_data = {}
        df_lines = [line.strip() for line in df_output.split("\n") if line.strip()]
        for line in df_lines[1:]:
            parts = line.split()
            if len(parts) >= 6:
                mountpoint = parts[5]
                df_data[mountpoint] = {
                    "filesystem": parts[0],
                    "size": parts[1],
                    "used": parts[2],
                    "free": parts[3],
                    "used_percent": parts[4],
                }
        for line in [line.strip() for line in findmnt_output.split("\n") if line.strip()]:
            parts = line.split(maxsplit=3)
            if len(parts) >= 4:
                target = parts[0]
                findmnt_data[target] = {"source": parts[1], "fstype": parts[2], "options": parts[3]}
        for mountpoint, df_info in df_data.items():
            findmnt_info = findmnt_data.get(mountpoint, {})
            vg_name, stripe_size = "", ""
            filesystem_path = df_info["filesystem"]
            for lv_name, lv_prop in lvm_volume.items():
                if lv_prop.get("dm_path") == filesystem_path:
                    vg_name = lv_prop.get("vg_name", "")
                    stripe_size = lv_prop.get("stripe_size", "")
                    break

            filesystem_entry = {
                "target": mountpoint,
                "source": filesystem_path,
                "fstype": findmnt_info.get("fstype", ""),
                "options": findmnt_info.get("options", ""),
                "size": df_info["size"],
                "free": df_info["free"],
                "used": df_info["used"],
                "used_percent": df_info["used_percent"],
                "vg": vg_name,
                "stripe_size": stripe_size,
                "max_mbps": 0,
                "max_iops": 0,
            }

            if filesystem_entry["fstype"] in ["nfs", "nfs4"]:
                nfs_source = filesystem_entry["source"]
                if ":" in nfs_source:
                    nfs_address = nfs_source.split(":")[0]

                    matched = False
                    for anf_volume in anf_storage_data:
                        anf_ip = anf_volume.get("ip", "")
                        if anf_ip and anf_ip == nfs_address:
                            filesystem_entry["max_mbps"] = anf_volume.get("throughputMibps", 0)
                            filesystem_entry["max_iops"] = "-"
                            filesystem_entry["nfs_type"] = "ANF"
                            filesystem_entry["service_level"] = anf_volume.get("serviceLevel", "")
                            matched = True
                            break

                    if not matched:
                        for nfs_share in afs_storage_data:
                            storage_account_name = nfs_share.get("Pool", "")
                            share_address = nfs_share.get("NFSAddress", "")
                            if (
                                ":" in share_address and share_address.split(":")[0] == nfs_address
                            ) or storage_account_name in nfs_address:
                                filesystem_entry["max_mbps"] = nfs_share.get("ThroughputMibps", 0)
                                filesystem_entry["max_iops"] = nfs_share.get("IOPS", 0)
                                filesystem_entry["nfs_type"] = "AFS"
                                break
            else:
                if filesystem_path.startswith("/dev/sd") or filesystem_path.startswith("/dev/nvme"):
                    disk_name = (
                        filesystem_path.split("/")[-1]
                        if "/" in filesystem_path
                        else filesystem_path
                    )

                    for disk_data in azure_disk_data:
                        if disk_data.get("name", "").endswith(disk_name):
                            filesystem_entry["max_mbps"] = disk_data.get("mbps", 0)
                            filesystem_entry["max_iops"] = disk_data.get("iops", 0)
                            break
                elif filesystem_path.startswith("/dev/mapper/") and vg_name:
                    disk_names = vg_to_disk_names.get(vg_name, [])

                    if disk_names:
                        filesystem_entry["azure_disk_names"] = disk_names
                        self.parent.log(
                            logging.INFO,
                            f"Mapped VG {vg_name} to {len(disk_names)} Azure disks: {disk_names}",
                        )
                    else:
                        self.parent.log(
                            logging.WARNING,
                            f"No disk mapping found for VG {vg_name}. Ensure device-to-lun mapping is available.",
                        )

            filesystems.append(filesystem_entry)

        return filesystems

    def _map_vg_to_disk_names(self, lvm_fullreport, imds_metadata, device_lun_map):
        """
        Map LVM volume groups to Azure disk names using direct device→lun→diskname correlation.

        Chain: PV device (/dev/sdc) → LUN (0) → disk name (via IMDS) → Azure disk

        :param lvm_fullreport: LVM fullreport JSON with PV information
        :param imds_metadata: IMDS metadata with lun-to-diskname mappings
        :param device_lun_map: Mapping of device names to LUN numbers (e.g., {"sdc": "0"})
        :return: Dict mapping VG names to lists of Azure disk names
        :rtype: Dict[str, List[str]]
        """
        vg_to_disk_names = {}

        try:
            lun_to_diskname = {}
            for disk_info in imds_metadata:
                lun = disk_info.get("lun")
                name = disk_info.get("name")
                if lun is not None and name:
                    lun_to_diskname[str(lun)] = name

            reports = lvm_fullreport.get("report", [])
            self.parent.log(
                logging.INFO,
                f"Found {len(reports)} LVM reports",
            )

            for report in reports:
                pvs = report.get("pv", [])
                vgs = report.get("vg", [])

                vg_names = [vg.get("vg_name") for vg in vgs if vg.get("vg_name")]
                if not vg_names:
                    self.parent.log(
                        logging.WARNING,
                        f"Report has PVs but no VG names found, skipping",
                    )
                    continue
                vg_name = vg_names[0]

                for pv in pvs:
                    pv_name = pv.get("pv_name")

                    if not pv_name:
                        self.parent.log(
                            logging.INFO,
                            f"Skipping PV with missing pv_name",
                        )
                        continue
                    device_name = pv_name.split("/")[-1] if "/" in pv_name else pv_name
                    lun = device_lun_map.get(device_name)
                    if lun is None:
                        self.parent.log(
                            logging.WARNING,
                            f"No LUN mapping found for device {device_name} (PV: {pv_name})",
                        )
                        continue
                    disk_name = lun_to_diskname.get(str(lun))
                    if not disk_name:
                        self.parent.log(
                            logging.WARNING,
                            f"No IMDS entry for LUN {lun} (device: {device_name})",
                        )
                        continue
                    if vg_name not in vg_to_disk_names:
                        vg_to_disk_names[vg_name] = []
                    vg_to_disk_names[vg_name].append(disk_name)

        except Exception as ex:
            self.parent.log(
                logging.ERROR,
                f"Failed to map VG to disk names: {ex}",
            )

        return vg_to_disk_names

    def collect_lvm_volumes(self, lvm_fullreport):
        """
        Collect LVM volume information.

        :param lvm_fullreport: Pre-fetched LVM fullreport JSON string
        :return: Tuple of logical volumes and volume groups
        :rtype: Tuple[Dict[str, Any], Dict[str, Any]]
        """
        log_volume_result = {}
        lvm_group_result = {}
        try:
            lvm_volumes = lvm_fullreport
            for lvm_volume in lvm_volumes.get("report", []):
                vol_groups = lvm_volume.get("vg", [])
                for vol_group in vol_groups:
                    vg_name = vol_group.get("vg_name")
                    pv_count = vol_group.get("pv_count", 0)
                    try:
                        pv_count = int(pv_count) if pv_count else 0
                    except (ValueError, TypeError):
                        pv_count = 0

                    lvm_group_result[vg_name] = {
                        "name": vg_name,
                        "disks": pv_count,
                        "logical_volumes": vol_group.get("lv_count", 0),
                        "total_size": vol_group.get("vg_size"),
                        "total_iops": 0,
                        "total_mbps": 0,
                    }

                logical_volumes = lvm_volume.get("lv", [])
                segments = lvm_volume.get("seg", [])

                for lv in logical_volumes:
                    lv_name = lv.get("lv_name")
                    vg_name = ""
                    if lv.get("lv_full_name") and "/" in lv.get("lv_full_name", ""):
                        vg_name = lv.get("lv_full_name", "").split("/")[0]
                    elif lv.get("vg_name"):
                        vg_name = lv.get("vg_name")

                    stripe_size, stripes = "", ""
                    lv_uuid = lv.get("lv_uuid")
                    for segment in segments:
                        if segment.get("lv_uuid") == lv_uuid:
                            stripes = segment.get("stripes", "")
                            stripe_size = segment.get("stripe_size", "")
                            break

                    if vg_name and vg_name != "rootvg":
                        log_volume_result[lv_name] = {
                            "name": lv_name,
                            "vg_name": vg_name,
                            "path": lv.get("lv_path"),
                            "dm_path": lv.get("lv_dm_path"),
                            "layout": lv.get("lv_layout"),
                            "size": lv.get("lv_size"),
                            "stripe_size": stripe_size,
                            "stripes": stripes,
                        }

        except Exception as ex:
            return f"ERROR: LVM volume collection failed: {str(ex)}"
        return log_volume_result, lvm_group_result

    def _parse_metadata(self, raw_data, data_type="metadata"):
        """
        Parse metadata that can be in various formats: dict, list, or JSON strings.

        :param raw_data: Raw metadata from context
        :param data_type: Type of data for logging purposes
        :return: List of dictionaries
        """
        parsed_data = []

        if not raw_data:
            self.parent.log(
                logging.INFO,
                f"No {data_type} data provided (empty or None)",
            )
            return parsed_data

        self.parent.log(
            logging.INFO,
            f"Parsing {data_type}: type={type(raw_data)}, "
            f"length={len(raw_data) if hasattr(raw_data, '__len__') else 'N/A'}",
        )

        if isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict):
                    parsed_data.append(item)
                elif isinstance(item, str):
                    item_stripped = item.strip()
                    if not item_stripped:
                        continue
                    try:
                        parsed_item = json.loads(item_stripped)
                        if isinstance(parsed_item, dict):
                            parsed_data.append(parsed_item)
                        elif isinstance(parsed_item, list):
                            parsed_data.extend(parsed_item)
                    except json.JSONDecodeError:
                        self.parent.log(
                            logging.WARNING,
                            f"Failed to parse {data_type} item as JSON: {item_stripped[:100]}",
                        )
        elif isinstance(raw_data, dict):
            parsed_data = [raw_data]
        elif isinstance(raw_data, str):
            try:
                parsed_data = json.loads(raw_data)
                if not isinstance(parsed_data, list):
                    parsed_data = [parsed_data]
            except json.JSONDecodeError:
                for line in raw_data.splitlines():
                    if line.strip():
                        try:
                            parsed_data.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            self.parent.log(
                                logging.WARNING,
                                f"Failed to parse {data_type} line: {line.strip()[:100]}",
                            )

        validated_data = []
        for item in parsed_data:
            if isinstance(item, dict):
                validated_data.append(item)
            else:
                self.parent.log(
                    logging.WARNING,
                    f"Skipping non-dict item in {data_type}: {type(item)} - {str(item)[:100]}",
                )

        self.parent.log(
            logging.INFO,
            f"Successfully parsed {len(validated_data)} {data_type} items, "
            f"skipped {len(parsed_data) - len(validated_data)} non-dict items",
        )

        return validated_data

    def gather_all_filesystem_info(
        self, context, filesystems, lvm_volumes, vg_to_disk_names
    ) -> list:
        """
        Gather all filesystem information and correlate as a single dictionary.

        Returns a dictionary keyed by mount point/target with comprehensive filesystem metadata.
        Fully populate all fields by correlating LVM data, Azure disk data, and VG-to-disk mappings.
        For LVM volumes, aggregates IOPS/MBPS from all underlying Azure disks in the volume group.

        Each entry contains: Target, Source, FSType, VG, Options, Size, Free, Used,
        UsedPercent, MaxMBPS, MaxIOPS, StripeSize

        :param context: Context object containing all required filesystem data
        :type context: Dict[str, Any]
        :param filesystems: List of filesystem dictionaries from _parse_filesystem_data
        :type filesystems: List[Dict[str, Any]]
        :param lvm_volumes: LVM volume information from collect_lvm_volumes
        :type lvm_volumes: Dict[str, Any]
        :param vg_to_disk_names: Pre-computed mapping of VG names to Azure disk names
        :type vg_to_disk_names: Dict[str, List[str]]
        :return: List keyed by target/mount point with all filesystem information
        :rtype: list
        """
        try:
            lvm_fullreport = context.get("lvm_fullreport", "")
            if not lvm_fullreport or not lvm_fullreport.get("report"):
                self.parent.log(
                    logging.WARNING,
                    "lvm_fullreport is empty or invalid. LVM data correlation will be incomplete.",
                )

            azure_disk_data = self._parse_metadata(
                context.get("azure_disks_metadata", []), "Azure disk"
            )
            afs_storage_data = self._parse_metadata(
                context.get("afs_storage_metadata", ""), "AFS storage"
            )
            anf_storage_data = self._parse_metadata(
                context.get("anf_storage_metadata", ""), "ANF storage"
            )
            diskname_to_diskdata = {}
            for disk_data in azure_disk_data:
                disk_name = disk_data.get("name", "")
                if disk_name:
                    diskname_to_diskdata[disk_name] = disk_data

            correlated_info = []

            for fs in filesystems:
                target = fs.get("target", "")
                if not target:
                    self.parent.log(
                        logging.WARNING, f"Skipping filesystem entry with no target: {fs}"
                    )
                    continue

                source = fs.get("source", "")
                vg_name = fs.get("vg", "")
                fstype = fs.get("fstype", "")
                stripe_size = fs.get("stripe_size", "")
                stripes = ""

                if not stripe_size and vg_name and source:
                    for lv_name, lv_info in lvm_volumes.items():
                        if lv_info.get("dm_path") == source:
                            stripe_size = lv_info.get("stripe_size", "")
                            stripes = lv_info.get("stripes", "")
                            self.parent.log(
                                logging.INFO,
                                f"Found LVM details for {target}: "
                                + f"stripe_size={stripe_size}, stripes={stripes}",
                            )
                            break

                max_mbps = fs.get("max_mbps", 0)
                max_iops = fs.get("max_iops", 0)
                azure_disk_names = []
                disk_count = 0
                if fstype in ["nfs", "nfs4"]:
                    if ":" in source:
                        nfs_address = source.split(":")[0]
                        matched = False
                        for anf_volume in anf_storage_data:
                            anf_ip = anf_volume.get("ip", "")
                            if anf_ip and anf_ip == nfs_address:
                                max_mbps = anf_volume.get("throughputMibps", 0)
                                max_iops = "-"
                                self.parent.log(
                                    logging.INFO,
                                    f"Correlated NFS {target} with "
                                    + f"ANF: MBPS={max_mbps}, ServiceLevel={anf_volume.get('serviceLevel', '')}",
                                )
                                matched = True
                                break
                        if not matched:
                            for nfs_share in afs_storage_data:
                                share_address = nfs_share.get("NFSAddress", "")
                                if (
                                    ":" in share_address
                                    and share_address.split(":")[0] == nfs_address
                                ):
                                    max_mbps = nfs_share.get("ThroughputMibps", 0)
                                    max_iops = nfs_share.get("IOPS", 0)
                                    self.parent.log(
                                        logging.INFO,
                                        f"Correlated NFS {target} with "
                                        + f"AFS: MBPS={max_mbps}, IOPS={max_iops}",
                                    )
                                    break

                elif source.startswith("/dev/mapper/") and vg_name:
                    disk_names = vg_to_disk_names.get(vg_name, [])

                    if disk_names:
                        azure_disk_names = disk_names
                        disk_count = len(disk_names)
                        total_mbps = 0
                        total_iops = 0

                        for disk_name in disk_names:
                            disk_data = diskname_to_diskdata.get(disk_name)
                            if disk_data:
                                total_mbps += disk_data.get("mbps", 0)
                                total_iops += disk_data.get("iops", 0)
                            else:
                                self.parent.log(
                                    logging.WARNING,
                                    f"No disk data found for {disk_name} in VG {vg_name}",
                                )

                        max_mbps = total_mbps
                        max_iops = total_iops

                        self.parent.log(
                            logging.INFO,
                            f"Aggregated performance for {target} (VG {vg_name}): "
                            f"{disk_count} disks, MBPS={max_mbps}, IOPS={max_iops}",
                        )
                    else:
                        self.parent.log(
                            logging.WARNING, f"No disk mapping found for VG {vg_name} at {target}"
                        )

                elif source.startswith("/dev/sd") or source.startswith("/dev/nvme"):
                    disk_name = source.split("/")[-1] if "/" in source else source

                    for disk_data in azure_disk_data:
                        if disk_data.get("name", "").endswith(disk_name):
                            max_mbps = disk_data.get("mbps", 0)
                            max_iops = disk_data.get("iops", 0)
                            azure_disk_names = [disk_data.get("name", "")]
                            disk_count = 1
                            self.parent.log(
                                logging.INFO,
                                f"Correlated direct disk {target}: MBPS={max_mbps}, IOPS={max_iops}",
                            )
                            break
                correlated_info.append(
                    {
                        "target": target,
                        "source": source,
                        "fstype": fstype,
                        "vg": vg_name,
                        "options": fs.get("options", ""),
                        "size": fs.get("size", ""),
                        "free": fs.get("free", ""),
                        "used": fs.get("used", ""),
                        "used_percent": fs.get("used_percent", ""),
                        "max_mbps": max_mbps,
                        "max_iops": max_iops,
                        "stripe_size": stripe_size,
                        "stripes": stripes,
                        "azure_disk_names": azure_disk_names,
                        "disk_count": disk_count,
                    }
                )

            self.parent.log(
                logging.INFO,
                f"Successfully correlated FS info for {len(correlated_info)} mount points with "
                f"{len(azure_disk_data)} Azure disks and {len(vg_to_disk_names)} VG mappings",
            )

            return correlated_info

        except Exception as ex:
            self.parent.log(
                logging.ERROR, f"Failed to gather correlated filesystem information: {ex}"
            )
            self.parent.handle_error(ex)
            return []

    def gather_azure_disks_info(self, context, lvm_fullreport, device_lun_map):
        """
        Gather correlated Azure disk information with LUN, device mapping, and performance metrics.

        :param context: Context containing Azure metadata
        :param lvm_fullreport: LVM fullreport JSON
        :param device_lun_map: Mapping of device names to LUN numbers
        :return: List of Azure disk information dictionaries
        :rtype: List[Dict[str, Any]]
        """
        azure_disks_info = []

        try:
            imds_metadata = self._parse_metadata(
                context.get("imds_disks_metadata", []), "IMDS disk"
            )
            azure_disk_data = self._parse_metadata(
                context.get("azure_disks_metadata", []), "Azure disk"
            )

            diskname_to_details = {}
            for disk_data in azure_disk_data:
                disk_name = disk_data.get("name", "")
                if disk_name:
                    diskname_to_details[disk_name] = disk_data
            lun_to_imds = {}
            for disk_info in imds_metadata:
                lun = disk_info.get("lun")
                if lun is not None:
                    lun_to_imds[str(lun)] = disk_info
            device_to_vg = {}
            if lvm_fullreport and lvm_fullreport.get("report"):
                for report in lvm_fullreport.get("report", []):
                    pvs = report.get("pv", [])
                    vgs = report.get("vg", [])
                    vg_name = vgs[0].get("vg_name") if vgs else ""

                    for pv in pvs:
                        pv_name = pv.get("pv_name", "")
                        if pv_name:
                            device_name = pv_name.split("/")[-1] if "/" in pv_name else pv_name
                            device_to_vg[device_name] = vg_name
            for device_name, lun in device_lun_map.items():
                imds_data = lun_to_imds.get(str(lun), {})
                disk_name = imds_data.get("name", "")
                disk_details = diskname_to_details.get(disk_name, {})
                vg_name = device_to_vg.get(device_name, "")

                azure_disks_info.append(
                    {
                        "LUNID": lun,
                        "Name": disk_name,
                        "DeviceName": f"/dev/{device_name}",
                        "VolumeGroup": vg_name,
                        "Size": disk_details.get("size", imds_data.get("diskSizeGB", "")),
                        "DiskType": disk_details.get(
                            "sku", imds_data.get("storageProfile", {}).get("sku", "")
                        ),
                        "IOPS": disk_details.get("iops", ""),
                        "MBPS": disk_details.get("mbps", ""),
                        "PerformanceTier": disk_details.get("tier", ""),
                        "StorageType": disk_details.get("encryption", ""),
                        "Caching": imds_data.get("caching", ""),
                        "WriteAccelerator": imds_data.get("writeAcceleratorEnabled", False),
                    }
                )

            self.parent.log(
                logging.INFO,
                f"Successfully correlated Azure disk info for {len(azure_disks_info)} disks",
            )

        except Exception as ex:
            self.parent.log(logging.ERROR, f"Failed to gather Azure disk information: {ex}")

        return azure_disks_info

    def gather_lvm_groups_info(self, lvm_groups, vg_to_disk_names, azure_disk_data):
        """
        Gather correlated LVM volume group information with aggregated performance metrics.

        :param lvm_groups: LVM groups from collect_lvm_volumes
        :param vg_to_disk_names: Mapping of VG names to Azure disk names
        :param azure_disk_data: Parsed Azure disk metadata
        :return: List of LVM group information dictionaries
        :rtype: List[Dict[str, Any]]
        """
        lvm_groups_info = []

        try:
            diskname_to_perf = {}
            for disk_data in azure_disk_data:
                disk_name = disk_data.get("name", "")
                if disk_name:
                    diskname_to_perf[disk_name] = {
                        "iops": disk_data.get("iops", 0),
                        "mbps": disk_data.get("mbps", 0),
                    }
            for vg_name, vg_data in lvm_groups.items():
                disk_names = vg_to_disk_names.get(vg_name, [])
                total_iops = 0
                total_mbps = 0
                for disk_name in disk_names:
                    perf_data = diskname_to_perf.get(disk_name, {})
                    total_iops += perf_data.get("iops", 0)
                    total_mbps += perf_data.get("mbps", 0)

                totalsize = vg_data.get("total_size", "")

                lvm_groups_info.append(
                    {
                        "Name": vg_name,
                        "Disks": vg_data.get("disks", 0),
                        "LogicalVolumes": vg_data.get("logical_volumes", 0),
                        "TotalSize": (
                            totalsize.replace("g", "GiB").replace("t", "TiB")
                            if totalsize and isinstance(totalsize, str)
                            else totalsize
                        ),
                        "TotalIOPS": total_iops,
                        "TotalMBPS": total_mbps,
                    }
                )

            self.parent.log(
                logging.INFO,
                f"Successfully correlated LVM group info for {len(lvm_groups_info)} volume groups",
            )

        except Exception as ex:
            self.parent.log(logging.ERROR, f"Failed to gather LVM group information: {ex}")

        return lvm_groups_info

    def gather_lvm_volumes_info(self, lvm_volumes):
        """
        Gather correlated LVM logical volume information.

        :param lvm_volumes: LVM volumes from collect_lvm_volumes
        :return: List of LVM volume information dictionaries
        :rtype: List[Dict[str, Any]]
        """
        lvm_volumes_info = []

        try:
            for lv_name, lv_data in lvm_volumes.items():
                size = lv_data.get("size", "")

                lvm_volumes_info.append(
                    {
                        "Name": lv_name,
                        "VGName": lv_data.get("vg_name", ""),
                        "LVPath": lv_data.get("path", ""),
                        "DMPath": lv_data.get("dm_path", ""),
                        "Layout": lv_data.get("layout", ""),
                        "Size": (
                            size.replace("g", "GiB").replace("t", "TiB")
                            if size and isinstance(size, str)
                            else size
                        ),
                        "StripeSize": lv_data.get("stripe_size", ""),
                        "Stripes": lv_data.get("stripes", ""),
                    }
                )

            self.parent.log(
                logging.INFO,
                f"Successfully correlated LVM volume info for {len(lvm_volumes_info)} logical volumes",
            )

        except Exception as ex:
            self.parent.log(logging.ERROR, f"Failed to gather LVM volume information: {ex}")

        return lvm_volumes_info

    def gather_anf_volumes_info(self, filesystems, anf_storage_data):
        """
        Gather ANF volume information for volumes that are actually mounted on the system.
        Extracts pool name and volume name from the ANF resource ID.

        :param filesystems: List of filesystem dictionaries from _parse_filesystem_data
        :param anf_storage_data: Parsed ANF storage metadata
        :return: List of ANF volume information dictionaries
        :rtype: List[Dict[str, Any]]
        """
        anf_volumes_info = []

        try:
            mounted_anf_ips = set()
            for fs in filesystems:
                if fs.get("fstype") in ["nfs", "nfs4"] and fs.get("nfs_type") == "ANF":
                    source = fs.get("source", "")
                    if ":" in source:
                        nfs_address = source.split(":")[0]
                        mounted_anf_ips.add(nfs_address)

            self.parent.log(
                logging.INFO,
                f"Found {len(mounted_anf_ips)} mounted ANF IPs: {mounted_anf_ips}. "
                f"Total ANF volumes in metadata: {len(anf_storage_data)}",
            )

            for anf_volume in anf_storage_data:
                anf_ip = anf_volume.get("ip", "")

                if anf_ip and anf_ip in mounted_anf_ips:
                    resource_id = anf_volume.get("id", "")
                    pool_name = ""
                    vol_name = ""

                    if resource_id:
                        parts = resource_id.split("/")
                        try:
                            if "capacityPools" in parts:
                                pool_idx = parts.index("capacityPools")
                                if pool_idx + 1 < len(parts):
                                    pool_name = parts[pool_idx + 1]
                            if "volumes" in parts:
                                vol_idx = parts.index("volumes")
                                if vol_idx + 1 < len(parts):
                                    vol_name = parts[vol_idx + 1]
                        except (ValueError, IndexError):
                            self.parent.log(
                                logging.WARNING,
                                f"Failed to parse ANF resource ID: {resource_id}",
                            )

                    if not vol_name:
                        name_field = anf_volume.get("name", "")
                        if "/" in name_field:
                            name_parts = name_field.split("/")
                            if len(name_parts) >= 2:
                                pool_name = name_parts[-2] if not pool_name else pool_name
                                vol_name = name_parts[-1]

                    protocol_types = anf_volume.get("protocolTypes", [])
                    if isinstance(protocol_types, list):
                        protocol_str = ", ".join(protocol_types)
                    else:
                        protocol_str = str(protocol_types)

                    anf_volumes_info.append(
                        {
                            "VolumeName": vol_name,
                            "PoolName": pool_name,
                            "ServiceLevel": anf_volume.get("serviceLevel", ""),
                            "ThroughputMibps": anf_volume.get("throughputMibps", 0),
                            "ProtocolTypes": protocol_str,
                            "NFSAddress": anf_ip,
                        }
                    )
                else:
                    if anf_ip:
                        self.parent.log(
                            logging.DEBUG,
                            f"Skipping ANF volume {anf_volume.get('name')} with IP {anf_ip} - not mounted on this system",
                        )
                    else:
                        self.parent.log(
                            logging.DEBUG,
                            f"Skipping ANF volume {anf_volume.get('name')} - no IP address found",
                        )

            self.parent.log(
                logging.INFO,
                f"Successfully gathered ANF volume info for {len(anf_volumes_info)} mounted volumes "
                f"(filtered from {len(anf_storage_data)} total ANF volumes)",
            )

        except Exception as ex:
            self.parent.log(logging.ERROR, f"Failed to gather ANF volume information: {ex}")

        return anf_volumes_info

    def collect(self, check, context) -> Any:
        """
        Collect filesystem information

        :param check: Check object
        :type check: Check
        :param context: Context object
        :type context: Dict[str, Any]
        :return: Filesystem information
        :rtype: Dict[str, Any]
        """
        try:
            lvm_fullreport = context.get("lvm_fullreport", "")
            if not lvm_fullreport or lvm_fullreport == {} or not lvm_fullreport.get("report"):
                self.parent.log(
                    logging.ERROR,
                    f"lvm_fullreport is empty or invalid: {lvm_fullreport}. "
                    f"LVM data collection may have failed. VG-to-disk mapping will not work.",
                )

            lvm_volumes, lvm_groups = self.collect_lvm_volumes(lvm_fullreport)

            findmnt_output = context.get("mount_info", "")
            df_output = context.get("df_info", "")

            raw_anf_data = context.get("anf_storage_metadata", "")
            self.parent.log(
                logging.INFO,
                f"Raw ANF data type: {type(raw_anf_data)}, "
                f"Length: {len(raw_anf_data) if hasattr(raw_anf_data, '__len__') else 'N/A'}, "
                f"First 500 chars: {str(raw_anf_data)[:500]}",
            )

            azure_disk_data = self._parse_metadata(
                context.get("azure_disks_metadata", []), "Azure disk"
            )
            afs_storage_data = self._parse_metadata(
                context.get("afs_storage_metadata", ""), "AFS storage"
            )
            anf_storage_data = self._parse_metadata(raw_anf_data, "ANF storage")
            imds_metadata = self._parse_metadata(
                context.get("imds_disks_metadata", []), "IMDS disk"
            )

            device_lun_map = context.get("device_lun_map", {})
            vg_to_disk_names = {}
            if device_lun_map and imds_metadata:
                vg_to_disk_names = self._map_vg_to_disk_names(
                    lvm_fullreport, imds_metadata, device_lun_map
                )
            elif imds_metadata:
                self.parent.log(
                    logging.WARNING,
                    "device_lun_map not found in context. LVM disk mapping may be incomplete.",
                )

            self.parent.log(
                logging.INFO,
                f"findmnt_output: {findmnt_output}\n"
                f"df_output: {df_output}\n"
                f"Azure disk data type: {type(azure_disk_data)}, Count: {len(azure_disk_data)}\n"
                f"IMDS metadata type: {type(imds_metadata)}, Count: {len(imds_metadata)}\n"
                f"ANF storage data type: {type(anf_storage_data)}, Count: {len(anf_storage_data)}\n"
                f"AFS storage data type: {type(afs_storage_data)}, Count: {len(afs_storage_data)}\n"
                f"VG→disk_names mapping: {vg_to_disk_names}",
            )

            filesystems = self._parse_filesystem_data(
                findmnt_output,
                df_output,
                lvm_volumes,
                lvm_groups,
                azure_disk_data=azure_disk_data,
                anf_storage_data=anf_storage_data,
                afs_storage_data=afs_storage_data,
                vg_to_disk_names=vg_to_disk_names,
            )

            formatted_filesystem_info = self.gather_all_filesystem_info(
                context=context,
                filesystems=filesystems,
                lvm_volumes=lvm_volumes,
                vg_to_disk_names=vg_to_disk_names,
            )

            azure_disks_info = self.gather_azure_disks_info(
                context=context,
                lvm_fullreport=lvm_fullreport,
                device_lun_map=device_lun_map,
            )

            lvm_groups_info = self.gather_lvm_groups_info(
                lvm_groups=lvm_groups,
                vg_to_disk_names=vg_to_disk_names,
                azure_disk_data=azure_disk_data,
            )

            lvm_volumes_info = self.gather_lvm_volumes_info(
                lvm_volumes=lvm_volumes,
            )

            anf_volumes_info = self.gather_anf_volumes_info(
                filesystems=filesystems,
                anf_storage_data=anf_storage_data,
            )

            return {
                "filesystems": filesystems,
                "lvm_volumes": lvm_volumes,
                "lvm_groups": lvm_groups,
                "formatted_filesystem_info": formatted_filesystem_info,
                "azure_disks_info": azure_disks_info,
                "lvm_groups_info": lvm_groups_info,
                "lvm_volumes_info": lvm_volumes_info,
                "anf_volumes_info": anf_volumes_info,
            }

        except Exception as ex:
            self.parent.handle_error(ex)
            return {"ERROR: Filesystem data collection failed": str(ex)}
