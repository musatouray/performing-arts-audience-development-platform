# Tenant settings audit

_Generated 2026-10-27 11:39 by scripts/08_audit_tenant_settings.py_

## Baseline checks

| Setting | Enabled | Scoped to groups | Expected | Status | Why |
|---|---|---|---|---|---|
| Publish to web | True | musaDevLab, sg-hh-fabric-admins | False | DRIFT | Public, anonymous links: the main leak risk for donor data. |
| External data sharing | False | entire org | False | OK | No cross-tenant OneLake sharing without review. |
| Guest users can access Microsoft Fabric | False | entire org | False | OK | B2B guests off by default; exceptions per workspace. |
| Create workspaces | True | musaDevLab, sg-hh-fabric-admins | True for sg-hh-fabric-admins | OK | Only platform admins create workspaces, so the topology stays as designed. |
| Users can create Fabric items | True | musaDevLab, sg-hh-fabric-admins, sg-hh-data-engineers, sg-hh-bi-developers | True for sg-hh-fabric-admins, sg-hh-data-engineers, sg-hh-bi-developers | OK | Builders only: no shadow items. |
| Certification | True | musaDevLab, sg-hh-fabric-admins | True for sg-hh-fabric-admins | OK | Only the people who apply the certification criteria can certify. |
| Service principals can call Fabric public APIs | True | musaDevLab, spn-fabricdevlab-grp | True | OK | CI/CD (fabric-cicd), limited to a dedicated group. |
| Users can synchronize workspace items with their Git repositories | True | entire org | True | OK | Git integration on DEV. |
| Users can sync workspace items with GitHub repositories | True | entire org | True | OK | The repo lives on GitHub. |
| Allow tenant and domain admins to override workspace assignments (preview) | True | entire org | True | OK | Script 02 assigns workspaces to domains. |
| Users can access data stored in OneLake with apps external to Fabric | True | entire org | True | OK | Script 06 uploads config over the ADLS API. |
| Users can work with semantic models in Excel using a live connection | True | entire org | True | OK | Excel is a main way to use the models. |
| Allow users to apply sensitivity labels for content | True | entire org | True for sg-hh-fabric-admins, sg-hh-data-engineers, sg-hh-bi-developers | SCOPE | Builders label what they publish (Purview). |
| Apply sensitivity labels from data sources to their data in Power BI | True | entire org | True | OK | Gold's label reaches the models. |
| Automatically apply sensitivity labels to downstream content | True | entire org | True | OK | Labels follow data into reports and Excel exports. |
| Users can use Copilot, AI Agents and other AI experiences powered by Azure OpenAI | True | entire org | True | OK | Data agents and Copilot (TODO section 9). |
| Users can create Ontology (preview) items | True | entire org | True | OK | Fabric IQ ontology (TODO section 9). |
| Enable anonymous data access for Fabric Apps (Preview) | False | entire org | False | OK | Apps sign users in with Entra; never anonymous. |

## All settings

| Group | Setting | Enabled |
|---|---|---|
| Additional workloads | Capacity admins and contributors can add and remove additional workloads | True |
| Additional workloads | Users can see and work with additional workloads not validated by Microsoft | False |
| Additional workloads | Workspace admins can add and remove additional workloads (preview) | True |
| Additional workloads | Workspace admins can develop partner workloads  | False |
| Admin API settings | Enhance admin APIs responses with DAX and mashup expressions | False |
| Admin API settings | Enhance admin APIs responses with detailed metadata | False |
| Admin API settings | Service principals can access admin APIs used for updates | False |
| Admin API settings | Service principals can access read-only admin APIs | False |
| Advanced networking | Block Public Internet Access | False |
| Advanced networking | Configure workspace-level IP firewall rules and trusted resource instances  | True |
| Advanced networking | Configure workspace-level inbound network rules | False |
| Advanced networking | Configure workspace-level outbound network rules | False |
| Advanced networking | Tenant-level Private Link | False |
| App settings | Create template organizational apps | True |
| App settings | Publish apps to the entire organization | True |
| App settings | Push apps to end users | True |
| Audit and usage settings | Azure Log Analytics connections for workspace administrators | False |
| Audit and usage settings | Microsoft can store query text to aid in support investigations | True |
| Audit and usage settings | Per-user data in usage metrics for content creators | True |
| Audit and usage settings | Show user data in the Fabric Capacity Metrics app and reports | True |
| Audit and usage settings | Usage metrics for content creators | True |
| Audit and usage settings | Workspace admins can turn on monitoring for their workspaces (preview) | True |
| Azure AI Service | Allow data processing outside geographic region for Azure AI services | True |
| Azure Maps services | Data sent to Azure Maps can be processed outside your capacity's geographic region, compliance boundary or national cloud instance | False |
| Azure Maps services | Users can use Azure Maps Weather Services (Preview) | True |
| Azure Maps services | Users can use Azure Maps services | True |
| Copilot and AI | Capacities can be designated as Fabric Copilot capacities | True |
| Copilot and AI | Data sent to Azure OpenAI can be processed outside your capacity's geographic region, compliance boundary, or national cloud instance | True |
| Copilot and AI | Data sent to Azure OpenAI can be stored outside your capacity's geographic region, compliance boundary, or national cloud instance | True |
| Copilot and AI | Data sent to OpenAI as a Microsoft Subprocessor can be processed outside your capacity's geographic region, compliance boundary, or national cloud instance | False |
| Copilot and AI | Only show approved items in the standalone Copilot in Power BI experience (preview) | False |
| Copilot and AI | Users can access a standalone, cross-item Power BI Copilot experience (preview) | True |
| Copilot and AI | Users can use Copilot, AI Agents and other AI experiences powered by Azure OpenAI | True |
| Copilot and AI | Users can use Copilot, AI Agents and other AI experiences powered by OpenAI as a Microsoft Subprocessor | False |
| Dashboard settings | Web content on dashboard tiles | True |
| Datamart settings | Create Datamarts (preview) | True |
| Developer settings | Allow service principals to create and use profiles | False |
| Developer settings | Block ResourceKey Authentication | False |
| Developer settings | Define maximum number of Fabric identities in a tenant | False |
| Developer settings | Embed content in apps | True |
| Developer settings | Service principals can call Fabric public APIs | True |
| Developer settings | Service principals can create workspaces, connections, and deployment pipelines | False |
| Discovery settings | Discover content | True |
| Discovery settings | Make certified content discoverable  | True |
| Discovery settings | Make promoted content discoverable | True |
| Discovery settings | Users can find objects in search | True |
| Domain management settings | Allow tenant and domain admins to override workspace assignments (preview) | True |
| Encryption | Allow cross-tenant customer-managed keys | False |
| Encryption | Apply customer-managed keys | False |
| Explore settings (preview) | Users with view permission can launch Explore | True |
| Export and sharing settings | Allow DirectQuery connections to Power BI semantic models | True |
| Export and sharing settings | Allow shareable links to grant access to everyone in your organization | True |
| Export and sharing settings | Allow specific users to turn on external data sharing | True |
| Export and sharing settings | B2B guest users can set up and be subscribed to email subscriptions | False |
| Export and sharing settings | Certification | True |
| Export and sharing settings | Copy and paste visuals | True |
| Export and sharing settings | Download reports | True |
| Export and sharing settings | Enable Microsoft Teams integration | True |
| Export and sharing settings | Enable Power BI add-in for PowerPoint | True |
| Export and sharing settings | Endorse master data | True |
| Export and sharing settings | Export reports as MHTML documents | True |
| Export and sharing settings | Export reports as PowerPoint presentations or PDF documents | True |
| Export and sharing settings | Export reports as Word documents | True |
| Export and sharing settings | Export reports as XML documents | True |
| Export and sharing settings | Export reports as image files | True |
| Export and sharing settings | Export to .csv | True |
| Export and sharing settings | Export to Excel | True |
| Export and sharing settings | External data sharing | False |
| Export and sharing settings | Featured content | True |
| Export and sharing settings | Guest users can access Microsoft Fabric | False |
| Export and sharing settings | Guest users can browse and access Fabric content | False |
| Export and sharing settings | Guest users can work with shared semantic models in their own tenants | False |
| Export and sharing settings | Install Power BI app for Microsoft Teams automatically | True |
| Export and sharing settings | Print dashboards and reports | True |
| Export and sharing settings | Publish to web | True |
| Export and sharing settings | Users can accept external data shares | False |
| Export and sharing settings | Users can invite guest users to collaborate through item sharing and permissions | True |
| Export and sharing settings | Users can see guest users in lists of suggested people | True |
| Export and sharing settings | Users can send email subscriptions to external users | False |
| Export and sharing settings | Users can set up email subscriptions | True |
| Export and sharing settings | Users can share Power BI visuals as Loop components (preview) | True |
| Export and sharing settings | Users can work with semantic models in Excel using a live connection | True |
| Export and sharing settings | Users with read or write permission can download data from notebooks | True |
| Gen1 dataflow settings | Create and use Gen1 dataflows | True |
| Git integration | Users can export items to Git repositories in other geographical locations | True |
| Git integration | Users can export workspace items with applied sensitivity labels to Git repositories | True |
| Git integration | Users can sync workspace items with GitHub repositories  | True |
| Git integration | Users can synchronize workspace items with their Git repositories | True |
| Help and support settings | Publish "Get Help" information | True |
| Help and support settings | Receive In-product notifications for service outages or incidents | False |
| Help and support settings | Receive email and Teams notifications for service outages or incidents | False |
| Help and support settings | Show a custom message before publishing reports | False |
| Help and support settings | Users can try Microsoft Fabric paid features | True |
| Information protection | Allow Microsoft Purview to secure AI interactions | True |
| Information protection | Allow users to apply sensitivity labels for content | True |
| Information protection | Allow workspace admins to override automatically applied sensitivity labels | True |
| Information protection | Apply sensitivity labels from data sources to their data in Power BI | True |
| Information protection | Automatically apply sensitivity labels to downstream content | True |
| Information protection | Domain admins can set default sensitivity labels for their domains (preview) | True |
| Information protection | Restrict content with protected labels from being shared via link with everyone in your organization | True |
| Insights settings | Receive notifications for top insights (preview) | True |
| Insights settings | Show entry points for insights (preview) | True |
| Integration settings | Allow XMLA endpoints and Analyze in Excel with on-premises semantic models | True |
| Integration settings | Allow non-Entra ID auth in Eventstream | True |
| Integration settings | ArcGIS GeoAnalytics for Fabric Runtime | False |
| Integration settings | Data sent to Azure Maps can be processed by Microsoft Online Services Subprocessors  | True |
| Integration settings | Data sent to Azure Maps can be processed outside your tenant's geographic region, compliance boundary, or national cloud instance | True |
| Integration settings | Dremio SSO | True |
| Integration settings | Enable Denodo SSO | False |
| Integration settings | Enable Starburst SSO | False |
| Integration settings | Enable granular access control for all data connections | False |
| Integration settings | Google BigQuery SSO | True |
| Integration settings | Integration with SharePoint and Microsoft Lists | True |
| Integration settings | Map and filled map visuals | True |
| Integration settings | Microsoft Entra single sign-on for on-premises data gateway | True |
| Integration settings | Microsoft Entra single sign-on for virtual network (VNet) data gateway | False |
| Integration settings | Redshift SSO | True |
| Integration settings | Semantic Model Execute Queries REST API | True |
| Integration settings | Semantic model owners can choose to automatically update semantic models from files imported from OneDrive or SharePoint | True |
| Integration settings | Semantic models can export data to OneLake | True |
| Integration settings | Snowflake SSO | True |
| Integration settings | Use ArcGIS Maps for Power BI | True |
| Integration settings | Use global search for Power BI | True |
| Integration settings | Users can connect to data sources by using Apache Arrow database connectivity (ADBC) | False |
| Integration settings | Users can share links to Power BI files stored in OneDrive and SharePoint through Power BI Desktop (preview) | True |
| Integration settings | Users can use the Azure Maps visual | True |
| Integration settings | Users can use the Power BI Model Context Protocol server endpoints (preview) | False |
| Integration settings | Users can view Power BI files saved in OneDrive and SharePoint (preview) | True |
| Kusto settings | Allow Real-Time Dashboards to include embedded app visuals | False |
| Microsoft Fabric | All Power BI users can see "Set alert" button to create Fabric Activator alerts | True |
| Microsoft Fabric | Allow monitoring data collection | True |
| Microsoft Fabric | Detect anomalies in Real-Time Intelligence (Preview) | True |
| Microsoft Fabric | Enable Event Schema Sets in Real-Time Hub (preview) | True |
| Microsoft Fabric | Enable Fabric App Items (preview) | True |
| Microsoft Fabric | Enable anonymous data access for Fabric Apps (Preview) | False |
| Microsoft Fabric | Enable new mirrored catalog items (preview) | True |
| Microsoft Fabric | Enable sending Operations Agents observability data to Agent 365 (preview) | False |
| Microsoft Fabric | Fabric data agents can send operational metadata for observability in Microsoft Foundry | True |
| Microsoft Fabric | Insights for operations agents (preview) | True |
| Microsoft Fabric | ML models can serve real-time predictions from API endpoints (preview) | True |
| Microsoft Fabric | Policies (preview) | False |
| Microsoft Fabric | Product Feedback | True |
| Microsoft Fabric | Users can access the Database hub (preview) | False |
| Microsoft Fabric | Users can be informed of upcoming conferences featuring Microsoft Fabric when they are logged in to Fabric | True |
| Microsoft Fabric | Users can create Azure Databricks Storage items (preview) | True |
| Microsoft Fabric | Users can create Digital Twin Builder (preview) items | True |
| Microsoft Fabric | Users can create Fabric items | True |
| Microsoft Fabric | Users can create Monitoring items (preview) | True |
| Microsoft Fabric | Users can create Ontology (preview) items | True |
| Microsoft Fabric | Users can create dbt job items (preview) | True |
| Microsoft Fabric | Users can create deployment plan (preview) items | True |
| OneLake settings | Authenticate with OneLake user-delegated SAS tokens | False |
| OneLake settings | Include end-user identifiers in OneLake diagnostic logs | True |
| OneLake settings | Use short-lived user-delegated SAS tokens | True |
| OneLake settings | Users can access data stored in OneLake with apps external to Fabric | True |
| OneLake settings | Users can sync data in OneLake with the OneLake File Explorer app | True |
| Plan settings | Show Oversubscription Warning | True |
| Plan settings | Users can upgrade to a Planner persona | True |
| Plan settings | Users can upgrade to a Stakeholder persona | True |
| Power BI visuals | Add and use certified visuals only (block uncertified) | False |
| Power BI visuals | Allow access to the browser's local storage | True |
| Power BI visuals | Allow downloads from custom visuals | False |
| Power BI visuals | Allow visuals created using the Power BI SDK | True |
| Power BI visuals | AppSource Custom Visuals SSO | False |
| Q&A settings | Review questions | True |
| Q&A settings | Synonym sharing | True |
| R and Python visuals settings | Interact with and share R and Python visuals | True |
| Scale-out settings | Scale out queries for large semantic models | True |
| Scorecards settings | Create and use Scorecards | True |
| Semantic Model Security | Block republish and disable package refresh | False |
| Semantic model settings | Users can edit semantic models in the Power BI service | True |
| Share data with your Microsoft 365 services | Share Fabric data with your Microsoft 365 services | True |
| Template app settings | Install template apps | True |
| Template app settings | Install template apps not listed in AppSource | False |
| Template app settings | Publish template apps | True |
| User experience experiments | Help Power BI optimize your experience | True |
| Workspace settings | Block users from reassigning personal workspaces (My Workspace) | False |
| Workspace settings | Create workspaces | True |
| Workspace settings | Define workspace retention period | True |
| Workspace settings | Fabric item recovery | True |
| Workspace settings | Use semantic models across workspaces | True |
