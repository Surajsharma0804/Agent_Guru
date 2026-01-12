package com.guru.phoneagent.di

import android.content.Context
import com.guru.phoneagent.audit.AuditLogger
import com.guru.phoneagent.security.SecurityManager
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Dependency Injection Module for Security Components
 * 
 * Provides production-grade security and audit logging components
 * with proper lifecycle management and dependency resolution.
 */
@Module
@InstallIn(SingletonComponent::class)
object SecurityModule {
    
    @Provides
    @Singleton
    fun provideSecurityManager(
        @ApplicationContext context: Context
    ): SecurityManager {
        return SecurityManager(context)
    }
    
    @Provides
    @Singleton
    fun provideAuditLogger(
        @ApplicationContext context: Context,
        securityManager: SecurityManager
    ): AuditLogger {
        return AuditLogger(context, securityManager)
    }
}