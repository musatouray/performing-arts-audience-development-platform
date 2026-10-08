<#
  Lets a Fabric workspace identity read ONE SharePoint site, and nothing else.

  Why: the education Dataflow signs in to SharePoint as the workspace identity.
  That identity is an app, not a person, so it can't be added through the site's
  Share button. Sites.Selected gives an app no access at all until a site is
  granted to it explicitly, which keeps it to exactly the site it needs.

  Run once per environment (dev, test and prod each have their own workspace identity).
  Needs an admin who can grant app permissions (Global Admin or Privileged Role Admin).

  Example:
    ./scripts/12_grant_sharepoint_site_access.ps1 `
        -WorkspaceIdentityAppId "<app ID from Workspace settings > Workspace identity>" `
        -SiteUrl "https://<tenant>.sharepoint.com/sites/<site>"
#>
param(
    [Parameter(Mandatory)] [string] $WorkspaceIdentityAppId,
    [Parameter(Mandatory)] [string] $SiteUrl,
    [ValidateSet("read", "write")] [string] $Role = "read"
)

$ErrorActionPreference = "Stop"

foreach ($m in "Microsoft.Graph.Applications", "Microsoft.Graph.Sites") {
    if (-not (Get-Module -ListAvailable -Name $m)) { Install-Module $m -Scope CurrentUser -Force }
}

Connect-MgGraph -NoWelcome -Scopes "Application.Read.All", "AppRoleAssignment.ReadWrite.All", "Sites.FullControl.All"

$identity = Get-MgServicePrincipal -Filter "appId eq '$WorkspaceIdentityAppId'"
if (-not $identity) { throw "No service principal found for app ID $WorkspaceIdentityAppId" }

# 1) Give the identity the Sites.Selected permission on both APIs the connector may use.
#    On its own this grants access to no sites at all.
$apis = @{
    "SharePoint"      = "00000003-0000-0ff1-ce00-000000000000"
    "Microsoft Graph" = "00000003-0000-0000-c000-000000000000"
}
foreach ($name in $apis.Keys) {
    $api  = Get-MgServicePrincipal -Filter "appId eq '$($apis[$name])'"
    $perm = $api.AppRoles | Where-Object { $_.Value -eq "Sites.Selected" -and $_.AllowedMemberTypes -contains "Application" }
    $has  = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $identity.Id |
            Where-Object { $_.ResourceId -eq $api.Id -and $_.AppRoleId -eq $perm.Id }
    if ($has) {
        Write-Host "$name Sites.Selected: already granted"
    } else {
        New-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $identity.Id `
            -PrincipalId $identity.Id -ResourceId $api.Id -AppRoleId $perm.Id | Out-Null
        Write-Host "$name Sites.Selected: granted"
    }
}

# 2) Allow it to read this one site.
$uri  = [Uri] $SiteUrl
$site = Get-MgSite -SiteId "$($uri.Host):$($uri.AbsolutePath)"

$existing = Get-MgSitePermission -SiteId $site.Id |
            Where-Object { $_.GrantedToIdentitiesV2.Application.Id -contains $WorkspaceIdentityAppId }
if ($existing) {
    Write-Host "Site access: already granted ($($existing.Roles -join ', '))"
} else {
    New-MgSitePermission -SiteId $site.Id -BodyParameter @{
        roles               = @($Role)
        grantedToIdentities = @(@{ application = @{ id = $WorkspaceIdentityAppId; displayName = $identity.DisplayName } })
    } | Out-Null
    Write-Host "Site access: granted '$Role' on $SiteUrl to $($identity.DisplayName)"
}

Disconnect-MgGraph | Out-Null
