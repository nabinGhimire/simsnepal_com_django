# Centralized Identity & Communication Concept

This document outlines the core architecture of ChatHamro's centralized identity system.

## Overview
`hamro.com` acts as the central hub for identity and communication.

Instead of each product maintaining separate identities, users register once in Hamro and can then:

- use first-party experiences (`hamro.com`, Hamro mobile apps),
- authenticate in third-party/federated experiences (`business.hamro.com`, future partner apps),
- receive business and platform notifications in a unified conversation layer.

## Key Principles
1. **Single Identity**: One user, one account, multiple contexts.
2. **Cross-Platform**: Seamless communication between web, mobile, and third-party integrations.
3. **Privacy First**: Users control which businesses can contact them.
4. **Real-Time**: Low-latency communication via WebSockets.

## System Roles

- **System**: Hamro core APIs and identity authority.
- **Business**: Sends messages directly from its own profile.
- **Platform**: Sends on behalf of business after explicit approval.

## Ownership Model

- `business.hamro.com` is an internal management portal owned by Hamro.
- Portal creates/updates businesses through internal system endpoints.
- Changes are reflected in core Hamro data immediately via sync APIs.

---
*ChatHamro Architecture*
