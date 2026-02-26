"""
Example: File Operations with Platform Integration System

This example demonstrates how to use the Platform Integration System
for cross-platform file operations with proper permission handling.

Performance: O(1) for single file operations, O(n) for batch operations
Security: All operations validated with permission checks
"""

import sys
from pathlib import Path
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from guru_platform.controllers.file_operations import FileOperationsController
from guru_platform.permissions.manager import PermissionManager
from guru_platform.platform_detector import PlatformDetector


def example_basic_file_operations():
    """Example: Basic file create, read, update, delete operations."""
    print("=" * 60)
    print("Example 1: Basic File Operations")
    print("=" * 60)
    
    # Initialize controller
    controller = FileOperationsController()
    
    # Create a test file
    test_file = Path("test_example.txt")
    content = "Hello from Agent Guru Platform Integration!"
    
    print(f"\n1. Creating file: {test_file}")
    controller.create_file(str(test_file), content)
    print(f"   ✓ File created successfully")
    
    # Read the file
    print(f"\n2. Reading file: {test_file}")
    read_content = controller.read_file(str(test_file))
    print(f"   Content: {read_content}")
    
    # Update the file
    print(f"\n3. Updating file: {test_file}")
    new_content = "Updated content from Agent Guru!"
    controller.update_file(str(test_file), new_content)
    print(f"   ✓ File updated successfully")
    
    # Verify update
    updated_content = controller.read_file(str(test_file))
    print(f"   New content: {updated_content}")
    
    # Delete the file
    print(f"\n4. Deleting file: {test_file}")
    controller.delete_file(str(test_file))
    print(f"   ✓ File deleted successfully")


def example_directory_operations():
    """Example: Directory creation, listing, and deletion."""
    print("\n" + "=" * 60)
    print("Example 2: Directory Operations")
    print("=" * 60)
    
    controller = FileOperationsController()
    
    # Create directory
    test_dir = Path("test_directory")
    print(f"\n1. Creating directory: {test_dir}")
    controller.create_directory(str(test_dir))
    print(f"   ✓ Directory created successfully")
    
    # Create files in directory
    print(f"\n2. Creating files in directory")
    for i in range(3):
        file_path = test_dir / f"file_{i}.txt"
        controller.create_file(str(file_path), f"Content {i}")
        print(f"   ✓ Created: {file_path}")
    
    # List directory contents
    print(f"\n3. Listing directory contents")
    contents = controller.list_directory(str(test_dir))
    for item in contents:
        print(f"   - {item}")
    
    # Delete directory (with confirmation)
    print(f"\n4. Deleting directory: {test_dir}")
    controller.delete_directory(str(test_dir), recursive=True)
    print(f"   ✓ Directory deleted successfully")


def example_file_copy_move():
    """Example: Copy and move file operations."""
    print("\n" + "=" * 60)
    print("Example 3: Copy and Move Operations")
    print("=" * 60)
    
    controller = FileOperationsController()
    
    # Create source file
    source = Path("source_file.txt")
    print(f"\n1. Creating source file: {source}")
    controller.create_file(str(source), "Original content")
    print(f"   ✓ Source file created")
    
    # Copy file
    copy_dest = Path("copied_file.txt")
    print(f"\n2. Copying file to: {copy_dest}")
    controller.copy_file(str(source), str(copy_dest))
    print(f"   ✓ File copied successfully")
    
    # Verify both files exist
    print(f"\n3. Verifying files:")
    print(f"   Source exists: {source.exists()}")
    print(f"   Copy exists: {copy_dest.exists()}")
    
    # Move file
    move_dest = Path("moved_file.txt")
    print(f"\n4. Moving file to: {move_dest}")
    controller.move_file(str(copy_dest), str(move_dest))
    print(f"   ✓ File moved successfully")
    
    # Verify move
    print(f"\n5. Verifying move:")
    print(f"   Original copy exists: {copy_dest.exists()}")
    print(f"   Moved file exists: {move_dest.exists()}")
    
    # Cleanup
    print(f"\n6. Cleaning up")
    controller.delete_file(str(source))
    controller.delete_file(str(move_dest))
    print(f"   ✓ Cleanup complete")


def example_permission_checks():
    """Example: Permission validation before operations."""
    print("\n" + "=" * 60)
    print("Example 4: Permission Checks")
    print("=" * 60)
    
    controller = FileOperationsController()
    permission_manager = PermissionManager()
    
    # Check current permission level
    print(f"\n1. Checking current permissions:")
    is_elevated = permission_manager.is_elevated()
    print(f"   Running with elevated privileges: {is_elevated}")
    
    # Check file access permissions
    test_file = Path("permission_test.txt")
    controller.create_file(str(test_file), "Test content")
    
    print(f"\n2. Checking file access permissions:")
    can_read = permission_manager.can_access_path(str(test_file), "r")
    can_write = permission_manager.can_access_path(str(test_file), "w")
    can_execute = permission_manager.can_access_path(str(test_file), "x")
    
    print(f"   Read permission: {can_read}")
    print(f"   Write permission: {can_write}")
    print(f"   Execute permission: {can_execute}")
    
    # Cleanup
    controller.delete_file(str(test_file))
    print(f"\n3. Cleanup complete")


def example_batch_operations():
    """Example: Batch file operations for efficiency."""
    print("\n" + "=" * 60)
    print("Example 5: Batch Operations")
    print("=" * 60)
    
    controller = FileOperationsController()
    
    # Create multiple files
    print(f"\n1. Creating batch of files:")
    file_paths: List[str] = []
    for i in range(5):
        file_path = f"batch_file_{i}.txt"
        file_paths.append(file_path)
        controller.create_file(file_path, f"Batch content {i}")
        print(f"   ✓ Created: {file_path}")
    
    # Read all files
    print(f"\n2. Reading all files:")
    for file_path in file_paths:
        content = controller.read_file(file_path)
        print(f"   {file_path}: {content}")
    
    # Delete all files
    print(f"\n3. Deleting all files:")
    for file_path in file_paths:
        controller.delete_file(file_path)
        print(f"   ✓ Deleted: {file_path}")


def example_platform_specific_paths():
    """Example: Platform-specific path handling."""
    print("\n" + "=" * 60)
    print("Example 6: Platform-Specific Paths")
    print("=" * 60)
    
    platform_info = PlatformDetector.detect()
    controller = FileOperationsController()
    
    print(f"\n1. Current platform: {platform_info.os_name}")
    
    # Get platform-specific temp directory
    if platform_info.os_name == "Windows":
        temp_dir = Path("C:/Temp")
    else:
        temp_dir = Path("/tmp")
    
    print(f"   Temp directory: {temp_dir}")
    
    # Create file in temp directory
    if temp_dir.exists():
        test_file = temp_dir / "platform_test.txt"
        print(f"\n2. Creating file in temp directory:")
        print(f"   Path: {test_file}")
        
        try:
            controller.create_file(str(test_file), "Platform-specific test")
            print(f"   ✓ File created successfully")
            
            # Cleanup
            controller.delete_file(str(test_file))
            print(f"   ✓ File deleted successfully")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    else:
        print(f"   ⚠ Temp directory does not exist")


def main():
    """Run all file operations examples."""
    print("\n" + "=" * 60)
    print("Agent Guru Platform Integration - File Operations Examples")
    print("=" * 60)
    
    try:
        # Run all examples
        example_basic_file_operations()
        example_directory_operations()
        example_file_copy_move()
        example_permission_checks()
        example_batch_operations()
        example_platform_specific_paths()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
