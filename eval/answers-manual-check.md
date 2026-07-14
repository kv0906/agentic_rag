# Manual check report — agent answers vs gold

Cases: 25 | model: gpt-5.4-mini | playbook PDF

## q01 · overview · easy

**Q:** What does the MM bot do?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

The Market Maker (MM) bot automatically places and manages buy/sell orders around the mid price to provide liquidity and capture the spread. You configure parameters like position limit, step size, distance, and budget; the bot spreads orders across a grid, updates them as price shifts, and runs continuously without manual intervention.

**Agent:**

The MM bot is a **market-making tool** that **automatically places and manages buy/sell orders around the mid price** to **provide liquidity and capture the spread**. You set parameters like position limit, step size, distance, and budget, and it keeps updating orders continuously without manual intervention. [Chunk 2]

---

## q02 · terms · easy

**Q:** What is a binary market?

**Expected retrieve:** True · **Actual:** False · **Routing:** MISS retrieve

**Gold:**

A market with only two possible outcomes: YES or NO.

**Agent:**

A **binary market** usually means a market or market structure with only **two possible states or outcomes**.

Depending on the context, it can mean:

- **Binary options / trading:** a yes/no bet on whether an asset will be above or below a certain price at a certain time.
- **Economics / finance more broadly:** a market where an event has only two outcomes, such as **up/down**, **yes/no**, or **default/no default**.
- **Prediction markets:** contracts that pay out only if a specific condition happens, making the result effectively binary.

If you meant a specific finance term or a concept from a document, I can explain that version too.

---

## q03 · terms · easy

**Q:** What is the spread?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

The gap between the best buy price and the best sell price.

**Agent:**

The **spread** is the **price gap between the best bid and best ask** in the order book; in this playbook, the bot aims to **capture the spread** by placing buy/sell orders around the mid price (Chunk 3).

---

## q04 · terms · easy

**Q:** What does MM User mean?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

The market-maker user account that owns a given market on the platform.

**Agent:**

“MM User” means a **Market Maker user**—an operator/account that uses an assigned trading wallet to place and manage trades on the platform. The playbook says MM users are assigned accounts in Wallet Management, and each MM user can only work with the accounts assigned to them. [Chunk 2, Chunk 5]

---

## q05 · navigation · medium

**Q:** What is the left-hand main navigation menu used for, and what are the main items?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

It is the map of the platform workspaces: Live Markets, Positions / Open Orders, Wallet Management, Reports, and Accounts.

**Agent:**

The left-hand main navigation menu is used to access the platform’s main workspaces. It acts as a map of the platform, with each item opening a different section of work. The main items are: **Live Markets**, **Positions / Open Orders**, **Wallet Management**, **Reports**, and **Accounts**. [Chunk 1]

---

## q06 · live_markets · medium

**Q:** Which market statuses appear on the Live Markets page?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Only markets that are Live or Approved appear on the Live Markets page. Proposed or rejected markets are not shown.

**Agent:**

The Live Markets page shows these market status filters: **All**, **Active**, and **Inactive**. It also says the page lists each market’s **current status**. [Chunk 3]

---

## q07 · live_markets · medium

**Q:** When should I use Merge Shares on a market?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Merge Shares combines matched YES + NO shares back into their underlying balance. Use it as a position-management action to settle complementary shares an account holds.

**Agent:**

Use **Merge Shares** when you have **matched YES and NO shares in the same market** and want to **combine them back into the underlying balance**. It’s a **position-management** action used to settle complementary shares you hold, not to place trades. [Chunk 1]

---

## q08 · positions · medium

**Q:** What does P&L mean on All Positions, and how is it colored?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

P&L is Profit and Loss — the unrealized profit or loss on your position using the latest market price. It shows in green when a position is up and red when it is down.

**Agent:**

On **All Positions**, **P&L** means **profit/loss**. It is colored **green when a position is up** and **red when it is down**. [Chunk 1]

---

## q09 · wallet · hard

**Q:** What characters are allowed in a new wallet name?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Wallet Name is required and supports alphanumeric characters and underscores only.

**Agent:**

A new wallet name supports **alphanumeric characters and underscores only**. (Chunk 1)

---

## q10 · wallet · hard

**Q:** If an MM user cannot see or trade on an account, where should I check first?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Check MM Assignments under Wallet Management. The MM user likely has not been assigned to that account yet.

**Agent:**

Check **Wallet Management → MM Assignments** first. That screen determines which trading accounts each MM user can access, so if they can’t see or trade on an account, it’s usually an assignment issue. [Chunk 1, Chunk 2, Chunk 4]

---

## q11 · reports · medium

**Q:** What are the four Reports sub-sections and when do I use each?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Dashboard (big-picture overview of volume, PnL, balances), Tx Log (per-order and money in/out), Markets (performance per market), and MM (performance per MM account). Start with Dashboard, then drill into the others.

**Agent:**

The **four Reports sub-sections** are:

1. **Dashboard** — use this for a **top-level overall summary** of performance across all MM accounts and markets.  
2. **Transaction Log (Tx Log)** — use this to see a **per-order record** of matched orders and related money movements.  
3. **Market Reports** — use this to view performance **broken down by market**.  
4. **MM Reports** — use this to view performance **broken down by Market Maker user / wallet**.  

Source: Reports overview and sub-section breakdown in the playbook ([Chunk 1], [Chunk 3], [Chunk 6], [Chunk 8]).

---

## q12 · reports · hard

**Q:** How is PnL calculated on the MM Report?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

PnL (USD) is net realized trading profit or loss, calculated as Redeem − Order Filled.

**Agent:**

PnL on the MM Report is calculated as **net realized trading profit or loss**. Specifically, the playbook defines it as:

**PnL (USD) = Redeem + Merge − Order Filled**  
or equivalently, in the account report: **PnL = Redeem − Order Filled** when referring to redeemed amount versus executed trade notional.  
Citations: chunk 3 (page 28), chunk 2 (page 24).



---

## q13 · strategy · easy

**Q:** What is Initial Seeding used for?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Initial Seeding creates the first buy/sell (YES/NO) orders in the order book and establishes an initial price level (mid price) for the market.

**Agent:**

Initial Seeding is used to create the first YES/NO buy-sell orders in the order book and establish the market’s initial mid price. It’s the starting step for seeding a market before keeping the book liquid with other strategies like Auto Refresh. [Chunk 2, Chunk 1]

---

## q14 · strategy · medium

**Q:** What is the valid range for Mid Price in cents?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Mid Price is in cents with a valid range of 1–99. Orders are placed symmetrically above and below this price.

**Agent:**

The valid range for **Mid Price** is **1–99 cents**. [Chunk 1](source=Huua-MMBot-Playbook%20Final.pdf%20|%20page=34), [Chunk 2](source=Huua-MMBot-Playbook%20Final.pdf%20|%20page=32)

---

## q15 · strategy · hard

**Q:** What are the recommended Auto Refresh Group 1 settings?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Group 1 (core liquidity): Position limit Admin YES $10 / NO $10, Presale YES $5 / NO $5; Distance 2; Step size 2–3; Number of orders 7–10; Budget $10 per side; Refresh time 1. Use Auto Refresh before the market goes LIVE.

**Agent:**

Recommended **Auto Refresh Group 1 (core liquidity)** settings are:

- **Position limit:** Admin **$10 / $10**; Presale **$5 / $5**
- **Distance:** **2**
- **Step size:** **2–3**
- **Number of orders:** **7–10**
- **Budget:** **$10 per side**
- **Refresh time:** **1 minute**  
- Run it **before the market goes live**.  

Source: Huua-MMBot-Playbook Final.pdf, p. 33 and quick reference on p. 46.

---

## q16 · strategy · hard

**Q:** What are recommended Auto Refresh Group 2 unmatched-order settings?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Group 2 sits further from mid: Distance 25–30, Step size 2, Number of orders 10, Budget $70–$100, Refresh time 3. Group 2 distance must always be higher than Group 1.

**Agent:**

Recommended **Auto Refresh Group 2 (unmatched orders)** settings are:

- **Distance:** 25–30¢
- **Step size:** 2
- **Number of orders:** 10
- **Budget:** $70–$100
- **Refresh time:** 3 minutes

Group 2 should sit farther from the mid price to catch larger moves, and its distance must be higher than Group 1. [Chunk 1][Chunk 3]

---

## q17 · strategy · easy

**Q:** What is the maximum number of orders per group?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Number of Orders is the total orders placed in the group, with a maximum of 50. This is also listed under universal rules on the cheat-sheet.

**Agent:**

The maximum number of orders per group is **50**. The quick reference says: **“Max 50 orders/group”** (Chunk 4, page 46).

---

## q18 · strategy · hard

**Q:** How does Volume Boost (Simple) work?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

It generates volume using account pairs: one wallet creates positions and the other burns them, producing matched trades. Use an even number of wallets and run it before the market goes LIVE. One cycle is create → burn → done; cycles repeat until the volume target is met. Recommended quantity $5–$10, refresh 1 min, target volume $40–$50.

**Agent:**

Volume Boost (Simple) generates volume by using **matched account pairs**: one wallet creates positions and the other burns them, so each cycle is a **create → burn → done** loop with no account looping. It picks a **random wallet pair** each cycle, adds small **jitter** to look less robotic, then waits **5–60 seconds** before the next cycle. It keeps repeating until the **target volume** is reached or you stop it. Use an **even number of wallets** and run it **before the market goes live**.  
Sources: Chunk 1, Chunk 2.

---

## q19 · strategy · hard

**Q:** What are the default Dynamic Budget Zones?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Stop 0¢–20¢ uses 0% budget (no new orders). Safe 20¢–80¢ uses 100% of available budget. Stop 80¢–100¢ uses 0%. Turn on Dynamic Budget in Auto Refresh. It only controls new orders on refresh.

**Agent:**

The default Dynamic Budget Zones are:

- **0¢–20¢:** Stop (**0%** budget)
- **20¢–80¢:** Safe (**100%** budget)
- **80¢–100¢:** Stop (**0%** budget)

[Source: Chunk 2; also summarized in Chunk 3]

---

## q20 · strategy · hard

**Q:** When should I use Sport Odds every 5 minutes vs every 1–2 hours?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Every 5 minutes is for very fast-moving live markets (highest cost, super responsive). Every 1–2 hours is before the match / low movement (lowest cost, slow). More frequent refresh means more Draw API calls and higher SGO cost. Sport Odds is only for admin-created sport markets.

**Agent:**

Use **every 5 minutes** only for **very fast-moving live sport markets** where odds change quickly and you need the bot to stay highly responsive. It has the **highest cost** and is the **most responsive** option. [Chunk 1]

Use **every 1–2 hours** for **quiet / low-movement markets**, especially **before match** or when **cost control matters most**. It has the **lowest cost** but is slower to react. [Chunk 1]

In short:
- **5 min** = fast live action, max responsiveness
- **1–2 hours** = quiet markets, minimize cost

The playbook also summarizes this as: **Quiet → 1–2h, Normal → 30m, Active → 15m, Fast live → 5m**. [Chunk 3]

---

## q21 · strategy · hard

**Q:** In Budget % mode with multiple groups, what is the rule for the sum of percentages?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

The sum of all % values across groups must not exceed 100%, because each group's budget is % × Position Limit and Position Limit is a shared risk cap.

**Agent:**

In **Budget (%) mode with multiple groups**, the **sum of all group percentages must not exceed 100%** of the shared Position Limit. If it did, the combined budgets could exceed the actual Position Limit. (Chunk 1, Chunk 2)

---

## q22 · workflow · medium

**Q:** What is the recommended order to start running the bot according to the playbook closing advice?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

Start with Initial Seeding to establish a mid price, then keep the book liquid with Auto Refresh. Watch positions and PnL in Reports, and use the cheat-sheet for defaults. When in doubt, use read-only actions (View Market, Monitor) before making changes.

**Agent:**

According to the closing advice, **start with Initial Seeding first** to establish a mid price, **then keep the book liquid with Auto Refresh**. It also suggests watching positions and PnL in Reports, and using read-only actions like View Market or Monitor if unsure. (Chunk 3)

---

## q23 · routing · easy

**Q:** hello

**Expected retrieve:** False · **Actual:** False · **Routing:** OK

**Gold:**

A short greeting reply is fine; no document retrieval is required.

**Agent:**

Hello! How can I help you today?

---

## q24 · routing · easy

**Q:** What is the weather in Singapore today?

**Expected retrieve:** False · **Actual:** False · **Routing:** OK

**Gold:**

Not in the playbook; the assistant should not invent platform content. Prefer saying it does not know or that this is outside the document.

**Agent:**

I can help with questions about uploaded PDFs, but I don’t have live weather access here.

If you want, I can:
- help you find weather info in a document you uploaded, or
- suggest the fastest way to check Singapore’s current weather.

---

## q25 · negative · hard

**Q:** What is the API rate limit for the public REST endpoint rate-limit header X-RateLimit-Remaining?

**Expected retrieve:** True · **Actual:** True · **Routing:** OK

**Gold:**

This is not specified in the MMBot External User Playbook. A correct system should say it does not know or that the document does not cover this.

**Agent:**

I couldn’t find any document content about a public REST API or the `X-RateLimit-Remaining` header in the uploaded PDF. The retrieved passages appear to be about MMBot strategy settings, not API rate limits.

If you meant a different document, please upload it or point me to the relevant PDF/page.

---
