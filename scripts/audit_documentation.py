#!/usr/bin/env python3
"""
Documentation Audit Script
Identifies outdated documentation that needs updating or archiving.
"""
import os
import re
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path("/home/admin/.openclaw/workspace/auto-trade-system")

# Current system state
CURRENT_STATE = {
    "active_exchange": "bybit",
    "client_library": "pybit",
    "execution_mode": "semi-auto",
    "python_version": "3.11+",
    "status": "Production Ready v2.0.0"
}

def check_file_for_outdated_info(filepath):
    """Check a markdown file for outdated information."""
    issues = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for outdated exchange references
        if re.search(r'ACTIVE_EXCHANGE.*=.*["\']?mexc["\']?', content, re.IGNORECASE):
            issues.append("Outdated: References MEXC as active exchange")
        
        if re.search(r'ACTIVE_EXCHANGE.*=.*["\']?binance["\']?', content, re.IGNORECASE):
            issues.append("Outdated: References Binance as active exchange")
        
        # Check for outdated client library
        if re.search(r'BYBIT_CLIENT_LIBRARY.*=.*["\']?ccxt["\']?', content, re.IGNORECASE):
            if "DEPRECATED" not in content.upper() and "ARCHIVE" not in content.upper():
                issues.append("Outdated: References CCXT as Bybit client (should be pybit)")
        
        # Check for outdated execution mode
        if re.search(r'EXECUTION_MODE.*=.*["\']?proposal["\']?', content, re.IGNORECASE):
            if "example" not in content.lower() and "config" not in content.lower():
                issues.append("Potentially outdated: References 'proposal' execution mode")
        
        # Check for Python version
        if re.search(r'python\s*3\.(8|9|10)', content, re.IGNORECASE):
            if "3.11" not in content:
                issues.append("Outdated: References Python < 3.11")
        
        # Check for removed/deprecated features
        if re.search(r'MEXC.*primary|primary.*MEXC', content, re.IGNORECASE):
            if "DEPRECATED" not in content.upper():
                issues.append("Outdated: References MEXC as primary exchange")
                
    except Exception as e:
        issues.append(f"Error reading file: {str(e)}")
    
    return issues

def categorize_document(filename):
    """Categorize document by type and relevance."""
    filename_lower = filename.lower()
    
    # MEXC-related documents (likely deprecated)
    if 'mexc' in filename_lower:
        return 'mexc_deprecated'
    
    # Historical reports with dates
    if re.search(r'\d{4}-\d{2}-\d{2}', filename):
        return 'historical_report'
    
    # Status/validation reports
    if any(word in filename_lower for word in ['status', 'validation', 'report', 'summary']):
        return 'status_report'
    
    # Quick reference guides
    if 'quick' in filename_lower or 'quickref' in filename_lower:
        return 'quick_reference'
    
    # Implementation summaries
    if 'implementation' in filename_lower or 'summary' in filename_lower:
        return 'implementation_doc'
    
    # Architecture docs
    if 'architecture' in filename_lower or 'design' in filename_lower:
        return 'architecture'
    
    # Deployment docs
    if 'deploy' in filename_lower:
        return 'deployment'
    
    return 'other'

def main():
    """Run documentation audit."""
    print("=" * 80)
    print("DOCUMENTATION AUDIT REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    # Find all markdown files in root
    md_files = list(ROOT_DIR.glob("*.md"))
    
    print(f"Total markdown files found: {len(md_files)}")
    print()
    
    # Categorize files
    categories = {}
    for filepath in md_files:
        category = categorize_document(filepath.name)
        if category not in categories:
            categories[category] = []
        categories[category].append(filepath)
    
    print("DOCUMENT CATEGORIES:")
    print("-" * 80)
    for category, files in sorted(categories.items()):
        print(f"\n{category.upper()} ({len(files)} files):")
        for f in sorted(files, key=lambda x: x.name):
            print(f"  - {f.name}")
    
    print("\n" + "=" * 80)
    print("OUTDATED CONTENT ANALYSIS")
    print("=" * 80)
    
    # Check each file for outdated info
    outdated_files = []
    for filepath in sorted(md_files):
        issues = check_file_for_outdated_info(filepath)
        if issues:
            outdated_files.append((filepath, issues))
    
    if outdated_files:
        print(f"\nFound {len(outdated_files)} files with potentially outdated content:\n")
        for filepath, issues in outdated_files:
            print(f"📄 {filepath.name}")
            for issue in issues:
                print(f"   ⚠️  {issue}")
            print()
    else:
        print("\n✅ No outdated content detected!")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    # Generate recommendations
    mexc_files = categories.get('mexc_deprecated', [])
    if mexc_files:
        print(f"\n📦 MEXC DEPRECATED DOCUMENTS ({len(mexc_files)} files):")
        print("   Recommendation: Move to docs_archive/deprecated/")
        for f in sorted(mexc_files, key=lambda x: x.name):
            print(f"   - {f.name}")
    
    historical_files = categories.get('historical_report', [])
    if historical_files:
        print(f"\n📚 HISTORICAL REPORTS ({len(historical_files)} files):")
        print("   Recommendation: Move to docs_archive/historical_reports/")
        print("   These are dated status reports from specific points in time")
    
    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
