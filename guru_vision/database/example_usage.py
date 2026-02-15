"""
Example usage of the FaceDatabase module.

This script demonstrates how to use the face database for storing
and retrieving face embeddings.
"""

import numpy as np
from guru_vision.database import FaceDatabase


def main():
    """Demonstrate basic database operations."""
    
    # Initialize database
    print("Initializing face database...")
    db = FaceDatabase("guru_face/database/example_identities.json")
    
    # Create some example embeddings (normally these would come from the recognition model)
    print("\nCreating example embeddings...")
    john_embeddings = [
        np.random.randn(512).astype(np.float32) for _ in range(3)
    ]
    jane_embeddings = [
        np.random.randn(512).astype(np.float32) for _ in range(2)
    ]
    
    # Add identities
    print("\nAdding identities to database...")
    db.add_identity("John Doe", john_embeddings, permission_level="admin")
    db.add_identity("Jane Smith", jane_embeddings, permission_level="user")
    
    print(f"  - Added John Doe with {len(john_embeddings)} embeddings (admin)")
    print(f"  - Added Jane Smith with {len(jane_embeddings)} embeddings (user)")
    
    # Add another embedding to existing identity
    print("\nAdding additional embedding to John Doe...")
    new_embedding = np.random.randn(512).astype(np.float32)
    db.add_embedding("John Doe", new_embedding, angle_category="profile")
    
    # Get all identities
    print("\nRetrieving all identities...")
    identities = db.get_all_identities()
    for identity in identities:
        print(f"  - {identity.name}: {len(identity.embeddings)} embeddings, "
              f"permission: {identity.permission_level}")
    
    # Search for a match
    print("\nSearching for identity match...")
    query_embedding = john_embeddings[0] + np.random.randn(512).astype(np.float32) * 0.01
    result = db.search(query_embedding, threshold=0.6)
    
    if result:
        print(f"  Match found: {result['identity']}")
        print(f"  Confidence: {result['confidence']:.4f}")
        print(f"  Permission: {result['permission_level']}")
    else:
        print("  No match found above threshold")
    
    # Update permission
    print("\nUpdating Jane Smith's permission to admin...")
    db.update_permission("Jane Smith", "admin")
    jane = db.get_identity("Jane Smith")
    print(f"  New permission level: {jane.permission_level}")
    
    # Save database
    print("\nSaving database to disk...")
    db.save()
    print(f"  Database saved to: {db.db_path}")
    
    # Export database
    print("\nExporting database...")
    export_path = "guru_face/database/backup.json"
    db.export_json(export_path)
    print(f"  Database exported to: {export_path}")
    
    # Load database
    print("\nLoading database from disk...")
    db2 = FaceDatabase("guru_face/database/example_identities.json")
    db2.load()
    print(f"  Loaded {len(db2.get_all_identities())} identities")
    
    # Remove identity
    print("\nRemoving Jane Smith...")
    db.remove_identity("Jane Smith")
    print(f"  Remaining identities: {len(db.get_all_identities())}")
    
    print("\nExample completed successfully!")


if __name__ == "__main__":
    main()
