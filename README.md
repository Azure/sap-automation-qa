# SAP Testing Automation Framework

![SAP Testing Automation Framework](./docs/images/sap-automation-qa.svg)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Azure](https://img.shields.io/badge/Microsoft-SAP%20on%20Azure-0078D4?logo=microsoft)](https://docs.microsoft.com/azure/sap)
[![Python Coverage](https://img.shields.io/badge/Code%20Coverage-85%25-success?logo=python&logoColor=white)](https://github.com/Azure/sap-automation-qa/actions/workflows/github-actions-code-coverage.yml)
[![Ansible Lint](https://github.com/Azure/sap-automation-qa/actions/workflows/github-actions-ansible-lint.yml/badge.svg)](https://github.com/Azure/sap-automation-qa/actions/workflows/github-actions-ansible-lint.yml)
[![OpenSSF Scorecard](https://img.shields.io/ossf-scorecard/github.com/Azure/sap-automation-qa)](https://scorecard.dev/viewer/?uri=github.com/Azure/sap-automation-qa)
[![GitHub Issues](https://img.shields.io/github/issues/Azure/sap-automation-qa)](https://github.com/Azure/sap-automation-qa/issues)

## 🔍 Overview

The SAP Testing Automation Framework is an open-source orchestration tool designed to validate SAP deployments on Microsoft Azure. It enables you to assess system configurations against SAP on Azure best practices and guidelines, and facilitates automation for various testing scenarios.

![SAP Testing Automation Framework](./docs/images/sap-testing-automation-framework.png)

## 📊 Key Scenarios

SAP Testing Automation is designed as a scalable framework to orchestrate and validate a wide spectrum of SAP landscape scenarios through repeatable, policy-driven test modules. The framework currently offers following scenarios -

> [!NOTE]
>
> The High Availability testing scenario in the SAP Testing Framework is **generally available (GA)**, while the Configuration Checks scenario is currently in **public preview**.

### High Availability Testing

In the SAP Testing Automation Framework, thorough validation of high availability SAP HANA scale-up and SAP Central Services failover mechanism in a two node pacemaker cluster can be performed, ensuring the system operates correctly across different situations.

- **High Availability Configuration Validation:** The framework helps to ensure that SAP HANA scale-up and SAP Central Services configurations and load balancer settings are compliant with SAP on Azure high availability configuration guidelines.
- **Functional Testing:** The framework executes series of real-world scenarios based on the SAP HANA and SAP Central Services high availability setup to identify potential issues, whether during a new system deployment or before implementing cluster changes in a production environment. The test cases are based on what is documented in how-to guides for SAP HANA and SAP Central Services configuration.
- **Offline configuration validation:** Offline validation is a mode of the framework that validates SAP HANA and SAP Central Services high availability cluster configurations without establishing a live SSH connection to the production cluster. Instead, it analyzes captured cluster information base (CIB) XML files exported from each cluster node.

### Configuration Checks (Preview)

The framework performs comprehensive configuration checks to ensure that the SAP system and its components are set up according to [SAP on Azure best practice](https://learn.microsoft.com/azure/sap/). This includes validating infrastructure settings, operating system parameter configurations, and network settings, in addition to the cluster configuration, to identify any deviations that could impact system performance or reliability.

- **Infrastructure Validation:** This includes validating the underlying infrastructure components, such as virtual machines, load balancer, and other resource configurations, to ensure they meet the requirements for running SAP workloads on Azure.
- **Storage Configuration Checks:** It validates settings of disks, storage accounts, Azure NetApp Files, including throughput, performance, and stripe size.
- **Operating System and SAP Parameter Validation:** The framework checks critical operating system parameters and SAP kernel settings to ensure they align with recommended configurations.
- **Cluster Configuration Validation:** This framework ensures that the high availability cluster resource settings adhere to best practices for high availability and failover scenarios.

The framework generates comprehensive reports, highlighting configuration mismatch or deviations from recommended best practices. For high availability scenarios, the report includes failover test outcomes, any failures encountered, and logs with insights to aid in troubleshooting identified issues.

## 🏆 Purpose

Testing is crucial for keeping SAP systems running smoothly, especially for critical business operations. This framework helps by addressing key challenges:

- **Risk Prevention** - The high availability testing helps simulate system failures like node crashes, network issues, and storage failures to check if recovery mechanisms work properly, helping to catch problems before they affect real operations. Configuration validation detects misalignments with SAP on Azure best practices early.
- **Compliance Requirements** - Many businesses need to prove their SAP systems are reliable. This framework provides detailed reports and logs that help with audits and ensure compliance with internal and regulatory standards.
- **Quality Assurance** - The framework runs automated tests to verify whether the failover behavior of SAP components functions as expected on Azure across various test scenarios. It also ensures that the cluster and resource configurations are set up correctly, helping to maintain system reliability.
- **Test Automation** - Manually validating overall SAP systems' configurations and high availability (HA) setup is slow and error-prone. This framework automates the process, from setup to reporting, saving time and ensuring more accurate and consistent results.

## 🏗️ Architecture and Components

To learn how the framework works, refer to the [architecture and components](./docs/ARCHITECTURE.md) documentation.

## 🚦 Get Started

There are two primary ways to get started with the SAP Testing Automation Framework. You can choose the path that best fits your current environment and objectives:

### Option 1: Standalone Setup of SAP Testing Automation Framework

For users focused solely on validating SAP functionality and configurations, the standalone approach offers a streamlined process to test critical SAP components without the complexity of full deployment integration. For more details on the setup, see following documents to get started -

- Configure management server following the document [Setup Guide for SAP Testing Automation Framework](https://github.com/Azure/sap-automation-qa/blob/main/docs/SETUP.MD).
  - For high availability testing scenarios, see [High Availability documentation](./docs/HIGH_AVAILABILITY.md).
  - For Configuration Checks and Testing details, see the [Configuration Checks documentation](./docs/CONFIGURATION_CHECKS.md).

### Option 2: Integration with SAP Deployment Automation Framework (SDAF)

If you already have an [SAP Deployment Automation Framework](https://learn.microsoft.com/azure/sap/automation/deployment-framework) environment set up, integrating the SAP Testing Automation Framework is a natural extension that allows you to leverage existing deployment pipelines and configurations. For more details on the setup, see [Setup Guide for SAP Testing Automation Framework](./docs/SETUP.MD).

## 🆘Support

For support and questions, please:

1. Check [existing issues](https://github.com/Azure/sap-automation-qa/issues/)
2. Create new issue if needed and provide detailed information about the problem

## 📚 Additional Resources

- [Azure SAP Documentation](https://docs.microsoft.com/azure/sap)
- [Configuration Checks Guide](./docs/CONFIGURATION_CHECKS.md)
- [High Availability Testing Guide](./docs/HIGH_AVAILABILITY.md)

## 🤝 Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit <https://cla.opensource.microsoft.com>.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## ⚖️ Legal

### License

> Copyright (c) Microsoft Corporation. Licensed under the MIT License.

### Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
