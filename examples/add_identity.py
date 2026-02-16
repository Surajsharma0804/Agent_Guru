#!/usr/bin/env python3
"""
GuruVision Incremental Identity Addition Example

This example demonstrates how to add new identities to the GuruVision system
without retraining the model. This allows for quick updates to the face database
while maintaining recognition accuracy for existing identities.

Requirements: 16.1, 16.2

Usage:
    python examples/add_identity.py
    python examples/add_identity.py --name "John Doe" --images person_images/
    python examples/add_identity.py --name "Jane Smith" --images images/ --permission admin
"""

import os
import sys
import argparse
import glob
import cv2

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guru_vision.engine import GuruVisionEngine


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Add new identity to GuruVision without retraining",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (prompts for input)
  python examples/add_identity.py
  
  # Add identity from command line
  python examples/add_identity.py --name "John Doe" --images person_images/
  
  # Add identity with specific permission level
  python examples/add_identity.py --name "Admin User" --images images/ --permission admin
  
  # Add identity from specific image files
  python examples/add_identity.py --name "Jane Smith" --images img1.jpg img2.jpg img3.jpg
        """
    )
    
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Name of the identity to add"
    )
    parser.add_argument(
        "--images",
        type=str,
        nargs="+",
        default=None,
        help="Path to image directory or list of image files"
    )
    parser.add_argument(
        "--permission",
        type=str,
        default="user",
        choices=["admin", "user", "guest", "denied"],
        help="Permission level for the identity (default: user)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (optional)"
    )
    parser.add_argument(
        "--min-images",
        type=int,
        default=5,
        help="Minimum number of images required (default: 5)"
    )
    
    return parser.parse_args()


def load_images_from_paths(image_paths):
    """
    Load images from file paths.
    
    Args:
        image_paths: List of image file paths or directories
        
    Returns:
        List of loaded image arrays
    """
    images = []
    supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
    
    for path in image_paths:
        if os.path.isdir(path):
            # Load all images from directory
            for ext in supported_extensions:
                pattern = os.path.join(path, f"*{ext}")
                images.extend([cv2.imread(f) for f in glob.glob(pattern)])
        elif os.path.isfile(path):
            # Load single image file
            ext = os.path.splitext(path.lower())[1]
            if ext in supported_extensions:
                img = cv2.imread(path)
                if img is not None:
                    images.append(img)
        else:
            print(f"⚠ Warning: Path not found: {path}")
    
    # Filter out None values (failed to load)
    images = [img for img in images if img is not None]
    
    return images


def interactive_mode():
    """
    Interactive mode for adding identities.
    
    Returns:
        Tuple of (name, image_paths, permission_level)
    """
    print("=" * 80)
    print("Interactive Identity Addition")
    print("=" * 80)
    print()
    
    # Get identity name
    while True:
        name = input("Enter identity name: ").strip()
        if name:
            break
        print("⚠ Name cannot be empty. Please try again.")
    
    print()
    
    # Get image paths
    print("Enter image paths (directory or individual files):")
    print("  • Enter a directory path to load all images from that directory")
    print("  • Enter individual image file paths separated by spaces")
    print("  • Press Enter when done")
    print()
    
    image_paths = []
    while True:
        path_input = input("Image path(s): ").strip()
        if not path_input:
            if image_paths:
                break
            else:
                print("⚠ At least one image path is required.")
                continue
        
        # Split by spaces and add to list
        paths = path_input.split()
        image_paths.extend(paths)
        
        print(f"  Added {len(paths)} path(s). Total: {len(image_paths)}")
        print("  Enter more paths or press Enter to continue...")
    
    print()
    
    # Get permission level
    print("Select permission level:")
    print("  1. admin   - Full system access")
    print("  2. user    - Standard access (default)")
    print("  3. guest   - Limited access")
    print("  4. denied  - Access denied")
    print()
    
    permission_map = {
        "1": "admin",
        "2": "user",
        "3": "guest",
        "4": "denied"
    }
    
    while True:
        choice = input("Permission level [1-4] (default: 2): ").strip()
        if not choice:
            permission_level = "user"
            break
        elif choice in permission_map:
            permission_level = permission_map[choice]
            break
        else:
            print("⚠ Invalid choice. Please enter 1-4.")
    
    print()
    
    return name, image_paths, permission_level


def main():
    """
    Main function for adding identities incrementally.
    
    This example demonstrates:
    1. Initializing the GuruVision engine
    2. Loading images for a new identity
    3. Adding the identity without retraining
    4. Verifying the identity was added successfully
    5. Testing recognition with the new identity
    """
    args = parse_arguments()
    
    print("=" * 80)
    print("GuruVision Incremental Identity Addition")
    print("=" * 80)
    print()
    print("This tool allows you to add new identities to the face database")
    print("without retraining the model. The new identity will be immediately")
    print("available for recognition.")
    print()
    
    # =========================================================================
    # STEP 1: Get Identity Information
    # =========================================================================
    if args.name and args.images:
        # Use command-line arguments
        name = args.name
        image_paths = args.images
        permission_level = args.permission
        
        print(f"Identity: {name}")
        print(f"Permission: {permission_level}")
        print(f"Image sources: {len(image_paths)}")
        print()
    else:
        # Use interactive mode
        name, image_paths, permission_level = interactive_mode()
    
    # =========================================================================
    # STEP 2: Load Images
    # =========================================================================
    print("Loading images...")
    
    images = load_images_from_paths(image_paths)
    
    if not images:
        print("✗ No images could be loaded!")
        print()
        print("Please check:")
        print("  • Image paths are correct")
        print("  • Images are in supported formats (JPG, PNG, BMP)")
        print("  • Files are not corrupted")
        print()
        return
    
    print(f"✓ Loaded {len(images)} images")
    print()
    
    # Check minimum images requirement
    if len(images) < args.min_images:
        print(f"⚠ Warning: Only {len(images)} images provided.")
        print(f"  Minimum recommended: {args.min_images} images")
        print(f"  For best results: 10-20 images with various angles and lighting")
        print()
        
        response = input("Continue anyway? [y/N]: ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return
        print()
    
    # Display image statistics
    print("Image statistics:")
    for i, img in enumerate(images[:5], 1):  # Show first 5
        h, w = img.shape[:2]
        print(f"  Image {i}: {w}x{h} pixels")
    if len(images) > 5:
        print(f"  ... and {len(images) - 5} more")
    print()
    
    # =========================================================================
    # STEP 3: Initialize GuruVision Engine
    # =========================================================================
    print("Initializing GuruVision engine...")
    
    try:
        engine = GuruVisionEngine(config_path=args.config)
        engine.initialize()
        
        print("✓ Engine initialized")
        print()
        
    except Exception as e:
        print(f"✗ Failed to initialize engine: {str(e)}")
        print()
        print("Common issues:")
        print("  • ONNX model not found (run training first)")
        print("  • Database file not found")
        print("  • Invalid configuration")
        print()
        return
    
    # =========================================================================
    # STEP 4: Check if Identity Already Exists
    # =========================================================================
    print("Checking if identity already exists...")
    
    existing_identities = engine.get_identities()
    existing_names = [identity.name for identity in existing_identities]
    
    if name in existing_names:
        print(f"⚠ Identity '{name}' already exists in the database!")
        print()
        response = input("Do you want to add more embeddings to this identity? [y/N]: ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return
        print()
        print("Adding additional embeddings to existing identity...")
    else:
        print(f"✓ Identity '{name}' is new")
    
    print()
    
    # =========================================================================
    # STEP 5: Add Identity
    # =========================================================================
    print(f"Adding identity '{name}' to database...")
    print("This will:")
    print("  1. Detect faces in all images")
    print("  2. Align faces to standard orientation")
    print("  3. Extract 512-dimensional embeddings")
    print("  4. Store embeddings in the database")
    print()
    print("Processing...")
    
    try:
        success = engine.add_identity(
            name=name,
            images=images,
            permission_level=permission_level
        )
        
        if not success:
            print("✗ Failed to add identity!")
            print()
            print("Possible reasons:")
            print("  • No faces detected in the images")
            print("  • Face detection failed")
            print("  • Database write error")
            print()
            return
        
        print()
        print(f"✓ Identity '{name}' added successfully!")
        print()
        
    except Exception as e:
        print(f"✗ Error adding identity: {str(e)}")
        return
    
    # =========================================================================
    # STEP 6: Verify Identity Was Added
    # =========================================================================
    print("Verifying identity was added...")
    
    identities = engine.get_identities()
    identity_info = next((i for i in identities if i.name == name), None)
    
    if identity_info:
        print("✓ Identity verified in database")
        print()
        print("Identity Information:")
        print(f"  Name: {identity_info.name}")
        print(f"  Permission Level: {identity_info.permission_level}")
        print(f"  Number of Embeddings: {identity_info.num_embeddings}")
        print(f"  Date Added: {identity_info.date_added}")
        print()
    else:
        print("⚠ Warning: Identity not found in database after adding")
        print()
    
    # =========================================================================
    # STEP 7: Summary and Next Steps
    # =========================================================================
    print("=" * 80)
    print("Identity Addition Complete!")
    print("=" * 80)
    print()
    print(f"Identity '{name}' is now ready for recognition.")
    print()
    print("Next steps:")
    print("  1. Test recognition with webcam:")
    print("     python examples/recognize_webcam.py")
    print()
    print("  2. Add more identities:")
    print("     python examples/add_identity.py")
    print()
    print("  3. Update permission level:")
    print(f"     engine.update_permission('{name}', 'admin')")
    print()
    print("  4. Remove identity if needed:")
    print(f"     engine.remove_identity('{name}')")
    print()
    print("Tips for best recognition accuracy:")
    print("  • Add 10-20 images per identity")
    print("  • Include various angles (frontal, profile, 45-degree)")
    print("  • Include different lighting conditions")
    print("  • Include different expressions")
    print("  • Use high-quality, clear images")
    print()
    print("=" * 80)
    
    # Cleanup
    engine.shutdown()


if __name__ == "__main__":
    main()
