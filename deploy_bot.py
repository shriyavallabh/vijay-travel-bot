#!/usr/bin/env python3
"""
Railway Deployment Automation Script for Travel RAG WhatsApp Bot

This script automates the deployment process to Railway:
1. Checks Railway CLI installation
2. Handles authentication (using API token)
3. Initializes project
4. Uploads environment variables
5. Deploys the application
6. Retrieves the public URL

Usage:
    python deploy_bot.py

Requirements:
    - Railway CLI: npm i -g @railway/cli
    - Node.js installed
"""

import os
import sys
import subprocess
import re
import time
from pathlib import Path

# Railway API Token for authentication (with workspace access)
RAILWAY_API_TOKEN = "84bddda2-68b4-4681-b4c8-65f2eb9e39bc"


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_step(step_num: int, message: str):
    """Print a formatted step message"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}[Step {step_num}]{Colors.ENDC} {message}")


def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.GREEN}[OK]{Colors.ENDC} {message}")


def print_error(message: str):
    """Print an error message"""
    print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {message}")


def print_warning(message: str):
    """Print a warning message"""
    print(f"{Colors.WARNING}[WARNING]{Colors.ENDC} {message}")


def print_info(message: str):
    """Print an info message"""
    print(f"{Colors.BLUE}[INFO]{Colors.ENDC} {message}")


def get_railway_env() -> dict:
    """Get environment for Railway commands"""
    env = os.environ.copy()
    # Set the API token for authentication
    if RAILWAY_API_TOKEN:
        env["RAILWAY_TOKEN"] = RAILWAY_API_TOKEN
    return env


def run_command(cmd: list, capture_output: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """
    Run a shell command and return the result.

    Args:
        cmd: Command as list of strings
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise exception on non-zero exit

    Returns:
        CompletedProcess instance
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=check,
            env=get_railway_env()
        )
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {' '.join(cmd)}")
        if e.stdout:
            print(f"  stdout: {e.stdout}")
        if e.stderr:
            print(f"  stderr: {e.stderr}")
        raise
    except FileNotFoundError:
        print_error(f"Command not found: {cmd[0]}")
        raise


def check_railway_cli() -> bool:
    """
    Step 1: Check if Railway CLI is installed.

    Returns:
        True if installed, False otherwise
    """
    print_step(1, "Checking Railway CLI installation...")

    try:
        result = run_command(["railway", "--version"], check=False)
        if result.returncode == 0:
            version = result.stdout.strip()
            print_success(f"Railway CLI installed: {version}")
            return True
        else:
            print_error("Railway CLI not working properly")
            return False
    except FileNotFoundError:
        print_error("Railway CLI is not installed!")
        print()
        print(f"{Colors.BOLD}Please install Railway CLI:{Colors.ENDC}")
        print("  npm i -g @railway/cli")
        print()
        print("Or with Homebrew (macOS):")
        print("  brew install railway")
        print()
        return False


def check_login() -> bool:
    """
    Step 2: Check Railway authentication status.

    Returns:
        True if authenticated, False otherwise
    """
    print_step(2, "Checking Railway authentication...")

    try:
        result = run_command(["railway", "whoami"], check=False)

        if result.returncode == 0 and result.stdout.strip():
            user = result.stdout.strip()
            print_success(f"Authenticated as: {user}")
            return True

        # Not logged in
        print_error("Not logged in to Railway!")
        print()
        print(f"{Colors.BOLD}Please run this command in your terminal first:{Colors.ENDC}")
        print(f"  {Colors.CYAN}railway login{Colors.ENDC}")
        print()
        print("Then run this script again.")
        return False

    except Exception as e:
        print_error(f"Authentication error: {e}")
        return False


def init_project() -> bool:
    """
    Step 3: Initialize Railway project.

    Returns:
        True if successful, False otherwise
    """
    print_step(3, "Initializing Railway project...")

    # Check if already linked to a project
    try:
        result = run_command(["railway", "status"], check=False)

        if result.returncode == 0 and "Project:" in result.stdout:
            # Already linked to a project
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if "Project:" in line:
                    project_name = line.split("Project:")[-1].strip()
                    print_success(f"Already linked to project: {project_name}")

                    # Ask if user wants to continue with existing project
                    response = input(f"\nContinue with existing project '{project_name}'? [Y/n]: ").strip().lower()
                    if response in ['', 'y', 'yes']:
                        return True
                    else:
                        print_info("Unlinking current project...")
                        run_command(["railway", "unlink"], check=False)
                        break
    except:
        pass

    # Initialize new project
    print_info("Creating new Railway project...")
    print()
    print(f"{Colors.WARNING}NOTE: You will be prompted to:{Colors.ENDC}")
    print("  1. Create a new project or select existing one")
    print("  2. Enter a project name (e.g., 'vijay-travel-bot')")
    print()

    try:
        # Run railway init interactively
        init_result = subprocess.run(
            ["railway", "init"],
            capture_output=False,
            text=True,
            env=get_railway_env()
        )

        if init_result.returncode == 0:
            # Verify project was created
            status = run_command(["railway", "status"], check=False)
            if status.returncode == 0 and "Project:" in status.stdout:
                print_success("Project initialized successfully!")
                return True

        print_error("Project initialization failed")
        return False

    except Exception as e:
        print_error(f"Init error: {e}")
        return False


def parse_env_file(env_path: str) -> dict:
    """
    Parse .env file and return key-value pairs.

    Args:
        env_path: Path to .env file

    Returns:
        Dictionary of environment variables
    """
    env_vars = {}

    if not os.path.exists(env_path):
        print_warning(f".env file not found at {env_path}")
        return env_vars

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE (handle values with = in them)
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove surrounding quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]

                if key:
                    env_vars[key] = value

    return env_vars


def upload_secrets(env_path: str) -> bool:
    """
    Step 4: Upload environment variables to Railway.

    Args:
        env_path: Path to .env file

    Returns:
        True if successful, False otherwise
    """
    print_step(4, "Uploading environment variables...")

    env_vars = parse_env_file(env_path)

    if not env_vars:
        print_warning("No environment variables found in .env file")
        response = input("Continue without environment variables? [y/N]: ").strip().lower()
        return response in ['y', 'yes']

    print_info(f"Found {len(env_vars)} environment variables")

    # Display variables (mask sensitive values)
    print()
    for key in env_vars:
        value = env_vars[key]
        if any(secret in key.upper() for secret in ['KEY', 'TOKEN', 'SECRET', 'PASSWORD']):
            masked = value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '****'
            print(f"  {key}={masked}")
        else:
            print(f"  {key}={value[:50]}{'...' if len(value) > 50 else ''}")
    print()

    # Upload each variable
    success_count = 0
    fail_count = 0

    for key, value in env_vars.items():
        try:
            # Use railway variables set
            result = run_command(
                ["railway", "variables", "set", f"{key}={value}"],
                check=False
            )

            if result.returncode == 0:
                success_count += 1
                print(f"  {Colors.GREEN}[OK]{Colors.ENDC} {key}")
            else:
                fail_count += 1
                print(f"  {Colors.FAIL}[FAIL]{Colors.ENDC} {key}: {result.stderr.strip()}")

        except Exception as e:
            fail_count += 1
            print(f"  {Colors.FAIL}[FAIL]{Colors.ENDC} {key}: {e}")

    print()
    print_info(f"Uploaded: {success_count}/{len(env_vars)} variables")

    if fail_count > 0:
        print_warning(f"Failed: {fail_count} variables")
        response = input("Continue with deployment? [Y/n]: ").strip().lower()
        return response in ['', 'y', 'yes']

    print_success("All environment variables uploaded!")
    return True


def deploy() -> bool:
    """
    Step 5: Deploy the application to Railway.

    Returns:
        True if successful, False otherwise
    """
    print_step(5, "Deploying application...")

    print_info("Starting deployment (this may take a few minutes)...")
    print()

    try:
        # Deploy with detach flag to avoid blocking
        result = subprocess.run(
            ["railway", "up", "--detach"],
            capture_output=False,
            text=True,
            env=get_railway_env()
        )

        if result.returncode == 0:
            print()
            print_success("Deployment initiated successfully!")
            return True
        else:
            print_error("Deployment failed")
            return False

    except Exception as e:
        print_error(f"Deployment error: {e}")
        return False


def get_public_url() -> str:
    """
    Step 6: Get the public URL of the deployed application.

    Returns:
        Public URL string or empty string if not found
    """
    print_step(6, "Retrieving public URL...")

    # Wait a moment for deployment to register
    print_info("Waiting for deployment to initialize...")
    time.sleep(3)

    try:
        # Try railway domain command
        result = run_command(["railway", "domain"], check=False)

        if result.returncode == 0 and result.stdout.strip():
            domain = result.stdout.strip()
            if not domain.startswith("http"):
                domain = f"https://{domain}"
            print_success(f"Public URL: {domain}")
            return domain
    except:
        pass

    # Try parsing from railway status
    try:
        result = run_command(["railway", "status"], check=False)

        if result.returncode == 0:
            # Look for URL patterns
            url_pattern = r'https?://[^\s]+'
            matches = re.findall(url_pattern, result.stdout)

            for url in matches:
                if 'railway.app' in url or 'up.railway.app' in url:
                    print_success(f"Public URL: {url}")
                    return url
    except:
        pass

    # If no URL found, check if we need to generate a domain
    print_warning("No public domain found.")
    print_info("Attempting to generate a public domain...")

    try:
        # Generate domain
        gen_result = subprocess.run(
            ["railway", "domain"],
            capture_output=False,
            text=True,
            env=get_railway_env()
        )

        if gen_result.returncode == 0:
            # Try to get it again
            time.sleep(2)
            result = run_command(["railway", "domain"], check=False)
            if result.returncode == 0 and result.stdout.strip():
                domain = result.stdout.strip()
                if not domain.startswith("http"):
                    domain = f"https://{domain}"
                print_success(f"Generated public URL: {domain}")
                return domain
    except:
        pass

    print_warning("Could not retrieve public URL automatically.")
    print_info("Please check Railway dashboard for the public URL.")
    return ""


def print_final_instructions(url: str):
    """Print final deployment instructions"""
    print()
    print("=" * 60)
    print(f"{Colors.GREEN}{Colors.BOLD}DEPLOYMENT COMPLETE!{Colors.ENDC}")
    print("=" * 60)
    print()

    if url:
        webhook_url = f"{url}/webhook"
        print(f"{Colors.BOLD}Your Webhook URL for Meta:{Colors.ENDC}")
        print(f"  {Colors.CYAN}{webhook_url}{Colors.ENDC}")
        print()
        print(f"{Colors.BOLD}Health Check URL:{Colors.ENDC}")
        print(f"  {url}/")
        print()
        print(f"{Colors.BOLD}API Endpoints:{Colors.ENDC}")
        print(f"  GET  {url}/           - Health check")
        print(f"  GET  {url}/stats      - System statistics")
        print(f"  GET  {url}/customers  - List customers")
        print(f"  POST {url}/query      - Query the agent")
        print()

    print(f"{Colors.BOLD}Next Steps:{Colors.ENDC}")
    print("  1. Copy the webhook URL above")
    print("  2. Go to Meta Developer Console")
    print("  3. Navigate to WhatsApp > Configuration > Webhook")
    print("  4. Paste the webhook URL")
    print("  5. Use your VERIFY_TOKEN from .env")
    print("  6. Subscribe to 'messages' webhook field")
    print()
    print(f"{Colors.BOLD}Useful Commands:{Colors.ENDC}")
    print("  railway logs        - View application logs")
    print("  railway status      - Check deployment status")
    print("  railway open        - Open Railway dashboard")
    print("  railway down        - Stop the deployment")
    print()
    print("=" * 60)


def main():
    """Main deployment orchestration"""
    print()
    print("=" * 60)
    print(f"{Colors.HEADER}{Colors.BOLD}RAILWAY DEPLOYMENT AUTOMATION{Colors.ENDC}")
    print(f"{Colors.HEADER}Travel RAG WhatsApp Bot{Colors.ENDC}")
    print("=" * 60)

    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    env_path = script_dir / ".env"

    print(f"\nProject directory: {script_dir}")
    print(f"Environment file: {env_path}")

    # Change to project directory
    os.chdir(script_dir)

    try:
        # Step 1: Check Railway CLI
        if not check_railway_cli():
            sys.exit(1)

        # Step 2: Check/Handle login
        if not check_login():
            sys.exit(1)

        # Step 3: Initialize project
        if not init_project():
            sys.exit(1)

        # Step 4: Upload secrets
        if not upload_secrets(str(env_path)):
            sys.exit(1)

        # Step 5: Deploy
        if not deploy():
            sys.exit(1)

        # Step 6: Get public URL
        url = get_public_url()

        # Final instructions
        print_final_instructions(url)

        print_success("Deployment automation completed!")

    except KeyboardInterrupt:
        print()
        print_warning("Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print()
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
