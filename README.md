# SAP Testing Automation Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Azure](https://img.shields.io/badge/Microsoft-SAP%20on%20Azure-0078D4?logo=microsoft)](https://docs.microsoft.com/azure/sap)
[![Python Coverage](https://img.shields.io/badge/Code%20Coverage-85%25-success?logo=python&logoColor=white)](https://github.com/Azure/sap-automation-qa/actions/workflows/github-actions-code-coverage.yml)
[![Ansible Lint](https://github.com/Azure/sap-automation-qa/actions/workflows/github-actions-ansible-lint.yml/badge.svg)](https://github.com/Azure/sap-automation-qa/actions/workflows/github-actions-ansible-lint.yml)
[![OpenSSF Scorecard](https://img.shields.io/ossf-scorecard/github.com/Azure/sap-automation-qa)](https://scorecard.dev/viewer/?uri=github.com/Azure/sap-automation-qa)

## 🔍 Overview

The SAP Testing Automation Framework is an open-source orchestration tool designed to validate SAP deployments on Microsoft Azure. It enables you to assess system configurations against SAP on Azure best practices and guidelines. Additionally, the framework facilitates automation for various testing scenarios, including High Availability (HA) functional testing.

> **NOTE**: This repository is currently in private preview and is intended for testing and feedback purposes. As this is an early release, it is not yet production-ready, and breaking changes can be introduced at any time.

## Supported Configuration Matrix

The following SAP components are supported in a two-node Pacemaker cluster running on SUSE Linux Enterprise Server (SLES) or Red Hat Enterprise Linux (RHEL):

- **SAP HANA Scale-Up**
- **SAP Central Services**

For additional information on supported configuration patterns, such as cluster types (Azure Fence Agent or SBD) and storage options (Azure Files or Azure NetApp Files) in this automated testing framework, refer to [supported high availability configuration](./docs/HIGH_AVAILABILITY.md).

## 📊 Key Features

- **High Availability Testing** - Thorough validation of the SAP HANA scale-up and SAP Central Services failover mechanism in a two node pacemaker cluster, ensuring the system operates correctly across various test cases.
  - **Configuration Validation** - Ensures that SAP HANA scale-up and SAP Central Services configurations comply with SAP on Azure best practices and guidelines.
  - **Functional Testing** - Executes test scenarios on the high availability setup to identify potential issues, whether during a new system deployment or before implementing cluster changes in a production environment.
- **Detailed Reporting** - Generates comprehensive reports, highlighting configuration mismatch or deviations from recommended best practices. Includes failover test outcomes, any failures encountered, and logs with insights to aid in troubleshooting identified issues.

## 🏆 Purpose

Testing is crucial for keeping SAP systems running smoothly, especially for critical business operations. This framework helps by addressing key challenges:

- **Preventing Risks** - It simulates system failures like node crashes, network issues, and storage failures to check if recovery mechanisms work properly, helping to catch problems before they affect real operations.
- **Meeting Compliance Requirements** - Many businesses need to prove their SAP systems are reliable. This framework provides detailed reports and logs that help with audits and ensure compliance with internal and regulatory standards.
- **Ensuring Quality** -  The framework runs automated tests to verify whether the failover behavior of SAP components functions as expected on Azure across various test scenarios. It also ensures that the cluster and resource configurations are set up correctly, helping to maintain system reliability.
- **Automating Testing**: Manually testing high availability (HA) setups is slow and error-prone. This framework automates the process—from setup to reporting—saving time and ensuring more accurate and consistent results.

## 🚦 Get Started

There are two primary ways to get started with the SAP Testing Automated Framework. Choose the path that best fits your current environment and objectives:

### Option 1: [Integration with SAP Deployment Automation Framework (SDAF)](./docs/SDAF_INTEGRATION.md)

If you already have [SDAF](https://github.com/Azure/sap-automation) environment set up, integrating the SAP Testing Automation Framework is a natural extension that allows you to leverage existing deployment pipelines and configurations.

### Option 2: [Getting Started with High Availability Testing (Standalone)](./docs/HIGH_AVAILABILITY.md)

For users focused solely on validating SAP functionality and configurations, the standalone approach offers a streamlined process to test critical SAP components without the complexity of full deployment integration.

## 🏗️ Architecture and Components

To learn how the framework works, refer to the [architecture and components](./docs/ARCHITECTURE.md) documentation.

## 🆘Support

For support and questions, please:

1. Check [existing issues](https://github.com/Azure/sap-automation-qa/issues/)
2. Create new issue if needed and provide detailed information about the problem

## 📚 Additional Resources

- [Azure SAP Documentation](https://docs.microsoft.com/azure/sap)
- [SAP on Azure: High Availability Guide](https://docs.microsoft.com/azure/sap/workloads/sap-high-availability-guide-start)

## 🤝 Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit <https://cla.opensource.microsoft.com>.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## ⚖️ Legal

### License

> Copyright (c) Microsoft Corporation. Licensed under the MIT License.

### Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
