# Documentation Archive

This directory contains archived documentation that is preserved for historical reference but may contain outdated information.

## Directory Structure

### `/deprecated/`
Contains documentation related to exchanges or features that are no longer active in the current system configuration.

**Current Contents:**
- **MEXC Documentation** (15 files) - MEXC was the primary exchange prior to May 11, 2026. These documents describe MEXC-specific setup, troubleshooting, and integration details that are no longer applicable since the system migrated to Bybit Demo Trading.

**When to Reference:**
- Understanding historical system evolution
- Migrating from old configurations
- Troubleshooting legacy integrations

**⚠️ Warning:** Do NOT use these documents for current system setup. Refer to main README.md and BYBIT_DEMO_TRADING_CONFIGURATION.md instead.

### Archived Code Files

**main_enterprise_DEPRECATED.py** (Archived 2026-05-18)
- Superseded by `app/main.py` which contains all enterprise features
- This file was a duplicate entry point that caused confusion
- All features (session scheduler, news guard, admin routes) are in main.py
- **Do not use this file** - it is preserved for historical reference only

### `/historical_reports/`
Contains time-specific status reports, validation cycles, and implementation updates from specific dates.

**Current Contents:**
- Status reports from May 11-13, 2026
- Validation cycle reports
- Implementation update logs
- Cleanup and restart reports

**When to Reference:**
- Audit trails for compliance
- Understanding decision history
- Tracking system evolution over time

**⚠️ Warning:** These are point-in-time snapshots. Current system status should be determined from live monitoring, not historical reports.

## Archive Policy

### What Gets Archived

1. **Deprecated Exchange Docs**: When an exchange is no longer the primary trading platform
2. **Dated Status Reports**: Reports with specific timestamps older than 30 days
3. **Superseded Implementations**: Documentation replaced by newer approaches
4. **Temporary Workarounds**: Fixes that have been properly resolved

### What Stays in Root

1. **Core Architecture Docs**: Self-healing architecture, execution layer design
2. **Current Configuration Guides**: Active exchange setup, current execution modes
3. **Quick Start & Onboarding**: Must always reflect current state
4. **Active Deployment Plans**: Current sprint plans and deployment strategies
5. **API Documentation**: Always current with codebase

### Review Schedule

- **Monthly**: Review new documents added to archive
- **Quarterly**: Assess if archived docs can be permanently deleted
- **Annually**: Comprehensive documentation audit (like this one)

## Restoration Process

If you need to restore an archived document to the root directory:

1. Verify the content is still accurate against current codebase
2. Update any outdated references (exchange names, config values, etc.)
3. Move file back to root: `mv docs_archive/deprecated/FILE.md .`
4. Update DOCUMENTATION_AUDIT_REPORT.md to note restoration
5. Commit with clear message explaining why it was restored

## Contact

For questions about archived documentation or to request restoration:
- Review `DOCUMENTATION_AUDIT_REPORT.md` for context on why docs were archived
- Check current `README.md` for up-to-date information
- Consult team lead before restoring deprecated documentation

---

**Last Updated:** May 14, 2026  
**Maintained By:** System Documentation Team
