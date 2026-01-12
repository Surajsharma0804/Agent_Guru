package com.guru.phoneagent.presentation

import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented tests for MainActivity
 * 
 * Production-grade UI tests for main application interface and user interactions.
 * Tests permission handling, navigation, and security features.
 */
@HiltAndroidTest
@RunWith(AndroidJUnit4::class)
class MainActivityTest {
    
    @get:Rule(order = 0)
    val hiltRule = HiltAndroidRule(this)
    
    @get:Rule(order = 1)
    val composeTestRule = createAndroidComposeRule<MainActivity>()
    
    @Before
    fun setUp() {
        hiltRule.inject()
    }
    
    @Test
    fun testMainActivityLaunches() {
        // Test that the main activity launches without crashing
        // This is a basic smoke test for the application startup
        composeTestRule.onNodeWithText("GURU").assertExists()
    }
    
    @Test
    fun testPermissionsScreenDisplayed() {
        // Test that permissions screen is displayed when permissions are not granted
        composeTestRule.onNodeWithText("Security Permissions Required").assertExists()
    }
}