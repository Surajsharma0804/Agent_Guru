# Goal Manager Integrations

## Overview

The Goal Manager integrates with four core Agent_Guru components to provide complete autonomous goal execution. This document details each integration point, including API contracts, data flow, error handling, and usage examples.

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Goal Manager                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Goal Decomposer                              │ │
│  │  Uses: LLM Runtime, Memory System                     │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────