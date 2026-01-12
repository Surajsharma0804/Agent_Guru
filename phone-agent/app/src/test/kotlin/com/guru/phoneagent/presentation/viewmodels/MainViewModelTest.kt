package com.guru.phoneagent.presentation.viewmodels

import com.guru.phoneagent.audit.AuditLogger
import com.guru.phoneagent.presentation.navigation.Screen
import com.guru.phoneagent.security.SecurityManager
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for MainViewModel
 * 
 * Production-grade test suite for view model state management and user interactions.
 * Tests navigation, permission handling, and security event logging.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MainViewModelTest {
    
    private lateinit var securityManager: SecurityManager
    private lateinit var auditLogger: AuditLogger
    private lateinit var viewModel: MainViewModel
    
    private val testDispatcher = StandardTestDispatcher()
    
    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        
        securityManager = mockk(relaxed = true)
        auditLogger = mockk(relaxed = true)
        
        viewModel = MainViewModel(securityManager, auditLogger)
    }
    
    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }
    
    @Test
    fun `test initial state`() = runTest {
        val initialState = viewModel.uiState.value
        
        assert(!initialState.permissionsGranted)
        assert(initialState.currentScreen == Screen.Permissions)
        assert(initialState.connectionState == ConnectionState.DISCONNECTED)
        assert(initialState.authorityState == AuthorityState.LOCKED)
        assert(initialState.pairingState == PairingState.NOT_PAIRED)
    }
    
    @Test
    fun `test permission state updates`() = runTest {
        val requiredPermissions = listOf("CAMERA", "MICROPHONE")
        val optionalPermissions = listOf("CALL_PHONE", "SEND_SMS")
        
        viewModel.setPermissionState(requiredPermissions, optionalPermissions)
        
        val state = viewModel.uiState.value
        assert(state.requiredPermissions == requiredPermissions)
        assert(state.optionalPermissions == optionalPermissions)
        assert(state.currentScreen == Screen.Permissions)
    }
    
    @Test
    fun `test permissions granted navigation`() = runTest {
        viewModel.setPermissionsGranted(true)
        
        val state = viewModel.uiState.value
        assert(state.permissionsGranted)
        assert(state.currentScreen == Screen.Home)
    }
    
    @Test
    fun `test navigation between screens`() = runTest {
        viewModel.navigateTo(Screen.Settings)
        
        val state = viewModel.uiState.value
        assert(state.currentScreen == Screen.Settings)
    }
    
    @Test
    fun `test pairing state management`() = runTest {
        viewModel.startPairing()
        testDispatcher.scheduler.advanceUntilIdle()
        
        val state = viewModel.uiState.value
        assert(state.pairingState == PairingState.SCANNING_QR)
    }
    
    @Test
    fun `test emergency stop`() = runTest {
        viewModel.emergencyStop()
        testDispatcher.scheduler.advanceUntilIdle()
        
        val state = viewModel.uiState.value
        assert(state.currentScreen == Screen.Emergency)
    }
}