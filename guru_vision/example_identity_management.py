"""
Example: Identity Management with GuruVision Engine

This example demonstrates how to use the identity management methods:
- add_identity(): Add new identities without retraining
- remove_identity(): Remove identities from the database
- get_identities(): Query all stored identities
- update_permission(): Update permission levels

Requirements demonstrated: 16.1, 16.2, 16.3, 16.4, 16.5, 12.3, 12.4, 9.5, 12.2
"""

import numpy as np
import cv2
from pathlib import Path
from guru_vision.engine import GuruVisionEngine


def create_sample_images(num_images: int = 5) -> list:
    """
    Create sample face images for demonstration.
    
    In a real application, you would load actual face images from files.
    """
    images = []
    for i in range(num_images):
        # Create a simple colored image (in real use, load actual face photos)
        image = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
        
        # Add some variation to simulate different angles/lighting
        brightness = 1.0 + (i * 0.1)
        image = np.clip(image * brightness, 0, 255).astype(np.uint8)
        
        images.append(image)
    
    return images


def example_add_identity():
    """
    Example: Adding a new identity to the system.
    
    Requirements: 16.1, 16.2, 16.3, 16.4, 16.5
    """
    print("=" * 60)
    print("Example 1: Adding New Identities")
    print("=" * 60)
    
    # Initialize the engine
    engine = GuruVisionEngine()
    
    try:
        engine.initialize()
        print("✓ Engine initialized successfully\n")
    except Exception as e:
        print(f"✗ Failed to initialize engine: {e}")
        print("Note: This example requires a trained model and proper setup")
        return
    
    # Add a new identity with 5 images
    print("Adding identity 'John Doe' with 5 images...")
    images = create_sample_images(5)
    
    success = engine.add_identity(
        name="John Doe",
        images=images,
        permission_level="user"
    )
    
    if success:
        print("✓ Identity 'John Doe' added successfully")
        print("  - Permission level: user")
        print("  - Images processed: 5")
    else:
        print("✗ Failed to add identity")
    
    # Add another identity with admin permission
    print("\nAdding identity 'Jane Smith' with admin permission...")
    images = create_sample_images(7)
    
    success = engine.add_identity(
        name="Jane Smith",
        images=images,
        permission_level="admin"
    )
    
    if success:
        print("✓ Identity 'Jane Smith' added successfully")
        print("  - Permission level: admin")
        print("  - Images processed: 7")
    
    # Try adding with fewer than 5 images (will show warning)
    print("\nAdding identity 'Bob Wilson' with only 3 images (will show warning)...")
    images = create_sample_images(3)
    
    success = engine.add_identity(
        name="Bob Wilson",
        images=images,
        permission_level="guest"
    )
    
    if success:
        print("✓ Identity 'Bob Wilson' added (with warning about image count)")
    
    engine.shutdown()


def example_get_identities():
    """
    Example: Querying all stored identities.
    
    Requirements: 12.4
    """
    print("\n" + "=" * 60)
    print("Example 2: Querying All Identities")
    print("=" * 60)
    
    engine = GuruVisionEngine()
    
    try:
        engine.initialize()
        print("✓ Engine initialized successfully\n")
    except Exception as e:
        print(f"✗ Failed to initialize engine: {e}")
        return
    
    # Get all identities
    identities = engine.get_identities()
    
    print(f"Found {len(identities)} identities in database:\n")
    
    for identity in identities:
        print(f"Name: {identity.name}")
        print(f"  Permission Level: {identity.permission_level}")
        print(f"  Number of Embeddings: {identity.num_embeddings}")
        print(f"  Date Added: {identity.date_added}")
        if identity.metadata:
            print(f"  Metadata: {identity.metadata}")
        print()
    
    engine.shutdown()


def example_update_permission():
    """
    Example: Updating permission levels for identities.
    
    Requirements: 9.5, 12.2
    """
    print("\n" + "=" * 60)
    print("Example 3: Updating Permission Levels")
    print("=" * 60)
    
    engine = GuruVisionEngine()
    
    try:
        engine.initialize()
        print("✓ Engine initialized successfully\n")
    except Exception as e:
        print(f"✗ Failed to initialize engine: {e}")
        return
    
    # Update permission level for an identity
    print("Updating permission level for 'John Doe' from 'user' to 'admin'...")
    
    success = engine.update_permission("John Doe", "admin")
    
    if success:
        print("✓ Permission level updated successfully")
        
        # Verify the update
        identities = engine.get_identities()
        john = next((i for i in identities if i.name == "John Doe"), None)
        if john:
            print(f"  New permission level: {john.permission_level}")
    else:
        print("✗ Failed to update permission (identity may not exist)")
    
    # Try updating a non-existent identity
    print("\nTrying to update non-existent identity 'Unknown Person'...")
    success = engine.update_permission("Unknown Person", "user")
    
    if not success:
        print("✓ Correctly returned False for non-existent identity")
    
    engine.shutdown()


def example_remove_identity():
    """
    Example: Removing identities from the database.
    
    Requirements: 12.3
    """
    print("\n" + "=" * 60)
    print("Example 4: Removing Identities")
    print("=" * 60)
    
    engine = GuruVisionEngine()
    
    try:
        engine.initialize()
        print("✓ Engine initialized successfully\n")
    except Exception as e:
        print(f"✗ Failed to initialize engine: {e}")
        return
    
    # Show current identities
    identities = engine.get_identities()
    print(f"Current identities: {len(identities)}")
    for identity in identities:
        print(f"  - {identity.name} ({identity.permission_level})")
    
    # Remove an identity
    print("\nRemoving identity 'Bob Wilson'...")
    success = engine.remove_identity("Bob Wilson")
    
    if success:
        print("✓ Identity removed successfully")
        
        # Show updated list
        identities = engine.get_identities()
        print(f"\nRemaining identities: {len(identities)}")
        for identity in identities:
            print(f"  - {identity.name} ({identity.permission_level})")
    else:
        print("✗ Failed to remove identity (may not exist)")
    
    # Try removing a non-existent identity
    print("\nTrying to remove non-existent identity 'Unknown Person'...")
    success = engine.remove_identity("Unknown Person")
    
    if not success:
        print("✓ Correctly returned False for non-existent identity")
    
    engine.shutdown()


def example_complete_workflow():
    """
    Example: Complete workflow demonstrating all identity management operations.
    
    Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 12.3, 12.4, 9.5, 12.2
    """
    print("\n" + "=" * 60)
    print("Example 5: Complete Identity Management Workflow")
    print("=" * 60)
    
    engine = GuruVisionEngine()
    
    try:
        engine.initialize()
        print("✓ Engine initialized successfully\n")
    except Exception as e:
        print(f"✗ Failed to initialize engine: {e}")
        print("\nNote: This example requires:")
        print("  1. A trained ONNX model at the configured path")
        print("  2. Proper configuration file or default paths")
        print("  3. All required dependencies installed")
        return
    
    # Step 1: Add multiple identities
    print("Step 1: Adding multiple identities...")
    identities_to_add = [
        ("Alice Johnson", "admin", 6),
        ("Bob Smith", "user", 5),
        ("Charlie Brown", "guest", 8),
    ]
    
    for name, permission, num_images in identities_to_add:
        images = create_sample_images(num_images)
        success = engine.add_identity(name, images, permission)
        print(f"  {'✓' if success else '✗'} {name} ({permission})")
    
    # Step 2: Query all identities
    print("\nStep 2: Querying all identities...")
    identities = engine.get_identities()
    print(f"  Total identities: {len(identities)}")
    
    # Step 3: Update permissions
    print("\nStep 3: Updating permissions...")
    engine.update_permission("Bob Smith", "admin")
    print("  ✓ Bob Smith promoted to admin")
    
    # Step 4: Remove an identity
    print("\nStep 4: Removing an identity...")
    engine.remove_identity("Charlie Brown")
    print("  ✓ Charlie Brown removed")
    
    # Step 5: Final state
    print("\nStep 5: Final database state...")
    identities = engine.get_identities()
    for identity in identities:
        print(f"  - {identity.name}: {identity.permission_level} "
              f"({identity.num_embeddings} embeddings)")
    
    engine.shutdown()
    print("\n✓ Workflow completed successfully")


if __name__ == "__main__":
    print("GuruVision Identity Management Examples")
    print("=" * 60)
    print()
    print("These examples demonstrate the identity management API.")
    print("Note: Requires a trained model and proper configuration.")
    print()
    
    # Run examples
    try:
        example_add_identity()
        example_get_identities()
        example_update_permission()
        example_remove_identity()
        example_complete_workflow()
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user")
    except Exception as e:
        print(f"\n\nError running examples: {e}")
        print("Make sure you have:")
        print("  1. Trained a model using the training pipeline")
        print("  2. Configured the model and database paths")
        print("  3. Installed all required dependencies")
