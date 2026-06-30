# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# pylint: disable=line-too-long,too-many-lines

"""
Shared dummy CIB/constants test data for the get_pcmk_properties_db and
get_pcmk_properties_scs module unit tests.
"""

# DB pacemaker test data

DB_DUMMY_XML_RSC = """<rsc_defaults>
  <meta_attributes id="build-resource-defaults">
    <nvpair id="build-resource-stickiness" name="resource-stickiness" value="1000"/>
    <nvpair name="migration-threshold" value="5000"/>
  </meta_attributes>
</rsc_defaults>"""

DB_DUMMY_XML_OP = """<op_defaults>
  <meta_attributes id="op-options">
    <nvpair name="timeout" value="600"/>
    <nvpair name="record-pending" value="true"/>
  </meta_attributes>
</op_defaults>"""

DB_DUMMY_XML_CRM = """<crm_config>
  <cluster_property_set id="cib-bootstrap-options">
    <nvpair name="stonith-enabled" value="true"/>
    <nvpair name="cluster-name" value="hdb_HDB"/>
    <nvpair name="maintenance-mode" value="false"/>
  </cluster_property_set>
</crm_config>"""

DB_DUMMY_XML_CONSTRAINTS = """<constraints>
  <rsc_colocation id="col_saphana_ip" score="4000" rsc="g_ip_HDB_HDB00" with-rsc="msl_SAPHana_HDB_HDB00"/>
  <rsc_order id="ord_SAPHana" kind="Optional" first="cln_SAPHanaTopology_HDB_HDB00" then="msl_SAPHana_HDB_HDB00"/>
</constraints>"""

DB_DUMMY_XML_RESOURCES = """<resources>
  <primitive id="stonith-sbd" class="stonith" type="external/sbd">
    <instance_attributes id="stonith-sbd-instance_attributes">
      <nvpair id="stonith-sbd-instance_attributes-pcmk_delay_max" name="pcmk_delay_max" value="30s"/>
      <nvpair name="login" value="12345-12345-12345-12345-12345" id="rsc_st_azure-instance_attributes-login"/>
      <nvpair name="passwd" value="********" id="rsc_st_azure-instance_attributes-passwd"/>
    </instance_attributes>
    <meta_attributes id="stonith-sbd-meta_attributes">
      <nvpair name="target-role" value="Started"/>
    </meta_attributes>
    <operations id="stonith-sbd-operations">
      <op name="monitor" interval="10" timeout="600" id="stonith-sbd-monitor"/>
      <op name="start" interval="0" timeout="20" id="stonith-sbd-start"/>
    </operations>
  </primitive>
  <clone id="cln_SAPHanaTopology_HDB_HDB00">
    <meta_attributes id="cln_SAPHanaTopology_HDB_HDB00-meta_attributes">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="target-role" value="Started"/>
    </meta_attributes>
    <primitive id="rsc_SAPHanaTopology_HDB_HDB00" class="ocf" provider="suse" type="SAPHanaTopology">
      <operations id="rsc_sap2_HDB_HDB00-operations">
        <op name="monitor" interval="10" timeout="600"/>
      </operations>
      <instance_attributes id="rsc_SAPHanaTopology_HDB_HDB00-instance_attributes">
        <nvpair name="SID" value="HDB"/>
        <nvpair name="InstanceNumber" value="00"/>
      </instance_attributes>
    </primitive>
  </clone>
  <master id="msl_SAPHana_HDB_HDB00">
    <meta_attributes id="msl_SAPHana_HDB_HDB00-meta_attributes">
      <nvpair name="clone-max" value="2"/>
      <nvpair name="target-role" value="Started"/>
    </meta_attributes>
    <primitive id="rsc_SAPHana_HDB_HDB00" class="ocf" provider="suse" type="SAPHana">
      <instance_attributes id="rsc_SAPHana_HDB_HDB00-instance_attributes">
        <nvpair name="SID" value="HDB"/>
        <nvpair name="InstanceNumber" value="00"/>
      </instance_attributes>
    </primitive>
  </master>
  <primitive id="rsc_ip_HDB_HDB00" class="ocf" provider="heartbeat" type="IPaddr2">
    <instance_attributes>
      <nvpair name="ip" value="127.0.0.1"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_azure_lb" class="ocf" provider="heartbeat" type="azure-lb">
    <instance_attributes>
      <nvpair name="port" value="62500"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_filesystem" class="ocf" provider="heartbeat" type="Filesystem">
    <instance_attributes>
      <nvpair name="device" value="/dev/sda1"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_fence_azure" class="stonith" type="fence_azure_arm">
    <instance_attributes>
      <nvpair name="login" value="testuser"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_angi_fs" class="ocf" provider="suse" type="SAPHanaFilesystem">
    <instance_attributes>
      <nvpair name="filesystem" value="/hana/data"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_angi_controller" class="ocf" provider="suse" type="SAPHanaController">
    <instance_attributes>
      <nvpair name="SID" value="HDB"/>
    </instance_attributes>
  </primitive>
  <clone id="hana_nfs_s1_active-clone">
    <meta_attributes id="hana_nfs_s1_active-clone-meta_attributes">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="hana_nfs_s1_active" class="ocf" provider="pacemaker" type="attribute">
      <instance_attributes id="hana_nfs_s1_active-instance_attributes">
        <nvpair name="active_value" value="true"/>
        <nvpair name="inactive_value" value="false"/>
        <nvpair name="name" value="hana_nfs_s1_active"/>
      </instance_attributes>
    </primitive>
  </clone>
  <clone id="hana_nfs_s2_active-clone">
    <meta_attributes id="hana_nfs_s2_active-clone-meta_attributes">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="hana_nfs_s2_active" class="ocf" provider="pacemaker" type="attribute">
      <instance_attributes id="hana_nfs_s2_active-instance_attributes">
        <nvpair name="active_value" value="true"/>
        <nvpair name="inactive_value" value="false"/>
        <nvpair name="name" value="hana_nfs_s2_active"/>
      </instance_attributes>
    </primitive>
  </clone>
</resources>"""

DB_DUMMY_XML_FULL_CIB = f"""<?xml version="1.0" encoding="UTF-8"?>
<cib>
  <configuration>
    {DB_DUMMY_XML_CRM}
    {DB_DUMMY_XML_RSC}
    {DB_DUMMY_XML_OP}
    {DB_DUMMY_XML_CONSTRAINTS}
    {DB_DUMMY_XML_RESOURCES}
  </configuration>
</cib>"""

DB_DUMMY_XML_SCALEOUT_RESOURCES = """<resources>
  <primitive id="stonith-sbd" class="stonith" type="external/sbd">
    <instance_attributes id="stonith-sbd-instance_attributes">
      <nvpair name="pcmk_delay_max" value="30s"/>
    </instance_attributes>
    <operations id="stonith-sbd-operations">
      <op name="monitor" interval="10" timeout="600"/>
    </operations>
  </primitive>
  <primitive id="rsc_fence_azure" class="stonith" type="fence_azure_arm">
    <instance_attributes>
      <nvpair name="login" value="testuser"/>
    </instance_attributes>
  </primitive>
  <clone id="fs_hana_shared_s1-clone">
    <meta_attributes id="fs_hana_shared_s1-clone-meta">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="fs_hana_shared_s1" class="ocf" provider="heartbeat" type="Filesystem">
      <instance_attributes id="fs_hana_shared_s1-instance_attributes">
        <nvpair name="device" value="10.23.1.7:/HN1-shared-s1"/>
        <nvpair name="directory" value="/hana/shared"/>
        <nvpair name="fstype" value="nfs"/>
        <nvpair name="fast_stop" value="no"/>
      </instance_attributes>
      <operations>
        <op name="monitor" interval="20" timeout="120"/>
        <op name="start" interval="0" timeout="120"/>
        <op name="stop" interval="0" timeout="120"/>
      </operations>
    </primitive>
  </clone>
  <clone id="fs_hana_shared_s2-clone">
    <meta_attributes id="fs_hana_shared_s2-clone-meta">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="fs_hana_shared_s2" class="ocf" provider="heartbeat" type="Filesystem">
      <instance_attributes id="fs_hana_shared_s2-instance_attributes">
        <nvpair name="device" value="10.23.1.7:/HN1-shared-s2"/>
        <nvpair name="directory" value="/hana/shared"/>
        <nvpair name="fstype" value="nfs"/>
        <nvpair name="fast_stop" value="no"/>
      </instance_attributes>
      <operations>
        <op name="monitor" interval="20" timeout="120"/>
        <op name="start" interval="0" timeout="120"/>
        <op name="stop" interval="0" timeout="120"/>
      </operations>
    </primitive>
  </clone>
  <clone id="hana_nfs_s1_active-clone">
    <meta_attributes id="hana_nfs_s1_active-clone-meta">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="hana_nfs_s1_active" class="ocf" provider="pacemaker" type="attribute">
      <instance_attributes id="hana_nfs_s1_active-instance_attributes">
        <nvpair name="active_value" value="true"/>
        <nvpair name="inactive_value" value="false"/>
        <nvpair name="name" value="hana_nfs_s1_active"/>
      </instance_attributes>
    </primitive>
  </clone>
  <clone id="hana_nfs_s2_active-clone">
    <meta_attributes id="hana_nfs_s2_active-clone-meta">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="hana_nfs_s2_active" class="ocf" provider="pacemaker" type="attribute">
      <instance_attributes id="hana_nfs_s2_active-instance_attributes">
        <nvpair name="active_value" value="true"/>
        <nvpair name="inactive_value" value="false"/>
        <nvpair name="name" value="hana_nfs_s2_active"/>
      </instance_attributes>
    </primitive>
  </clone>
  <clone id="cln_SAPHanaTopology_HN1_HDB03-clone">
    <meta_attributes id="cln_SAPHanaTopology_HN1_HDB03-clone-meta">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="rsc_SAPHanaTopology_HN1_HDB03" class="ocf" provider="heartbeat" type="SAPHanaTopology">
      <instance_attributes>
        <nvpair name="SID" value="HN1"/>
        <nvpair name="InstanceNumber" value="03"/>
      </instance_attributes>
      <operations>
        <op name="monitor" interval="10" timeout="600"/>
        <op name="start" interval="0" timeout="600"/>
        <op name="stop" interval="0" timeout="300"/>
      </operations>
    </primitive>
  </clone>
  <primitive id="rsc_SAPHana_HN1_HDB03" class="ocf" provider="heartbeat" type="SAPHanaController">
    <instance_attributes id="rsc_SAPHana_HN1_HDB03-instance_attributes">
      <nvpair name="SID" value="HN1"/>
      <nvpair name="InstanceNumber" value="03"/>
      <nvpair name="PREFER_SITE_TAKEOVER" value="true"/>
      <nvpair name="DUPLICATE_PRIMARY_TIMEOUT" value="7200"/>
      <nvpair name="AUTOMATED_REGISTER" value="false"/>
    </instance_attributes>
    <operations>
      <op name="start" interval="0" timeout="3600"/>
      <op name="stop" interval="0" timeout="3600"/>
      <op name="promote" interval="0" timeout="3600"/>
      <op name="demote" interval="0" timeout="320"/>
      <op name="monitor" interval="60" timeout="700"/>
    </operations>
  </primitive>
  <primitive id="rsc_ip_HN1_HDB03" class="ocf" provider="heartbeat" type="IPaddr2">
    <instance_attributes>
      <nvpair name="ip" value="10.23.0.18"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_azure_lb" class="ocf" provider="heartbeat" type="azure-lb">
    <instance_attributes>
      <nvpair name="port" value="62503"/>
    </instance_attributes>
  </primitive>
</resources>"""

DB_DUMMY_XML_SCALEOUT_CIB = f"""<?xml version="1.0" encoding="UTF-8"?>
<cib>
  <configuration>
    {DB_DUMMY_XML_CRM}
    {DB_DUMMY_XML_RSC}
    {DB_DUMMY_XML_OP}
    {DB_DUMMY_XML_CONSTRAINTS}
    {DB_DUMMY_XML_SCALEOUT_RESOURCES}
  </configuration>
</cib>"""

DB_DUMMY_GLOBAL_INI_SCALEOUT = """[DEFAULT]
dummy1 = dummy2

[ha_dr_provider_SAPHanaSR]
provider = SAPHanaSR
path = /usr/share/SAPHanaSR-ScaleOut
execution_order = 1

[ha_dr_provider_chksrv]
provider = ChkSrv
path = /usr/share/SAPHanaSR-ScaleOut
execution_order = 2
action_on_lost = kill

[trace]
ha_dr_saphanasr = info
ha_dr_chksrv = info
"""

DB_DUMMY_XML_RHEL_ANGI_RESOURCES = """<resources>
  <primitive id="rsc_st_azure" class="stonith" type="fence_azure_arm">
    <instance_attributes>
      <nvpair name="msi" value="true"/>
    </instance_attributes>
  </primitive>
  <clone id="cln_SAPHanaTopology_HDB_HDB00">
    <meta_attributes id="cln_SAPHanaTopology_HDB_HDB00-meta_attributes">
      <nvpair name="clone-max" value="2"/>
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="rsc_SAPHanaTopology_HDB_HDB00" class="ocf" provider="heartbeat" type="SAPHanaTopology">
      <instance_attributes>
        <nvpair name="SID" value="HDB"/>
        <nvpair name="InstanceNumber" value="00"/>
      </instance_attributes>
      <operations>
        <op name="monitor" interval="30" timeout="300"/>
        <op name="start" interval="0" timeout="600"/>
        <op name="stop" interval="0" timeout="300"/>
      </operations>
    </primitive>
  </clone>
  <clone id="cln_SAPHanaController_HDB_HDB00">
    <meta_attributes id="cln_SAPHanaController_HDB_HDB00-meta_attributes">
      <nvpair name="clone-max" value="2"/>
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
      <nvpair name="promotable" value="true"/>
    </meta_attributes>
    <primitive id="rsc_SAPHanaController_HDB_HDB00" class="ocf" provider="heartbeat" type="SAPHanaController">
      <instance_attributes id="rsc_SAPHanaController_HDB_HDB00-instance_attributes">
        <nvpair name="SID" value="HDB"/>
        <nvpair name="InstanceNumber" value="00"/>
        <nvpair name="PREFER_SITE_TAKEOVER" value="true"/>
        <nvpair name="DUPLICATE_PRIMARY_TIMEOUT" value="7200"/>
        <nvpair name="AUTOMATED_REGISTER" value="true"/>
      </instance_attributes>
      <meta_attributes id="rsc_SAPHanaController_HDB_HDB00-meta_attributes">
        <nvpair name="priority" value="10"/>
      </meta_attributes>
      <operations>
        <op name="start" interval="0" timeout="3600"/>
        <op name="stop" interval="0" timeout="3600"/>
        <op name="promote" interval="0" timeout="900"/>
        <op name="demote" interval="0" timeout="320"/>
        <op name="monitor" interval="59" timeout="700" role="Promoted"/>
        <op name="monitor" interval="61" timeout="700" role="Unpromoted"/>
      </operations>
    </primitive>
  </clone>
  <clone id="cln_SAPHanaFilesystem_HDB_HDB00">
    <meta_attributes id="cln_SAPHanaFilesystem_HDB_HDB00-meta_attributes">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="rsc_SAPHanaFilesystem_HDB_HDB00" class="ocf" provider="heartbeat" type="SAPHanaFilesystem">
      <instance_attributes>
        <nvpair name="SID" value="HDB"/>
        <nvpair name="InstanceNumber" value="00"/>
        <nvpair name="ON_FAIL_ACTION" value="fence"/>
      </instance_attributes>
      <operations>
        <op name="monitor" interval="120" timeout="120"/>
        <op name="start" interval="0" timeout="10"/>
        <op name="stop" interval="0" timeout="20"/>
      </operations>
    </primitive>
  </clone>
  <primitive id="rsc_ip_HDB_HDB00" class="ocf" provider="heartbeat" type="IPaddr2">
    <instance_attributes>
      <nvpair name="ip" value="172.238.1.36"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_nc_HDB_HDB00" class="ocf" provider="heartbeat" type="azure-lb">
    <instance_attributes>
      <nvpair name="port" value="62500"/>
    </instance_attributes>
  </primitive>
</resources>"""

DB_DUMMY_XML_RHEL_ANGI_CIB = f"""<?xml version="1.0" encoding="UTF-8"?>
<cib>
  <configuration>
    {DB_DUMMY_XML_CRM}
    {DB_DUMMY_XML_RSC}
    {DB_DUMMY_XML_OP}
    {DB_DUMMY_XML_CONSTRAINTS}
    {DB_DUMMY_XML_RHEL_ANGI_RESOURCES}
  </configuration>
</cib>"""

DB_DUMMY_XML_RHEL_ANGI_SCALEOUT_RESOURCES = """<resources>
  <primitive id="rsc_st_azure" class="stonith" type="fence_azure_arm">
    <instance_attributes>
      <nvpair name="msi" value="true"/>
    </instance_attributes>
  </primitive>
  <clone id="fs_HN1_HDB03_fscheck-clone">
    <meta_attributes id="fs_HN1_HDB03_fscheck-clone-meta_attributes">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="fs_HN1_HDB03_fscheck" class="ocf" provider="heartbeat" type="Filesystem">
      <instance_attributes>
        <nvpair name="device" value="172.61.1.7:/HN1-shared-s1"/>
        <nvpair name="directory" value="/hana/shared"/>
        <nvpair name="fstype" value="nfs"/>
        <nvpair name="fast_stop" value="no"/>
      </instance_attributes>
      <operations>
        <op name="monitor" interval="20" timeout="120"/>
        <op name="start" interval="0" timeout="120"/>
        <op name="stop" interval="0" timeout="120"/>
      </operations>
    </primitive>
  </clone>
  <clone id="hana_nfs_s1_active-clone">
    <meta_attributes id="hana_nfs_s1_active-clone-meta">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="hana_nfs_s1_active" class="ocf" provider="pacemaker" type="attribute">
      <instance_attributes>
        <nvpair name="active_value" value="true"/>
        <nvpair name="inactive_value" value="false"/>
        <nvpair name="name" value="hana_nfs_s1_active"/>
      </instance_attributes>
    </primitive>
  </clone>
  <clone id="cln_SAPHanaTopology_HN1_HDB03">
    <meta_attributes id="cln_SAPHanaTopology_HN1_HDB03-meta_attributes">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="rsc_SAPHanaTopology_HN1_HDB03" class="ocf" provider="heartbeat" type="SAPHanaTopology">
      <instance_attributes>
        <nvpair name="SID" value="HN1"/>
        <nvpair name="InstanceNumber" value="03"/>
      </instance_attributes>
      <operations>
        <op name="monitor" interval="30" timeout="300"/>
        <op name="start" interval="0" timeout="600"/>
        <op name="stop" interval="0" timeout="300"/>
      </operations>
    </primitive>
  </clone>
  <clone id="cln_SAPHanaFilesystem_HN1_HDB03">
    <meta_attributes id="cln_SAPHanaFilesystem_HN1_HDB03-meta_attributes">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="interleave" value="true"/>
    </meta_attributes>
    <primitive id="rsc_SAPHanaFilesystem_HN1_HDB03" class="ocf" provider="heartbeat" type="SAPHanaFilesystem">
      <instance_attributes>
        <nvpair name="SID" value="HN1"/>
        <nvpair name="InstanceNumber" value="03"/>
        <nvpair name="ON_FAIL_ACTION" value="fence"/>
      </instance_attributes>
      <operations>
        <op name="monitor" interval="120" timeout="120"/>
        <op name="start" interval="0" timeout="10"/>
        <op name="stop" interval="0" timeout="20"/>
      </operations>
    </primitive>
  </clone>
  <clone id="cln_SAPHanaController_HN1_HDB03">
    <meta_attributes id="cln_SAPHanaController_HN1_HDB03-meta_attributes">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="master-max" value="1"/>
      <nvpair name="interleave" value="true"/>
      <nvpair name="promotable" value="true"/>
    </meta_attributes>
    <primitive id="rsc_SAPHanaController_HN1_HDB03" class="ocf" provider="heartbeat" type="SAPHanaController">
      <instance_attributes id="rsc_SAPHanaController_HN1_HDB03-instance_attributes">
        <nvpair name="SID" value="HN1"/>
        <nvpair name="InstanceNumber" value="03"/>
        <nvpair name="PREFER_SITE_TAKEOVER" value="true"/>
        <nvpair name="DUPLICATE_PRIMARY_TIMEOUT" value="7200"/>
        <nvpair name="AUTOMATED_REGISTER" value="true"/>
      </instance_attributes>
      <meta_attributes id="rsc_SAPHanaController_HN1_HDB03-meta_attributes">
        <nvpair name="priority" value="100"/>
      </meta_attributes>
      <operations>
        <op name="start" interval="0" timeout="3600"/>
        <op name="stop" interval="0" timeout="3600"/>
        <op name="promote" interval="0" timeout="900"/>
        <op name="demote" interval="0" timeout="320"/>
        <op name="monitor" interval="59" timeout="700" role="Promoted"/>
        <op name="monitor" interval="61" timeout="700" role="Unpromoted"/>
      </operations>
    </primitive>
  </clone>
  <primitive id="rsc_ip_HN1_HDB03" class="ocf" provider="heartbeat" type="IPaddr2">
    <instance_attributes>
      <nvpair name="ip" value="172.61.0.11"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_nc_HN1_HDB03" class="ocf" provider="heartbeat" type="azure-lb">
    <instance_attributes>
      <nvpair name="port" value="62503"/>
    </instance_attributes>
  </primitive>
</resources>"""

DB_DUMMY_XML_RHEL_ANGI_SCALEOUT_CIB = f"""<?xml version="1.0" encoding="UTF-8"?>
<cib>
  <configuration>
    {DB_DUMMY_XML_CRM}
    {DB_DUMMY_XML_RSC}
    {DB_DUMMY_XML_OP}
    {DB_DUMMY_XML_CONSTRAINTS}
    {DB_DUMMY_XML_RHEL_ANGI_SCALEOUT_RESOURCES}
  </configuration>
</cib>"""

DB_DUMMY_GLOBAL_INI_RHEL_ANGI = """[DEFAULT]
dummy1 = dummy2

[ha_dr_provider_hanasr]
provider = HanaSR
path = /usr/share/sap-hana-ha/
execution_order = 1

[ha_dr_provider_chksrv]
provider = ChkSrv
path = /usr/share/sap-hana-ha/
execution_order = 2
action_on_lost = stop

[trace]
ha_dr_hanasr = info
ha_dr_chksrv = info
"""

DB_DUMMY_OS_COMMAND = """kernel.numa_balancing = 0"""

DB_DUMMY_GLOBAL_INI_SAPHANASR = """[DEFAULT]
dummy1 = dummy2

[ha_dr_provider_SAPHanaSR]
provider = SAPHanaSR
path = /usr/share/SAPHanaSR
execution_order = 1

[ha_dr_provider_suschksrv]
provider = susChkSrv
path = /usr/share/SAPHanaSR
execution_order = 3
action_on_host = fence

[trace]
ha_dr_sushanasr = info
"""

DB_DUMMY_GLOBAL_INI_ANGI = """[DEFAULT]
dummy1 = dummy2

[ha_dr_provider_sushanasr]
provider = susHanaSR
path = /usr/share/SAPHanaSR-angi
execution_order = 1

[ha_dr_provider_suschksrv]
provider = susChkSrv
path = /usr/share/SAPHanaSR-angi
execution_order = 3
action_on_host = fence

[trace]
ha_dr_sushanasr = info
ha_dr_suschksrv = info
"""

DB_DUMMY_CONSTANTS = {
    "VALID_CONFIGS": {
        "REDHAT": {
            "stonith-enabled": {"value": "true", "required": False},
            "cluster-name": {"value": "hdb_HDB", "required": False},
        },
        "azure-fence-agent": {"priority": {"value": "10", "required": False}},
        "sbd": {"pcmk_delay_max": {"value": "30", "required": False}},
        "scale_out_hsr": {
            "migration-threshold": {"value": ["50"], "required": True},
        },
        "angi_scale_up": {
            "node-health-strategy": {"value": "custom", "required": True},
            "concurrent-fencing": {"value": "true", "required": False},
        },
    },
    "RSC_DEFAULTS": {
        "resource-stickiness": {"value": "1000", "required": False},
        "migration-threshold": {"value": "5000", "required": False},
    },
    "OP_DEFAULTS": {
        "timeout": {"value": "600", "required": False},
        "record-pending": {"value": "true", "required": False},
    },
    "CRM_CONFIG_DEFAULTS": {
        "stonith-enabled": {"value": "true", "required": False},
        "maintenance-mode": {"value": "false", "required": False},
    },
    "RESOURCE_DEFAULTS": {
        "REDHAT": {
            "fence_agent": {
                "meta_attributes": {
                    "pcmk_delay_max": {"value": "15", "required": False},
                    "target-role": {"value": "Started", "required": False},
                },
                "operations": {
                    "monitor": {
                        "timeout": {"value": ["700", "700s"], "required": False},
                        "interval": {"value": "10", "required": False},
                    },
                    "start": {"timeout": {"value": "20", "required": False}},
                },
                "instance_attributes": {"login": {"value": "testuser", "required": False}},
            },
            "sbd_stonith": {
                "meta_attributes": {
                    "pcmk_delay_max": {"value": "30", "required": False},
                    "target-role": {"value": "Started", "required": False},
                },
                "operations": {
                    "monitor": {
                        "timeout": {"value": ["30", "30s"], "required": False},
                        "interval": {"value": "10", "required": False},
                    },
                    "start": {"timeout": {"value": "20", "required": False}},
                },
            },
            "hana": {
                "meta_attributes": {"clone-max": {"value": "2", "required": False}},
                "operations": {
                    "monitor": {"timeout": {"value": ["600", "600s"], "required": False}}
                },
                "instance_attributes": {"SID": {"value": "HDB", "required": False}},
            },
            "scaleout_filesystem": {
                "instance_attributes": {
                    "fast_stop": {"value": "no", "required": False},
                },
                "meta_attributes": {
                    "clone-node-max": {"value": "1", "required": False},
                    "interleave": {"value": "true", "required": False},
                },
                "operations": {
                    "monitor": {
                        "interval": {"value": ["20", "20s"], "required": False},
                        "timeout": {"value": ["120", "120s"], "required": False},
                    },
                },
            },
            "nfs_attribute": {
                "instance_attributes": {
                    "active_value": {"value": "true", "required": False},
                    "inactive_value": {"value": "false", "required": False},
                },
                "meta_attributes": {
                    "clone-node-max": {"value": "1", "required": False},
                    "interleave": {"value": "true", "required": False},
                },
            },
            "scaleout_hana": {
                "meta_attributes": {
                    "notify": {"value": "true", "required": False},
                    "clone-node-max": {"value": "1", "required": False},
                },
                "instance_attributes": {
                    "SID": {"value": "HN1", "required": False},
                    "PREFER_SITE_TAKEOVER": {"value": "true", "required": False},
                    "AUTOMATED_REGISTER": {"value": "true", "required": False},
                },
                "operations": {
                    "monitor": {
                        "timeout": {"value": ["700", "700s"], "required": False},
                    },
                },
            },
            "scaleout_topology": {
                "meta_attributes": {
                    "clone-node-max": {"value": "1", "required": False},
                    "interleave": {"value": "true", "required": False},
                },
                "operations": {
                    "monitor": {
                        "interval": {"value": ["10", "10s"], "required": False},
                        "timeout": {"value": ["600", "600s"], "required": False},
                    },
                },
            },
            "angi_topology": {
                "meta_attributes": {
                    "clone-max": {"value": "2", "required": False},
                    "clone-node-max": {"value": "1", "required": False},
                    "interleave": {"value": "true", "required": False},
                },
                "operations": {
                    "monitor": {
                        "interval": {"value": ["30", "30s"], "required": False},
                        "timeout": {"value": ["300", "300s"], "required": False},
                    },
                    "start": {"timeout": {"value": ["600", "600s"], "required": False}},
                    "stop": {"timeout": {"value": ["300", "300s"], "required": False}},
                },
            },
            "angi_hana": {
                "meta_attributes": {
                    "clone-max": {"value": "2", "required": False},
                    "clone-node-max": {"value": "1", "required": False},
                    "interleave": {"value": "true", "required": False},
                    "promotable": {"value": "true", "required": False},
                    "priority": {"value": "10", "required": False},
                },
                "instance_attributes": {
                    "PREFER_SITE_TAKEOVER": {"value": "true", "required": False},
                    "DUPLICATE_PRIMARY_TIMEOUT": {"value": "7200", "required": False},
                    "AUTOMATED_REGISTER": {"value": "true", "required": False},
                },
                "operations": {
                    "promote": {"timeout": {"value": ["900", "900s"], "required": False}},
                    "demote": {"timeout": {"value": ["320", "320s"], "required": False}},
                    "monitor": {
                        "interval": {
                            "value": ["59", "59s", "61", "61s"],
                            "required": False,
                        },
                        "timeout": {"value": ["700", "700s"], "required": False},
                    },
                    "start": {"timeout": {"value": ["3600", "3600s"], "required": False}},
                    "stop": {"timeout": {"value": ["3600", "3600s"], "required": False}},
                },
            },
            "angi_scaleout_hana": {
                "meta_attributes": {
                    "clone-node-max": {"value": "1", "required": False},
                    "master-max": {"value": "1", "required": False},
                    "interleave": {"value": "true", "required": False},
                    "promotable": {"value": "true", "required": False},
                    "priority": {"value": "100", "required": False},
                },
                "instance_attributes": {
                    "PREFER_SITE_TAKEOVER": {"value": "true", "required": False},
                    "DUPLICATE_PRIMARY_TIMEOUT": {"value": "7200", "required": False},
                    "AUTOMATED_REGISTER": {"value": "true", "required": False},
                },
                "operations": {
                    "promote": {
                        "timeout": {
                            "value": ["900", "900s", "3600", "3600s"],
                            "required": False,
                        }
                    },
                    "demote": {"timeout": {"value": ["320", "320s"], "required": False}},
                    "monitor": {
                        "interval": {
                            "value": ["59", "59s", "60", "60s", "61", "61s"],
                            "required": False,
                        },
                        "timeout": {"value": ["700", "700s"], "required": False},
                    },
                    "start": {"timeout": {"value": ["3600", "3600s"], "required": False}},
                    "stop": {"timeout": {"value": ["3600", "3600s"], "required": False}},
                },
            },
            "angi_filesystem": {
                "instance_attributes": {
                    "ON_FAIL_ACTION": {"value": "fence", "required": False},
                },
                "meta_attributes": {
                    "clone-node-max": {"value": "1", "required": False},
                    "interleave": {"value": "true", "required": False},
                },
                "operations": {
                    "monitor": {
                        "interval": {"value": ["120", "120s"], "required": False},
                        "timeout": {"value": ["120", "120s"], "required": False},
                    },
                },
            },
        }
    },
    "OS_PARAMETERS": {
        "DEFAULTS": {
            "sysctl": {
                "kernel.numa_balancing": {"value": "kernel.numa_balancing = 0", "required": False}
            }
        }
    },
    "GLOBAL_INI": {
        "REDHAT": {
            "SAPHanaSR": {
                "ha_dr_provider_SAPHanaSR": {
                    "provider": {"value": "SAPHanaSR", "required": True},
                    "path": {
                        "value": ["/usr/share/SAPHanaSR", "/hana/shared/myHooks"],
                        "required": True,
                    },
                    "execution_order": {"value": "1", "required": True},
                },
                "ha_dr_provider_suschksrv": {
                    "provider": {"value": "susChkSrv", "required": True},
                    "path": {
                        "value": ["/usr/share/SAPHanaSR", "/hana/shared/myHooks"],
                        "required": True,
                    },
                    "execution_order": {"value": "3", "required": True},
                    "action_on_host": {"value": "fence", "required": True},
                },
                "trace": {
                    "ha_dr_sushanasr": {"required": False},
                },
            },
            "SAPHanaController": {
                "ha_dr_provider_SAPHanaSR": {
                    "provider": {"value": "SAPHanaSR", "required": True},
                    "path": {
                        "value": [
                            "/usr/share/SAPHanaSR-ScaleOut",
                            "/hana/shared/myHooks",
                        ],
                        "required": True,
                    },
                    "execution_order": {"value": "1", "required": True},
                },
                "ha_dr_provider_chksrv": {
                    "provider": {"value": "ChkSrv", "required": True},
                    "path": {
                        "value": [
                            "/usr/share/SAPHanaSR-ScaleOut",
                            "/hana/shared/myHooks",
                        ],
                        "required": True,
                    },
                    "execution_order": {"value": "2", "required": True},
                    "action_on_lost": {"value": "kill", "required": True},
                },
                "trace": {
                    "ha_dr_saphanasr": {"required": False},
                    "ha_dr_chksrv": {"required": False},
                },
            },
            "SAPHanaSR-angi": {
                "ha_dr_provider_hanasr": {
                    "provider": {"value": "HanaSR", "required": True},
                    "path": {
                        "value": ["/usr/share/sap-hana-ha", "/hana/shared/myHooks"],
                        "required": True,
                    },
                    "execution_order": {"value": "1", "required": True},
                },
                "ha_dr_provider_chksrv": {
                    "provider": {"value": "ChkSrv", "required": True},
                    "path": {
                        "value": ["/usr/share/sap-hana-ha", "/hana/shared/myHooks"],
                        "required": True,
                    },
                    "execution_order": {"value": "2", "required": True},
                    "action_on_lost": {"value": "stop", "required": True},
                },
                "trace": {
                    "ha_dr_hanasr": {"required": False},
                    "ha_dr_chksrv": {"required": False},
                },
            },
        },
        "SUSE": {
            "SAPHanaSR-angi": {
                "ha_dr_provider_sushanasr": {
                    "provider": {"value": "susHanaSR", "required": True},
                    "path": {
                        "value": ["/usr/share/SAPHanaSR-angi", "/hana/shared/myHooks"],
                        "required": True,
                    },
                    "execution_order": {"value": "1", "required": True},
                },
                "ha_dr_provider_suschksrv": {
                    "provider": {"value": "susChkSrv", "required": True},
                    "path": {
                        "value": ["/usr/share/SAPHanaSR-angi", "/hana/shared/myHooks"],
                        "required": True,
                    },
                    "execution_order": {"value": "3", "required": True},
                    "action_on_host": {"value": "fence", "required": True},
                },
                "trace": {
                    "ha_dr_sushanasr": {"required": False},
                    "ha_dr_suschksrv": {"required": False},
                },
            }
        },
    },
    "CONSTRAINTS": {
        "rsc_location": {"score": {"value": "INFINITY", "required": False}},
        "rsc_colocation": {"score": {"value": "4000", "required": False}},
        "rsc_order": {"kind": {"value": "Optional", "required": False}},
    },
}

# SCS pacemaker test data

SCS_DUMMY_XML_RSC = """<rsc_defaults>
  <meta_attributes id="build-resource-defaults">
    <nvpair id="build-resource-stickiness" name="resource-stickiness" value="1000"/>
    <nvpair name="migration-threshold" value="5000"/>
  </meta_attributes>
</rsc_defaults>"""

SCS_DUMMY_XML_OP = """<op_defaults>
  <meta_attributes id="op-options">
    <nvpair name="timeout" value="600"/>
    <nvpair name="record-pending" value="true"/>
  </meta_attributes>
</op_defaults>"""

SCS_DUMMY_XML_CRM = """<crm_config>
  <cluster_property_set id="cib-bootstrap-options">
    <nvpair name="stonith-enabled" value="true"/>
    <nvpair name="cluster-name" value="scs_S4D"/>
    <nvpair name="maintenance-mode" value="false"/>
  </cluster_property_set>
</crm_config>"""

SCS_DUMMY_XML_CONSTRAINTS = """<constraints>
  <rsc_colocation id="col_scs_ip" score="4000" rsc="g_ip_S4D_ASCS00" with-rsc="rsc_sap_S4D_ASCS00"/>
  <rsc_order id="ord_SCS" kind="Optional" first="rsc_sap_S4D_ASCS00" then="rsc_sap_S4D_ERS10"/>
  <rsc_location id="loc_test" score="INFINITY" rsc="test_resource"/>
</constraints>"""

SCS_DUMMY_XML_RESOURCES = """<resources>
  <primitive id="stonith-sbd" class="stonith" type="external/sbd">
    <instance_attributes id="stonith-sbd-instance_attributes">
      <nvpair id="stonith-sbd-instance_attributes-pcmk_delay_max" name="pcmk_delay_max" value="30s"/>
      <nvpair name="login" value="12345-12345-12345-12345-12345" id="rsc_st_azure-instance_attributes-login"/>
      <nvpair name="password" value="********" id="rsc_st_azure-instance_attributes-password"/>
    </instance_attributes>
    <meta_attributes id="stonith-sbd-meta_attributes">
      <nvpair name="target-role" value="Started"/>
    </meta_attributes>
    <operations id="stonith-sbd-operations">
      <op name="monitor" interval="10" timeout="600" id="stonith-sbd-monitor"/>
      <op name="start" interval="0" timeout="20" id="stonith-sbd-start"/>
    </operations>
  </primitive>
  <primitive id="rsc_fence_azure" class="stonith" type="fence_azure_arm">
    <instance_attributes>
      <nvpair name="login" value="testuser"/>
      <nvpair name="resourceGroup" value="test-rg"/>
    </instance_attributes>
    <meta_attributes>
      <nvpair name="pcmk_delay_max" value="15"/>
    </meta_attributes>
    <operations>
      <op name="monitor" interval="10" timeout="700"/>
    </operations>
  </primitive>
  <primitive id="rsc_ip_S4D_ASCS00" class="ocf" provider="heartbeat" type="IPaddr2">
    <instance_attributes>
      <nvpair name="ip" value="10.0.1.100"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_azure_lb" class="ocf" provider="heartbeat" type="azure-lb">
    <instance_attributes>
      <nvpair name="port" value="62500"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_azure_events" class="ocf" provider="heartbeat" type="azure-events-az">
    <instance_attributes>
      <nvpair name="subscriptionId" value="12345"/>
    </instance_attributes>
  </primitive>
  <group id="g_sap_S4D_ASCS00">
    <primitive id="rsc_sap_S4D_ASCS00" class="ocf" provider="heartbeat" type="SAPInstance">
      <instance_attributes>
        <nvpair name="InstanceName" value="S4D_ASCS00_sapascs"/>
        <nvpair name="START_PROFILE" value="/sapmnt/S4D/profile/S4D_ASCS00_sapascs"/>
      </instance_attributes>
      <meta_attributes>
        <nvpair name="target-role" value="Started"/>
      </meta_attributes>
      <operations>
        <op name="monitor" interval="10" timeout="600"/>
      </operations>
    </primitive>
  </group>
  <group id="g_sap_S4D_ERS10">
    <primitive id="rsc_sap_S4D_ERS10" class="ocf" provider="heartbeat" type="SAPInstance">
      <instance_attributes>
        <nvpair name="InstanceName" value="S4D_ERS10_sapers"/>
        <nvpair name="START_PROFILE" value="/sapmnt/S4D/profile/S4D_ERS10_sapers"/>
      </instance_attributes>
      <meta_attributes>
        <nvpair name="target-role" value="Started"/>
      </meta_attributes>
      <operations>
        <op name="monitor" interval="10" timeout="600"/>
      </operations>
    </primitive>
  </group>
</resources>"""

SCS_DUMMY_XML_FULL_CIB = f"""<?xml version="1.0" encoding="UTF-8"?>
<cib>
  <configuration>
    {SCS_DUMMY_XML_CRM}
    {SCS_DUMMY_XML_RSC}
    {SCS_DUMMY_XML_OP}
    {SCS_DUMMY_XML_CONSTRAINTS}
    {SCS_DUMMY_XML_RESOURCES}
  </configuration>
</cib>"""

SCS_DUMMY_OS_COMMAND = """kernel.numa_balancing = 0"""

SCS_DUMMY_CONSTANTS = {
    "VALID_CONFIGS": {
        "REDHAT": {
            "stonith-enabled": {"value": "true", "required": False},
            "cluster-name": {"value": "scs_S4D", "required": False},
        },
        "azure-fence-agent": {"priority": {"value": "10", "required": False}},
        "sbd": {
            "have-watchdog": {"value": "true", "required": True},
            "stonith-timeout": {"value": "210", "required": True},
        },
    },
    "RSC_DEFAULTS": {
        "resource-stickiness": {"value": "1000", "required": False},
        "migration-threshold": {"value": "5000", "required": False},
    },
    "OP_DEFAULTS": {
        "timeout": {"value": "600", "required": False},
        "record-pending": {"value": "true", "required": False},
    },
    "CRM_CONFIG_DEFAULTS": {
        "stonith-enabled": {"value": "true", "required": False},
        "maintenance-mode": {"value": "false", "required": False},
    },
    "RESOURCE_DEFAULTS": {
        "REDHAT": {
            "fence_agent": {
                "meta_attributes": {
                    "pcmk_delay_max": {"value": "15", "required": False},
                    "target-role": {"value": "Started", "required": False},
                },
                "operations": {
                    "monitor": {
                        "timeout": {"value": ["700", "700s"], "required": False},
                        "interval": {"value": "10", "required": False},
                    },
                    "start": {"timeout": {"value": "20", "required": False}},
                },
                "instance_attributes": {
                    "login": {"value": "testuser", "required": False},
                    "resourceGroup": {"value": "test-rg", "required": False},
                },
            },
            "sbd_stonith": {
                "meta_attributes": {
                    "pcmk_delay_max": {"value": "30", "required": False},
                    "target-role": {"value": "Started", "required": False},
                },
                "operations": {
                    "monitor": {
                        "timeout": {"value": ["30", "30s"], "required": False},
                        "interval": {"value": "10", "required": False},
                    },
                    "start": {"timeout": {"value": "20", "required": False}},
                },
            },
            "ascs": {
                "meta_attributes": {"target-role": {"value": "Started", "required": False}},
                "operations": {
                    "monitor": {"timeout": {"value": ["600", "600s"], "required": False}}
                },
                "instance_attributes": {
                    "InstanceName": {"value": "S4D_ASCS00_sapascs", "required": False}
                },
            },
            "ers": {
                "meta_attributes": {"target-role": {"value": "Started", "required": False}},
                "operations": {
                    "monitor": {"timeout": {"value": ["600", "600s"], "required": False}}
                },
                "instance_attributes": {
                    "InstanceName": {"value": "S4D_ERS10_sapers", "required": False}
                },
            },
            "ipaddr": {
                "instance_attributes": {
                    "ip": {
                        "value": {"AFS": ["10.0.1.100"], "ANF": ["10.0.1.101"]},
                        "required": False,
                    }
                }
            },
        }
    },
    "OS_PARAMETERS": {
        "DEFAULTS": {
            "sysctl": {
                "kernel.numa_balancing": {"value": "kernel.numa_balancing = 0", "required": False}
            }
        }
    },
    "CONSTRAINTS": {
        "rsc_location": {"score": {"value": "INFINITY", "required": False}},
        "rsc_colocation": {"score": {"value": "4000", "required": False}},
        "rsc_order": {"kind": {"value": "Optional", "required": False}},
    },
}
