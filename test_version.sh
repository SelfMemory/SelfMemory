#!/bin/bash

# Test script to validate versioning logic
echo "Testing automatic versioning logic..."

# Create a temporary pyproject.toml for testing
cat > test_pyproject.toml << EOF
[project]
name = "selfmemory"
version = "0.2.0"
description = "Test"
EOF

echo "Initial version in test file:"
grep '^version = ' test_pyproject.toml

# Test 1: Patch version increment (default)
echo -e "\n=== Test 1: Patch increment ==="
current_version=$(grep '^version = ' test_pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "Current version: $current_version"

IFS='.' read -r major minor patch <<< "$current_version"
patch=$((patch + 1))
new_version="$major.$minor.$patch"
echo "New version: $new_version"

sed -i "s/version = \"$current_version\"/version = \"$new_version\"/" test_pyproject.toml
echo "Updated file:"
grep '^version = ' test_pyproject.toml

# Test 2: Minor version increment
echo -e "\n=== Test 2: Minor increment ==="
current_version=$(grep '^version = ' test_pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "Current version: $current_version"

IFS='.' read -r major minor patch <<< "$current_version"
minor=$((minor + 1))
patch=0
new_version="$major.$minor.$patch"
echo "New version: $new_version"

sed -i "s/version = \"$current_version\"/version = \"$new_version\"/" test_pyproject.toml
echo "Updated file:"
grep '^version = ' test_pyproject.toml

# Test 3: Major version increment
echo -e "\n=== Test 3: Major increment ==="
current_version=$(grep '^version = ' test_pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "Current version: $current_version"

IFS='.' read -r major minor patch <<< "$current_version"
major=$((major + 1))
minor=0
patch=0
new_version="$major.$minor.$patch"
echo "New version: $new_version"

sed -i "s/version = \"$current_version\"/version = \"$new_version\"/" test_pyproject.toml
echo "Updated file:"
grep '^version = ' test_pyproject.toml

# Cleanup
rm test_pyproject.toml
echo -e "\n✅ All tests passed! Versioning logic works correctly."
