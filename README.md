# ADCleaner
Active Directory Cleaner (ADC) v1.0
ADC is a Python-based automation tool designed to clean up stale Active Directory (AD) accounts. It identifies and optionally disables or deletes inactive users and computers based on customizable thresholds and rules.

# Warning
This tool is in development. While disabling AD objects have been thoroughly tested, deleting objects have not. Deleting objects should work in theory, but it is currently untested.

# Key Features
>Dry Run Mode (enabled by default): Simulates changes without making actual modifications.

User & Computer Cleanup:
>Disable or delete accounts based on last logon or last change date.
>Automatically excludes accounts based on group membership, naming patterns, or IP presence.

Configurable Behavior via JSON:
>Set inactivity thresholds (e.g., 5 years since last logon).
>Define bypass rules based on naming, groups, or IP addresses.

AD Statistics Summary:
>Displays number of GPOs, OUs, enabled/disabled users and computers, forest details, and Recycle Bin status.

PowerShell Integration:
>Uses native PowerShell commands to interact with Active Directory securely.

Logging and Reporting:
>Outputs CSV reports of bypassed and affected accounts with timestamps.

Requirements
>Windows system joined to an Active Directory domain
>RSAT tools installed (Active Directory PowerShell module)
>Python 3.x

# Roadmap
-Dry Run
> Developed > Tested

-Disable User
> Developed > Tested

-Delete User
> Developed

-Disable Computer
> Developed > Tested

-Delete Computer
> Developed

-List statistics about AD environment.
> Developed > Tested
> Could use more stats.
