"""Tests for permission management."""

import time


from Agent_Guru.reasoning.safety.permissions import Permission, PermissionManager


class TestPermission:
    """Tests for Permission model."""
    
    def test_permission_creation(self):
        """Test creating a permission."""
        perm = Permission(
            user_id="user123",
            permission_scope="messaging",
            granted_at=time.time(),
            granted_by="admin",
        )
        
        assert perm.user_id == "user123"  # nosec B101
        assert perm.permission_scope == "messaging"  # nosec B101
        assert perm.granted_by == "admin"  # nosec B101
        assert perm.expires_at is None  # nosec B101
        assert perm.metadata == {}  # nosec B101
    
    def test_permission_with_expiration(self):
        """Test permission with expiration."""
        now = time.time()
        perm = Permission(
            user_id="user123",
            permission_scope="messaging",
            granted_at=now,
            granted_by="admin",
            expires_at=now + 3600,  # Expires in 1 hour
        )
        
        assert not perm.is_expired()  # nosec B101
    
    def test_permission_expired(self):
        """Test expired permission."""
        now = time.time()
        perm = Permission(
            user_id="user123",
            permission_scope="messaging",
            granted_at=now - 7200,  # Granted 2 hours ago
            granted_by="admin",
            expires_at=now - 3600,  # Expired 1 hour ago
        )
        
        assert perm.is_expired()  # nosec B101
    
    def test_permission_never_expires(self):
        """Test permission that never expires."""
        perm = Permission(
            user_id="user123",
            permission_scope="messaging",
            granted_at=time.time() - 86400,  # Granted 1 day ago
            granted_by="admin",
            expires_at=None,
        )
        
        assert not perm.is_expired()  # nosec B101
    
    def test_permission_to_dict(self):
        """Test converting permission to dictionary."""
        now = time.time()
        perm = Permission(
            user_id="user123",
            permission_scope="messaging",
            granted_at=now,
            granted_by="admin",
            metadata={"reason": "test"},
        )
        
        data = perm.to_dict()
        
        assert data["user_id"] == "user123"  # nosec B101
        assert data["permission_scope"] == "messaging"  # nosec B101
        assert data["granted_at"] == now  # nosec B101
        assert data["granted_by"] == "admin"  # nosec B101
        assert data["metadata"] == {"reason": "test"}  # nosec B101
    
    def test_permission_from_dict(self):
        """Test creating permission from dictionary."""
        now = time.time()
        data = {
            "user_id": "user123",
            "permission_scope": "messaging",
            "granted_at": now,
            "granted_by": "admin",
            "expires_at": now + 3600,
            "metadata": {"reason": "test"},
        }
        
        perm = Permission.from_dict(data)
        
        assert perm.user_id == "user123"  # nosec B101
        assert perm.permission_scope == "messaging"  # nosec B101
        assert perm.granted_at == now  # nosec B101
        assert perm.granted_by == "admin"  # nosec B101
        assert perm.expires_at == now + 3600  # nosec B101
        assert perm.metadata == {"reason": "test"}  # nosec B101


class TestPermissionManager:
    """Tests for PermissionManager."""
    
    def test_manager_initialization(self):
        """Test permission manager initialization."""
        manager = PermissionManager()
        
        assert manager is not None  # nosec B101
    
    def test_manager_with_file_database(self, tmp_path):
        """Test permission manager with file database."""
        db_path = tmp_path / "permissions.db"
        manager = PermissionManager(db_path=str(db_path))
        
        assert manager is not None  # nosec B101
        assert db_path.exists()  # nosec B101
        
        manager.close()
    
    def test_grant_permission(self):
        """Test granting permission."""
        manager = PermissionManager()
        
        perm = manager.grant_permission(
            user_id="user123",
            permission_scope="messaging",
            granted_by="admin",
        )
        
        assert perm.user_id == "user123"  # nosec B101
        assert perm.permission_scope == "messaging"  # nosec B101
        assert perm.granted_by == "admin"  # nosec B101
    
    def test_grant_permission_with_expiration(self):
        """Test granting permission with expiration."""
        manager = PermissionManager()
        
        expires_at = time.time() + 3600
        perm = manager.grant_permission(
            user_id="user123",
            permission_scope="messaging",
            granted_by="admin",
            expires_at=expires_at,
        )
        
        assert perm.expires_at == expires_at  # nosec B101
    
    def test_grant_permission_with_metadata(self):
        """Test granting permission with metadata."""
        manager = PermissionManager()
        
        metadata = {"reason": "test", "approved_by": "manager"}
        perm = manager.grant_permission(
            user_id="user123",
            permission_scope="messaging",
            granted_by="admin",
            metadata=metadata,
        )
        
        assert perm.metadata == metadata  # nosec B101
    
    def test_check_permission_granted(self):
        """Test checking granted permission."""
        manager = PermissionManager()
        
        manager.grant_permission("user123", "messaging", "admin")
        
        assert manager.check_permission("user123", "messaging")  # nosec B101
    
    def test_check_permission_not_granted(self):
        """Test checking permission not granted."""
        manager = PermissionManager()
        
        assert not manager.check_permission("user123", "messaging")  # nosec B101
    
    def test_check_permission_different_scope(self):
        """Test checking different permission scope."""
        manager = PermissionManager()
        
        manager.grant_permission("user123", "messaging", "admin")
        
        assert not manager.check_permission("user123", "file_deletion")  # nosec B101
    
    def test_check_permission_expired(self):
        """Test checking expired permission."""
        manager = PermissionManager()
        
        # Grant permission that expires immediately
        manager.grant_permission(
            user_id="user123",
            permission_scope="messaging",
            granted_by="admin",
            expires_at=time.time() - 1,  # Already expired
        )
        
        assert not manager.check_permission("user123", "messaging")  # nosec B101
    
    def test_revoke_permission(self):
        """Test revoking permission."""
        manager = PermissionManager()
        
        manager.grant_permission("user123", "messaging", "admin")
        assert manager.check_permission("user123", "messaging")  # nosec B101
        
        revoked = manager.revoke_permission("user123", "messaging", "admin")
        
        assert revoked  # nosec B101
        assert not manager.check_permission("user123", "messaging")  # nosec B101
    
    def test_revoke_nonexistent_permission(self):
        """Test revoking permission that doesn't exist."""
        manager = PermissionManager()
        
        revoked = manager.revoke_permission("user123", "messaging", "admin")
        
        assert not revoked  # nosec B101
    
    def test_get_user_permissions_empty(self):
        """Test getting permissions for user with none."""
        manager = PermissionManager()
        
        perms = manager.get_user_permissions("user123")
        
        assert len(perms) == 0  # nosec B101
    
    def test_get_user_permissions_multiple(self):
        """Test getting multiple permissions for user."""
        manager = PermissionManager()
        
        manager.grant_permission("user123", "messaging", "admin")
        manager.grant_permission("user123", "file_deletion", "admin")
        manager.grant_permission("user123", "smart_home", "admin")
        
        perms = manager.get_user_permissions("user123")
        
        assert len(perms) == 3  # nosec B101
        scopes = {p.permission_scope for p in perms}
        assert scopes == {"messaging", "file_deletion", "smart_home"}  # nosec B101
    
    def test_get_user_permissions_filters_expired(self):
        """Test that get_user_permissions filters out expired permissions."""
        manager = PermissionManager()
        
        # Grant valid permission
        manager.grant_permission("user123", "messaging", "admin")
        
        # Grant expired permission
        manager.grant_permission(
            user_id="user123",
            permission_scope="file_deletion",
            granted_by="admin",
            expires_at=time.time() - 1,
        )
        
        perms = manager.get_user_permissions("user123")
        
        # Should only return the valid permission
        assert len(perms) == 1  # nosec B101
        assert perms[0].permission_scope == "messaging"  # nosec B101
    
    def test_request_permission(self):
        """Test requesting permission."""
        manager = PermissionManager()
        
        request = manager.request_permission(
            user_id="user123",
            permission_scope="messaging",
            reason="Need to send notifications",
        )
        
        assert request["user_id"] == "user123"  # nosec B101
        assert request["permission_scope"] == "messaging"  # nosec B101
        assert request["reason"] == "Need to send notifications"  # nosec B101
        assert request["status"] == "pending"  # nosec B101
        assert "request_id" in request  # nosec B101
    
    def test_cache_performance(self):
        """A cached check answers without reading the database.

        This test used to time two checks and require the second to take at
        most twice the first. grant_permission() already caches, so both
        were cache hits of a few microseconds and the comparison was noise:
        it failed on CI with 24 us against 2 x 5.8 us while the cache
        worked. Database reads are now counted instead of timed.
        """
        manager = PermissionManager()
        manager.grant_permission("user123", "messaging", "admin")
        manager.clear_cache()

        reads: list[str] = []
        assert manager._conn is not None  # nosec B101
        manager._conn.set_trace_callback(
            lambda sql: reads.append(sql) if sql.lstrip().upper().startswith("SELECT") else None
        )

        assert manager.check_permission("user123", "messaging") is True  # nosec B101
        assert len(reads) >= 1, "a check after clear_cache() must read the database"  # nosec B101

        reads.clear()
        assert manager.check_permission("user123", "messaging") is True  # nosec B101
        assert reads == [], "the second check must be answered from the cache"  # nosec B101
    
    def test_clear_cache_specific_user(self):
        """Test clearing cache for specific user."""
        manager = PermissionManager()
        
        manager.grant_permission("user1", "messaging", "admin")
        manager.grant_permission("user2", "messaging", "admin")
        
        # Populate cache
        manager.check_permission("user1", "messaging")
        manager.check_permission("user2", "messaging")
        
        # Clear cache for user1
        manager.clear_cache("user1")
        
        # Both should still work (user2 from cache, user1 from database)
        assert manager.check_permission("user1", "messaging")  # nosec B101
        assert manager.check_permission("user2", "messaging")  # nosec B101
    
    def test_clear_cache_all_users(self):
        """Test clearing cache for all users."""
        manager = PermissionManager()
        
        manager.grant_permission("user1", "messaging", "admin")
        manager.grant_permission("user2", "messaging", "admin")
        
        # Populate cache
        manager.check_permission("user1", "messaging")
        manager.check_permission("user2", "messaging")
        
        # Clear all cache
        manager.clear_cache()
        
        # Both should still work (from database)
        assert manager.check_permission("user1", "messaging")  # nosec B101
        assert manager.check_permission("user2", "messaging")  # nosec B101
    
    def test_audit_log_grant(self):
        """Test audit log for grant action."""
        manager = PermissionManager()
        
        manager.grant_permission("user123", "messaging", "admin")
        
        log = manager.get_audit_log(user_id="user123")
        
        assert len(log) > 0  # nosec B101
        assert log[0]["action"] == "grant"  # nosec B101
        assert log[0]["user_id"] == "user123"  # nosec B101
        assert log[0]["permission_scope"] == "messaging"  # nosec B101
    
    def test_audit_log_revoke(self):
        """Test audit log for revoke action."""
        manager = PermissionManager()
        
        manager.grant_permission("user123", "messaging", "admin")
        manager.revoke_permission("user123", "messaging", "admin", "No longer needed")
        
        log = manager.get_audit_log(user_id="user123")
        
        # Should have both grant and revoke
        assert len(log) >= 2  # nosec B101
        actions = [entry["action"] for entry in log]
        assert "grant" in actions  # nosec B101
        assert "revoke" in actions  # nosec B101
    
    def test_audit_log_request(self):
        """Test audit log for request action."""
        manager = PermissionManager()
        
        manager.request_permission("user123", "messaging", "Need access")
        
        log = manager.get_audit_log(user_id="user123")
        
        assert len(log) > 0  # nosec B101
        assert log[0]["action"] == "request"  # nosec B101
        assert log[0]["reason"] == "Need access"  # nosec B101
    
    def test_audit_log_limit(self):
        """Test audit log with limit."""
        manager = PermissionManager()
        
        # Create multiple audit entries
        for i in range(10):
            manager.grant_permission(f"user{i}", "messaging", "admin")
        
        log = manager.get_audit_log(limit=5)
        
        assert len(log) == 5  # nosec B101
    
    def test_audit_log_all_users(self):
        """Test audit log for all users."""
        manager = PermissionManager()
        
        manager.grant_permission("user1", "messaging", "admin")
        manager.grant_permission("user2", "file_deletion", "admin")
        
        log = manager.get_audit_log()
        
        assert len(log) >= 2  # nosec B101
        user_ids = {entry["user_id"] for entry in log}
        assert "user1" in user_ids  # nosec B101
        assert "user2" in user_ids  # nosec B101
    
    def test_permission_persistence(self, tmp_path):
        """Test that permissions persist across manager instances."""
        db_path = tmp_path / "permissions.db"
        
        # Create first manager and grant permission
        manager1 = PermissionManager(db_path=str(db_path))
        manager1.grant_permission("user123", "messaging", "admin")
        manager1.close()
        
        # Create second manager and check permission
        manager2 = PermissionManager(db_path=str(db_path))
        assert manager2.check_permission("user123", "messaging")  # nosec B101
        manager2.close()
    
    def test_replace_existing_permission(self):
        """Test replacing existing permission."""
        manager = PermissionManager()
        
        # Grant initial permission
        perm1 = manager.grant_permission("user123", "messaging", "admin")
        
        # Small delay to ensure different timestamp
        import time
        time.sleep(0.01)
        
        # Grant same permission again (should replace)
        perm2 = manager.grant_permission("user123", "messaging", "system")
        
        # Should have new granted_by
        assert perm2.granted_by == "system"  # nosec B101
        assert perm2.granted_at >= perm1.granted_at  # Use >= to handle fast execution  # nosec B101
        
        # Should still have permission
        assert manager.check_permission("user123", "messaging")  # nosec B101
    
    def test_manager_close(self):
        """Test closing manager."""
        manager = PermissionManager()
        
        manager.grant_permission("user123", "messaging", "admin")
        manager.close()

        assert manager._conn is None, "close() must release the connection"  # nosec B101
        manager.close()  # idempotent
        assert manager._conn is None  # nosec B101
