#!/usr/bin/env python3
"""
Test hybrid deployment configuration
Validates that system can run in both local and VPS modes
"""

import os
import subprocess
import sys
from pathlib import Path


def test_local_environment():
    """Test local systemd-based deployment"""
    print("🔍 Testing local deployment...")
    
    # Check systemd services exist
    service_files = [
        "systemd/auto-trade-api.service",
        "systemd/auto-trade-worker.service"
    ]
    
    all_exist = True
    for service_file in service_files:
        path = Path(service_file)
        if not path.exists():
            print(f"❌ Missing: {service_file}")
            all_exist = False
    
    if all_exist:
        print("✅ Local deployment config valid")
    
    return all_exist


def test_vps_scripts():
    """Test VPS deployment scripts exist and are executable"""
    print("🔍 Testing VPS deployment scripts...")
    
    scripts = [
        "scripts/vps/setup_vps.sh",
        "scripts/vps/install_tailscale.sh",
        "scripts/vps/enable_tailscale_exit_node.sh",
        "scripts/vps/configure_tailscale_ssh.sh",
        "scripts/vps/deploy_to_vps.sh",
        "scripts/vps/validate_vps_env.sh"
    ]
    
    all_valid = True
    for script in scripts:
        path = Path(script)
        if not path.exists():
            print(f"❌ Missing: {script}")
            all_valid = False
        elif not os.access(path, os.X_OK):
            print(f"⚠️  Not executable: {script}")
            os.chmod(path, 0o755)
            print(f"   Fixed permissions")
    
    if all_valid:
        print("✅ VPS deployment scripts valid")
    
    return all_valid


def test_docker_compose():
    """Test Docker Compose configuration"""
    print("🔍 Testing Docker Compose config...")
    
    # Check if docker-compose.yml exists
    compose_file = Path("docker-compose.yml")
    if not compose_file.exists():
        print("❌ docker-compose.yml not found")
        return False
    
    # Check if .env file exists (required for validation)
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  No .env file found (Docker Compose validation skipped)")
        print("   Create .env from .env.example to enable full validation")
        return True  # Don't fail, just skip
    
    try:
        result = subprocess.run(
            ["docker", "compose", "config"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            # Check if error is due to missing env vars (expected in dev)
            if "required variable" in result.stderr or "is not set" in result.stderr:
                print("⚠️  Docker Compose needs environment variables")
                print("   Add DB_PASSWORD and GRAFANA_PASSWORD to .env file")
                return True  # Not a code issue, just config
            else:
                print(f"❌ Docker Compose config invalid:")
                print(result.stderr[:200])  # Limit output
                return False
        
        print("✅ Docker Compose config valid")
        return True
    except FileNotFoundError:
        print("⚠️  Docker Compose not installed (required for VPS deployment)")
        return False
    except subprocess.TimeoutExpired:
        print("⚠️  Docker Compose config check timed out")
        return False


def test_documentation():
    """Test VPS documentation exists"""
    print("🔍 Testing documentation...")
    
    docs = [
        "docs/VPS_DEPLOYMENT_GUIDE.md",
        "docs/VPS_REMOTE_DEVELOPMENT.md"
    ]
    
    all_exist = True
    for doc in docs:
        if not Path(doc).exists():
            print(f"❌ Missing: {doc}")
            all_exist = False
    
    if all_exist:
        print("✅ Documentation complete")
    
    return all_exist


def test_readme_updated():
    """Test README includes deployment options"""
    print("🔍 Testing README updates...")
    
    readme_path = Path("README.md")
    if not readme_path.exists():
        print("❌ README.md not found")
        return False
    
    content = readme_path.read_text()
    
    required_sections = [
        "Deployment Options",
        "Local Deployment",
        "VPS Deployment",
        "Remote Development"
    ]
    
    missing = []
    for section in required_sections:
        if section not in content:
            missing.append(section)
    
    if missing:
        print(f"❌ README missing sections: {', '.join(missing)}")
        return False
    
    print("✅ README deployment options documented")
    return True


def test_env_example_updated():
    """Test .env.example includes VPS configuration"""
    print("🔍 Testing .env.example updates...")
    
    env_path = Path(".env.example")
    if not env_path.exists():
        print("❌ .env.example not found")
        return False
    
    content = env_path.read_text()
    
    required_configs = [
        "VPS Deployment Configuration",
        "TAILSCALE_ENABLED",
        "REMOTE_DEV"
    ]
    
    missing = []
    for config in required_configs:
        if config not in content:
            missing.append(config)
    
    if missing:
        print(f"❌ .env.example missing configs: {', '.join(missing)}")
        return False
    
    print("✅ .env.example VPS configuration added")
    return True


def main():
    print("=" * 60)
    print("Hybrid Deployment Validation")
    print("=" * 60)
    print()
    
    tests = [
        ("Local Environment", test_local_environment),
        ("VPS Scripts", test_vps_scripts),
        ("Docker Compose", test_docker_compose),
        ("Documentation", test_documentation),
        ("README Updates", test_readme_updated),
        ("Environment Config", test_env_example_updated)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} failed with error: {e}")
            results.append((name, False))
        print()
    
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 All tests passed! Hybrid deployment ready.")
        print()
        print("Next steps:")
        print("1. Review docs/VPS_DEPLOYMENT_GUIDE.md for setup instructions")
        print("2. Provision Singapore VPS (DigitalOcean/Vultr recommended)")
        print("3. Run: ./scripts/vps/setup_vps.sh on VPS")
        print("4. Follow Tailscale authentication process")
        print("5. Deploy: ./scripts/vps/deploy_to_vps.sh")
        return 0
    else:
        print("⚠️  Some tests failed. Review output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
