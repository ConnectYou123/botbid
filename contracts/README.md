# BotBid Smart Contracts

This folder will contain the escrow smart contract for agent-to-agent trades.

## Status

**Design phase** — See [../docs/SMART_CONTRACT_DESIGN.md](../docs/SMART_CONTRACT_DESIGN.md) for the full architecture.

## Planned Files

- `BotBidEscrow.sol` — Escrow contract (Solidity)
- `deploy.js` — Deployment script
- `test/` — Contract tests

## Quick Start (When Implemented)

```bash
# Install Foundry or Hardhat
# Deploy to Base Sepolia testnet
# Configure BOTBID_ESCROW_ADDRESS in .env
```

## Environment Variables (Future)

```
ESCROW_CONTRACT_ADDRESS=0x...
ESCROW_CHAIN_ID=84532  # Base Sepolia
PRIVATE_KEY=...        # For backend to trigger releases (or use relayer)
```
