#!/usr/bin/env python3
"""
Test runner script for the Iris Smart Glasses project.

Runs all tests and provides coverage reporting.
"""

import sys
import os
import subprocess
import argparse

def run_tests(test_files=None, verbose=False, coverage=False):
    """Run tests with optional coverage."""
    
    # Base pytest command
    cmd = ['python', '-m', 'pytest']
    
    if verbose:
        cmd.append('-v')
    
    if coverage:
        cmd.extend(['--cov=core', '--cov=features', '--cov-report=html', '--cov-report=term'])
    
    # Add specific test files or run all
    if test_files:
        cmd.extend(test_files)
    else:
        cmd.append('tests/')
    
    # Add asyncio mode for async tests
    cmd.extend(['-p', 'no:warnings', '--asyncio-mode=auto'])
    
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=os.path.dirname(__file__))

def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description='Run Iris Smart Glasses tests')
    parser.add_argument('tests', nargs='*', help='Specific test files to run')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-c', '--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--parser', action='store_true', help='Run only parser tests')
    parser.add_argument('--discovery', action='store_true', help='Run only discovery tests')
    parser.add_argument('--iot', action='store_true', help='Run only IoT tests')
    parser.add_argument('--features', action='store_true', help='Run only feature tests')
    
    args = parser.parse_args()
    
    # Determine which tests to run
    test_files = []
    
    if args.parser:
        test_files.append('tests/test_parser.py')
    if args.discovery:
        test_files.append('tests/test_discovery.py')
    if args.iot:
        test_files.append('tests/test_iot.py')
    if args.features:
        test_files.append('tests/test_features.py')
    
    # If specific tests provided, use those
    if args.tests:
        test_files = args.tests
    
    # Run the tests
    result = run_tests(test_files, args.verbose, args.coverage)
    
    if result.returncode == 0:
        print("\n✅ All tests passed!")
        
        if args.coverage:
            print("\n📊 Coverage report generated in htmlcov/index.html")
    else:
        print("\n❌ Some tests failed!")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())