# SAP Testing Automation Framework

## Overview

The SAP Testing Automation Framework is a automation solution designed to validate the configuration and performance of SAP systems on Azure under a wide array of scenarios. This framework not only streamlines the testing of SAP environments but also brings confidence and assurance by simulating real-world conditions.

Currently, the framework offers test scenarios focusing on high availability functional testing and configuration checks. Under the high availability category, we address critical components including:

- **SAP HANA Database HA Configurations:** Validate SAP HANA database configurations, ensuring resilience, rapid failover, and optimal performance even in adverse conditions.
- **SAP Central Services (SCS/ERS) HA Setups:** Test and verify the configuration integrity and robustness of SAP Central Services, including load balancing, failover mechanisms, and component interoperability.

By integrating comprehensive monitoring, detailed logging, and automated evaluation, our framework transforms how organizations maintain and enhance the reliability of their SAP landscapes on Azure.

### Purpose

Testing is crucial for maintaining business continuity in SAP environments. This framework addresses several critical needs:

**Risk Mitigation**:
The framework provides systematic testing of failure scenarios, helping organizations identify and address potential issues before they impact production systems. It simulates various failure modes, including node failures, network interruptions, and storage issues, ensuring that recovery mechanisms function as designed.

**Compliance**:
Organizations must often demonstrate that their SAP systems meet specific availability requirements. This framework provides documented evidence of HA testing, including detailed logs and reports that can be used for audit purposes. It helps ensure that HA implementations align with organizational standards and regulatory requirements.

**Quality Assurance**:
Through automated and consistent testing procedures, the framework helps maintain high quality standards across SAP infrastructure components. It validates that all HA mechanisms, including clustering software, storage replication, and application-level failover, work together seamlessly.

**Automation**:
Manual testing of HA configurations is time-consuming and prone to human error. This framework automates the entire testing process, from setup to execution and reporting, significantly reducing the operational overhead of HA testing while improving accuracy and consistency.

## Get Started

There are two primary ways to get started with the SAP Testing Automated Framework. Choose the path that best fits your current environment and objectives:

### [Integration with SAP Deployment Automation Framework (SDAF)](./docs/SDAF_INTEGRATION.md)

If you already have [SDAF](https://github.com/Azure/sap-automation) environment set up, integrating the SAP Testing Automation Framework is a natural extension that allows you to leverage existing deployment pipelines and configurations.

### [Getting Started with High Availability Testing (Standalone)](./docs/GETTING_STARTED.md)

For users focused solely on validating SAP functionality and configurations, the standalone approach offers a streamlined process to test critical SAP components without the complexity of full deployment integration.


### [Architecture and Components](./docs/ARCHITECTURE.md)

## License

Copyright (c) Microsoft Corporation.
Licensed under the MIT License.

## Support

For support and questions, please:
1. Check existing issues
2. Create new issue if needed
3. Provide detailed information about the problem

## Additional Resources
- [Azure SAP Documentation](https://docs.microsoft.com/azure/sap)
- [SAP on Azure: High Availability Guide](https://docs.microsoft.com/azure/sap/workloads/sap-high-availability-guide-start)

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
