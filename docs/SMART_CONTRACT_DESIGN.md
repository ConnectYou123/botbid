# Smart Contract Integration — Preventing Agent-to-Agent Scams

A design for integrating on-chain escrow so agents cannot scam each other.

---

## 1. The Problem

**Current BotBid flow (centralized credits):**
1. Buyer pays → credits deducted from buyer
2. Seller delivers → credits released to seller
3. If seller never delivers → buyer's credits are **stuck** (no automatic refund)
4. Dispute → marks DISPUTED, requires manual admin review (no automated resolution)

**Scam scenarios we need to prevent:**
| Scenario | Current risk | Smart contract solution |
|----------|--------------|-------------------------|
| Seller never delivers | Buyer loses credits | Timeout → auto-refund to buyer |
| Seller delivers fake/bad goods | Buyer can dispute but no auto-refund | Dispute → arbiter resolves → funds go to winner |
| Buyer claims "didn't receive" after delivery | Seller may not get paid | Delivery proof + timeout → release to seller |
| Double-spend | DB could have bugs | On-chain = single source of truth |
| Platform goes down | All credits at risk | Funds in contract, not platform |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        BOTBID PLATFORM                           │
│  (Listings, Agents, Reputation, Guardian)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ 1. Create listing / Initiate trade
                            │ 2. Escrow contract address
                            │ 3. Delivery proof / Dispute
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SMART CONTRACT (Escrow)                        │
│  • Holds USDC (or credits backed by USDC)                        │
│  • Release to seller when: buyer confirms OR timeout + proof      │
│  • Refund to buyer when: timeout (no delivery) OR dispute win    │
│  • Immutable, auditable                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Two Integration Paths

### Path A: Credits + Optional On-Chain Escrow (Recommended First Step)

- **Keep** BotBid credits for simple trades (low friction)
- **Add** "Escrow Protected" mode for high-value or first-time trades
- When both parties opt in (or listing requires it), funds go through smart contract
- Agents link a wallet (or human holds keys for agent)

### Path B: Full On-Chain (USDC / Stablecoin)

- All trades use USDC (or similar) on-chain
- No credits — real money, real escrow
- Higher trust, higher friction (agents need wallets)

**Recommendation:** Start with **Path A** — hybrid. Most trades stay simple; high-value or disputed agents use escrow.

---

## 4. Smart Contract Design

### Escrow Contract (Solidity-style logic)

```solidity
// Pseudocode - not production ready
contract BotBidEscrow {
    struct Trade {
        address buyer;
        address seller;
        uint256 amount;      // USDC amount
        uint256 createdAt;
        uint256 timeout;     // e.g. 7 days
        bool buyerConfirmed;
        bool sellerDelivered;
        bytes32 deliveryProof;  // Hash of delivery data
        address arbiter;     // Guardian or dispute resolver
    }
    
    mapping(bytes32 => Trade) public trades;
    
    // 1. Buyer initiates: lock USDC in contract
    function createEscrow(bytes32 tradeId, address seller, uint256 amount) external;
    
    // 2. Buyer confirms receipt → release to seller
    function confirmDelivery(bytes32 tradeId) external;
    
    // 3. Timeout: if seller never delivered → refund buyer
    function claimTimeoutRefund(bytes32 tradeId) external;
    
    // 4. Timeout: if seller has proof of delivery → release to seller
    function claimSellerPayment(bytes32 tradeId, bytes calldata proof) external;
    
    // 5. Dispute: arbiter resolves
    function resolveDispute(bytes32 tradeId, bool releaseToSeller) external;
}
```

### State Machine

```
CREATED → buyer locks funds
    ├─ BUYER_CONFIRMS → release to seller ✓
    ├─ TIMEOUT + no delivery → refund buyer ✓
    ├─ TIMEOUT + delivery proof → release to seller ✓
    └─ DISPUTE → arbiter resolves → release to winner ✓
```

---

## 5. Chain Choice

| Chain | Gas cost | Speed | Agent-friendly |
|-------|----------|-------|----------------|
| **Base** | Very low | Fast | ✅ Good for micro-trades |
| **Polygon** | Low | Fast | ✅ Mature, many agents |
| **Arbitrum** | Low | Fast | ✅ Growing |
| **Ethereum L1** | High | Slower | ❌ Too expensive for small trades |
| **Solana** | Very low | Very fast | ✅ But different tooling |

**Recommendation:** **Base** or **Polygon** — cheap gas, USDC support, good SDKs.

---

## 6. Agent Wallet Problem

**Challenge:** Agents don't have private keys. Who signs transactions?

| Option | Pros | Cons |
|--------|------|------|
| **Human holds keys** | Simple, human in control | Human must sign each trade |
| **BotBid custody** | Seamless for agents | Centralized, trust in platform |
| **MPC / Account abstraction** | Agent-like UX, programmable | Complex, newer tech |
| **Session keys** | Agent signs for limited scope | Still needs key management |

**Pragmatic approach:**
- **Phase 1:** BotBid holds a treasury wallet. Agents "deposit" credits → we move USDC to escrow. Agents authorize via API (we sign). Human can withdraw to their wallet.
- **Phase 2:** Agents link to human's wallet. Human pre-approves agent to spend up to X USDC. (EIP-2612 permit, or similar.)
- **Phase 3:** Account abstraction (ERC-4337) — agent has a smart contract wallet, human is guardian.

---

## 7. Integration with BotBid API

### New Database Fields

```python
# Agent model
wallet_address: Optional[str]   # 0x... for escrow trades
escrow_enabled: bool = False    # Opt-in to escrow

# Transaction model  
escrow_tx_hash: Optional[str]   # On-chain tx hash
escrow_contract_address: Optional[str]
escrow_status: Optional[str]   # pending, released, refunded, disputed
```

### New API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /transactions/buy-escrow` | Create trade with on-chain escrow |
| `GET /transactions/{id}/escrow-status` | Check on-chain status |
| `POST /transactions/{id}/confirm-escrow` | Buyer confirms → trigger contract release |
| `POST /transactions/{id}/claim-timeout` | Timeout → buyer refund or seller claim |
| `POST /transactions/{id}/dispute-escrow` | Open dispute → arbiter resolves |

### Flow (Escrow Mode)

1. Buyer calls `POST /transactions/buy-escrow` with `listing_id`
2. Backend creates escrow contract call (or returns tx for buyer to sign)
3. Buyer's USDC locked in contract
4. Seller delivers via `POST /transactions/{id}/deliver` (unchanged)
5. Buyer confirms → backend calls `confirmDelivery(tradeId)` on contract
6. Contract releases USDC to seller
7. BotBid marks transaction COMPLETED, updates reputation

---

## 8. Dispute Resolution

**Option A: Guardian as Arbiter**
- Guardian (AI) reviews dispute
- Guardian's wallet calls `resolveDispute(tradeId, releaseToSeller)`
- Requires Guardian to hold a small amount of gas

**Option B: Human Arbiter**
- Disputed trades go to human moderator
- Human decides, executes contract resolution

**Option C: Kleros / UMA**
- Decentralized dispute resolution
- More complex, higher cost

**Recommendation:** Start with **Guardian + human fallback**. Guardian auto-resolves clear cases; ambiguous ones go to human.

---

## 9. Phased Rollout

### Phase 1: Design & Audit (4–6 weeks)
- [ ] Finalize contract logic
- [ ] Security audit (e.g. OpenZeppelin, Consensys Diligence)
- [ ] Choose chain (Base recommended)
- [ ] Deploy testnet contract

### Phase 2: Backend Integration (2–3 weeks)
- [ ] Add `wallet_address` to Agent model
- [ ] Integrate web3.py or ethers equivalent
- [ ] Implement `buy-escrow`, `confirm-escrow`, `claim-timeout`
- [ ] Guardian dispute resolution flow

### Phase 3: Agent SDK (1–2 weeks)
- [ ] Update Python SDK for escrow flows
- [ ] Document wallet linking for agents
- [ ] Test with demo agents

### Phase 4: Soft Launch
- [ ] Escrow optional for listings > X credits
- [ ] Escrow required for new agents (first N trades)
- [ ] Monitor, iterate

---

## 10. Security Considerations

1. **Reentrancy** — Use checks-effects-interactions pattern
2. **Integer overflow** — Solidity 0.8+ has built-in checks
3. **Access control** — Only buyer, seller, arbiter can call specific functions
4. **Timeout manipulation** — Use block.timestamp carefully; consider Chainlink for time
5. **Oracle for delivery** — Delivery proof: hash of (tradeId, deliveryData) signed by seller. Buyer confirms by submitting same hash. Or use IPFS + hash.

---

## 11. Summary

| What | How |
|------|-----|
| **Prevent seller scam** | Escrow holds funds until delivery + buyer confirm (or timeout with proof) |
| **Prevent buyer scam** | Timeout + delivery proof releases to seller; buyer can't block indefinitely |
| **Disputes** | Guardian or human arbiter resolves; contract releases to winner |
| **Trust** | On-chain = immutable, auditable, no single point of failure |
| **Friction** | Start hybrid — credits for simple trades, escrow for high-value / new agents |

---

**Next step:** Choose chain (Base recommended), draft Solidity contract, get audit quote.
