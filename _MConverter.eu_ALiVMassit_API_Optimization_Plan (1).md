**ALiVMassit**

API Flow Optimization Plan

Complete Technical Instruction Manual

|              |                           |
|--------------|---------------------------|
| **Version**  | 1.0 --- May 2026          |
| **Platform** | FastAPI + Python 3.11     |
| **Scope**    | Auth → AI → Agents → Exec |

**1. Executive Summary**

|                                                               |
|---------------------------------------------------------------|
| **System Baseline State --- 5 Optimization Zones Identified** |

ALiVMassit is a FastAPI-based enterprise trading platform with multi-agent AI orchestration. After full source analysis, this plan identifies 5 critical optimization zones across the end-to-end API flow. Each zone has concrete, file-specific instructions with before/after code patterns and measurable KPIs.

| **Component / Flow**     | **Current Implementation**                         | **Optimization Status** |
|--------------------------|----------------------------------------------------|-------------------------|
| **Auth & Rate Limiting** | JWT + IP-based rate limit per endpoint             | **⚠ Needs work**        |
| **LLM Task Routing**     | TaskModelSelector + 8-tier model registry          | **✅ Good**             |
| **Agent Pipeline**       | Sequential: Scanner→Strategy→Score→Risk            | **⚠ Needs work**        |
| **Exchange Caching**     | ThreeTierCache L1/L2/L3 + RequestCoalescer         | **✅ Good**             |
| **DB / Storage**         | SQLite + Alembic (PostgreSQL-ready)                | **⚠ Needs work**        |
| **Worker Queues**        | Dramatiq + Redis (4 queues)                        | **❌ Critical**         |
| **GO/NO-GO Gate**        | PF≥1.2, net_pnl\>0, ≥30 trades --- currently NO_GO | **❌ Critical**         |

**2. Zone A --- Authentication & Rate Limiting**

|                                                |
|------------------------------------------------|
| **File: app/api/auth.py · app/api/trading.py** |

**2.1 Current Behaviour**

Two separate secret mechanisms run in parallel: JWT Bearer tokens for user auth (/auth/login, /auth/register) and a plain TRADING_API_SECRET string checked per-request inside enforce_trading_rate_limit(). The rate limiter is IP-based and per-minute only, with no burst protection or sliding window. If TRADING_API_SECRET is unset, only loopback IPs are allowed --- a safe fallback but not production-grade.

**2.2 Problems Found**

- enforce_trading_rate_limit() is called synchronously inside the endpoint, blocking the event loop under load.

- Rate limit is per_minute only. No burst window means 60 rapid requests in second 1 all pass, then the next 59 seconds are blocked.

- No token refresh invalidation cache --- revoked JWTs remain valid until expiry.

- TRADING_API_SECRET compared with plain string equality (no constant-time compare), vulnerable to timing attack.

**2.3 Optimization Instructions**

**Step A1 --- Constant-Time Secret Compare**

In app/api/trading.py, replace the plain equality check with hmac.compare_digest:

> \# BEFORE
>
> if auth != f\"Bearer {secret}\":
>
> \# AFTER
>
> import hmac
>
> expected = f\"Bearer {secret}\".encode()
>
> if not hmac.compare_digest(auth.encode(), expected):

**Step A2 --- Sliding-Window Rate Limiter with Burst Cap**

Replace the per-minute counter with a Redis sliding-window (token bucket). In app/api/trading.py, replace enforce_trading_rate_limit():

> \# app/infra/rate_limit.py (new file)
>
> import time, redis.asyncio as redis
>
> async def sliding_window_ok(r, key, limit, window_s, burst):
>
> now = time.time()
>
> pipe = r.pipeline()
>
> pipe.zremrangebyscore(key, 0, now - window_s)
>
> pipe.zcard(key)
>
> pipe.zadd(key, {str(now): now})
>
> pipe.expire(key, window_s + 1)
>
> \_, count, \*\_ = await pipe.execute()
>
> return count \< limit

**Step A3 --- JWT Deny-List for Revocation**

In app/security/auth.py, add a Redis deny-list check on every request. Store revoked JTIs (JWT IDs) with TTL equal to remaining token validity:

> async def is_token_revoked(jti: str) -\> bool:
>
> return await redis.exists(f\"revoked:{jti}\")
>
> \# On logout:
>
> await redis.setex(f\"revoked:{jti}\", token_ttl_remaining, \"1\")

**2.4 Expected Impact**

| **Metric**            | **Before**                 | **After**                   |
|-----------------------|----------------------------|-----------------------------|
| Timing attack surface | Vulnerable (string eq)     | Eliminated (HMAC)           |
| Burst abuse window    | 60 req/min allowed in 1s   | \<5 burst, 20/min sustained |
| Revoked token risk    | Valid until expiry (\~1hr) | Blocked immediately         |

**3. Zone B --- LLM Task Routing & Cost Control**

|                                                                                                |
|------------------------------------------------------------------------------------------------|
| **Files: app/llm/model_optimizer.py · app/llm/optimized_router.py · app/api/llm_optimized.py** |

**3.1 Current Architecture (Strengths)**

The existing LLM routing is architecturally sound. The 8-tier ModelRegistry with Gemini Flash Free (70% of tasks) → GPT-4o-mini (20%) → Claude Sonnet (10%) correctly follows cost-optimisation principles. TaskModelSelector gates deterministic tasks (no LLM call), saving 100% of cost for those paths. OptimizedModelRouter performs agent-aware budget downgrade at runtime.

**3.2 Problems Found**

- OptimizerBridgeClient wraps every LLM call in a separate HTTP session. No connection pooling → cold TCP on every call adds 80--200 ms.

- The message length cap (max_input_chars) truncates silently. Truncated market data produces inconsistent outputs with no warning logged.

- There is no response cache for deterministic, time-bounded tasks (e.g., news_summary with same headline). Identical calls re-pay LLM costs.

- SpendTracker stores cost data only in-memory. Restart resets the daily budget counter --- budget guard can be bypassed by restarting the process.

**3.3 Optimization Instructions**

**Step B1 --- Persistent HTTP Session with Connection Pooling**

In app/llm/provider.py (OpenAIChatProvider), replace per-call httpx.AsyncClient with a shared session:

> \# In \_\_init\_\_:
>
> import httpx
>
> self.\_session = httpx.AsyncClient(
>
> base_url=\"https://openrouter.ai\",
>
> limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
>
> timeout=httpx.Timeout(30.0),
>
> )
>
> \# Register teardown in FastAPI lifespan:
>
> await provider.\_session.aclose()

**Step B2 --- Log & Alert on Truncation**

In app/api/llm_optimized.py, \_clamp_message() should emit a warning metric when truncation occurs:

> def \_clamp_message(msg: str) -\> str:
>
> cap = settings.max_input_chars
>
> if len(msg) \> cap:
>
> logger.warning(\"LLM input truncated: %d → %d chars\", len(msg), cap)
>
> usage_tracker.increment(\'llm.truncations\')
>
> return msg\[:cap\]
>
> return msg

**Step B3 --- Response Cache for Stable Tasks**

Wrap news_summary and market_summary calls in ThreeTierCache (already present in app/cache/three_tier_cache.py). TTL = 5 minutes for market data, 15 minutes for news:

> cache_key = f\'llm:{body.task_name}:{hashlib.md5(message.encode()).hexdigest()}\'
>
> cached = await cache.get(cache_key)
>
> if cached: return cached
>
> result = await \_call_llm(\...)
>
> ttl = 300 if \'market\' in body.task_name else 900
>
> await cache.set(cache_key, result, ttl=ttl)

**Step B4 --- Persist SpendTracker to Redis**

In app/llm/spend_tracker.py, add Redis flush on every increment and load on startup so daily budget survives restarts:

> async def log(self, cost: float):
>
> self.\_today_usd += cost
>
> await redis.incrbyfloat(\"spend:today\", cost) \# atomic
>
> async def load_from_redis(self):
>
> val = await redis.get(\"spend:today\")
>
> self.\_today_usd = float(val or 0)

**3.4 Model Routing Decision Table (Reference)**

| **Task Type**                 | **Assigned Tier**  | **Model**            | **Cost/1K** |
|-------------------------------|--------------------|----------------------|-------------|
| market_scan, classification   | ULTRA_CHEAP / FAST | Gemini Flash Free    | \$0.0001    |
| news_summary, reporting       | BUDGET             | Minimax M2           | \$0.0002    |
| sentiment, technical_analysis | DEFAULT / BALANCED | GPT-4o-mini          | \$0.0004    |
| strategy_decision, risk       | ANALYSIS           | Claude 3.5 Sonnet    | \$0.008     |
| heavy_reasoning (critical)    | PREMIUM / HEAVY    | Claude 3.7 / O3-mini | \$0.015     |

**4. Zone C --- Agent Pipeline Concurrency**

|                                                                               |
|-------------------------------------------------------------------------------|
| **Files: app/ai/orchestrator.py · app/agents/ · orchestrator/coordinator.py** |

**4.1 Current Pipeline Flow**

The pipeline is strictly sequential: MarketScannerAgent → StrategySelector → AIScoreFilter → RiskManager → ExecutionGateway → PerformanceTracker → LearningFeedback. This means the AI Orchestrator (Regime, Ranker, Ensemble) and the StrategySelector run one after another even when they could run in parallel.

**4.2 Problems Found**

- AIIntelligenceWrapper uses lazy initialization (\_lazy_init). On the first bot cycle, module loading can take 2--5 seconds --- blocking the entire cycle.

- MockExchangeService is used in production paths when the real exchange service fails to inject. This produces random OHLCV data silently corrupting regime detection.

- PerformanceTracker re-reads all closed trades from the DB on every cycle (\_trades list rebuilt). With 170+ closed trades this is O(N) per cycle.

- Learning feedback (learning_params.json) is loaded from disk on every LearningFeedback.run() --- pure disk I/O on the hot path.

- There is no circuit-breaker around the agent pipeline. A single agent failure causes the full cycle to fail silently (coordinator.paused stays False).

**4.3 Optimization Instructions**

**Step C1 --- Eager Initialization at Startup**

Move AIIntelligenceWrapper.\_lazy_init() to the FastAPI lifespan event, not first-call. In main app startup (apps/main.py or equivalent):

> @asynccontextmanager
>
> async def lifespan(app: FastAPI):
>
> await ai_wrapper.initialize_async(exchange_service=real_exchange)
>
> yield
>
> await ai_wrapper.shutdown()

**Step C2 --- Parallel Agent Stages with asyncio.gather()**

In orchestrator.py run_cycle(), the regime detection and strategy selection are independent. Run them concurrently:

> \# BEFORE (sequential)
>
> regime = await orchestrator.detect_regime(scan)
>
> strategy = await selector.select(scan)
>
> \# AFTER (parallel --- saves \~200--400ms per cycle)
>
> regime, strategy = await asyncio.gather(
>
> orchestrator.detect_regime(scan),
>
> selector.select(scan),
>
> )

**Step C3 --- Cache Learning Params In-Memory**

In app/learning/self_learning.py, load learning_params.json once at startup and watch for file changes rather than reading on every cycle:

> \_params_cache: dict = {}
>
> \_params_mtime: float = 0.0
>
> def load_parameters() -\> dict:
>
> global \_params_cache, \_params_mtime
>
> mtime = Path(PARAMS_PATH).stat().st_mtime
>
> if mtime != \_params_mtime:
>
> \_params_cache = json.loads(Path(PARAMS_PATH).read_text())
>
> \_params_mtime = mtime
>
> return \_params_cache

**Step C4 --- Circuit Breaker around Agent Pipeline**

Add a lightweight circuit breaker in orchestrator/coordinator.py. After 3 consecutive cycle failures, pause the coordinator and send a Telegram alert:

> self.\_consecutive_failures = 0
>
> FAILURE_THRESHOLD = 3
>
> try:
>
> result = await self.run_cycle()
>
> self.\_consecutive_failures = 0
>
> except Exception as e:
>
> self.\_consecutive_failures += 1
>
> if self.\_consecutive_failures \>= FAILURE_THRESHOLD:
>
> self.pause(reason=f\"Circuit breaker: {e}\")
>
> await telegram.send(f\'🚨 Bot paused after {FAILURE_THRESHOLD} failures: {e}\')

**Step C5 --- Replace MockExchangeService Injection**

In app/ai/integration_wrapper.py, the \_create_mock_exchange_service() must never run in production. Add an environment check and raise on startup if real exchange is missing:

> def \_lazy_init(self, exchange_service=None):
>
> if exchange_service is None:
>
> if os.getenv(\"ENVIRONMENT\") == \"production\":
>
> raise RuntimeError(\"Real exchange service required in production\")
>
> exchange_service = self.\_create_mock_exchange_service()
>
> logger.warning(\'⚠ Using MockExchangeService --- only valid in testing\')

**5. Zone D --- Exchange Data & Caching Layer**

|                                                                                               |
|-----------------------------------------------------------------------------------------------|
| **Files: app/exchange/aggregator.py · app/cache/three_tier_cache.py · app/exchange/retry.py** |

**5.1 Current Strengths to Preserve**

- RequestCoalescer correctly prevents N simultaneous identical requests from hitting the exchange. This is production-grade behaviour --- keep it.

- ThreeTierCache (L1 memory / L2 Redis / L3 disk) fallback chain is architecturally sound and already deployed.

- RetryConfig with exponential backoff + ±25% jitter is correctly implemented in app/exchange/retry.py. RATE_LIMIT_RETRY (5 s initial, 30 s max) is appropriate for exchange 429s.

**5.2 Problems Found**

- WebSocket manager (app/exchange/websocket_manager.py, 42 KB) has reconnection logic but no heartbeat health-check. If a WebSocket silently stalls, cached data becomes stale while appearing fresh.

- Cache TTLs are configured at 2--10 seconds. For OHLCV on 4h timeframe, 10 s is appropriate, but positions TTL of 2 s causes Redis hammering during a high-frequency cycle (30+ trades/day).

- DashboardAggregationService.\_latency_stats grows unbounded --- it appends every latency reading to a list with no max-length cap.

- L3 (disk) cache uses Python pickle. Pickle is not safe against corrupted cache files and can silently produce wrong data.

**5.3 Optimization Instructions**

**Step D1 --- WebSocket Heartbeat Check**

In app/exchange/enhanced_websocket.py, add a periodic PING and mark connection as stale if no PONG is received within 10 s:

> async def \_heartbeat_loop(self):
>
> while not self.\_stopped:
>
> await asyncio.sleep(30)
>
> try:
>
> await self.\_ws.ping()
>
> self.\_last_pong = time.time()
>
> except Exception:
>
> await self.\_reconnect()

**Step D2 --- Adaptive Cache TTLs by Market Volatility**

In app/exchange/aggregator.py, expose a set_ttl() method and have the PerformanceTracker update TTLs based on the current market scenario tag (Low-vol / Normal / High-vol):

> SCENARIO_TTL = {
>
> \"Low-vol\": {\"positions\": 5, \"orders\": 8, \"trades\": 30},
>
> \"Normal\": {\"positions\": 2, \"orders\": 3, \"trades\": 10},
>
> \"High-vol\": {\"positions\": 1, \"orders\": 2, \"trades\": 5},
>
> }
>
> aggregator.\_cache_ttls = SCENARIO_TTL\[scenario\]

**Step D3 --- Cap Latency Stats List**

In DashboardAggregationService.\_\_init\_\_(), replace plain lists with deques with a max length:

> from collections import deque
>
> self.\_latency_stats = {
>
> \"binance\": deque(maxlen=1000),
>
> \"mexc\": deque(maxlen=1000),
>
> }

**Step D4 --- Replace Pickle with JSON in L3 Cache**

In app/cache/three_tier_cache.py, replace pickle serialization with orjson (faster than stdlib json) for disk cache. This prevents pickle-deserialization corruption attacks and makes cache files human-readable:

> import orjson \# pip install orjson
>
> \# Write: Path(cache_file).write_bytes(orjson.dumps(value))
>
> \# Read: orjson.loads(Path(cache_file).read_bytes())

**6. Zone E --- Database, Workers & GO/NO-GO Gate**

|                                                                                                       |
|-------------------------------------------------------------------------------------------------------|
| **Files: app/storage/ · workers/ · app/api/workers.py · app/ai/orchestrator.py (PerformanceTracker)** |

**6.1 Database --- Critical Issues**

- SQLite is used in production on a VPS. Under concurrent worker writes (scanner + execution + reporting simultaneously), SQLite\'s writer lock causes SQLITE_BUSY errors. Migration to PostgreSQL is already scaffolded (DATABASE_URL env var) --- activate it.

- No DB connection pool --- every request opens a new connection via sqlite3.connect(). Connection overhead is \~1 ms per request, which compounds significantly at 30+ trades/day.

- No query-level timeout. A runaway analytics query (app/analytics/engine.py --- 23 KB) can block all DB writes indefinitely.

**6.2 Step E1 --- Activate PostgreSQL**

Set in .env to enable the already-built PostgreSQL path:

> DATABASE_URL=postgresql+asyncpg://vmassit:password@localhost:5432/vmassit_db
>
> \# In app/storage/db.py, the connect() function already selects PG when DATABASE_URL is set

Then run Alembic migration:

> alembic upgrade head

**6.3 Step E2 --- Add SQLite WAL Mode (if staying on SQLite)**

If PostgreSQL cannot be activated immediately, enable WAL mode to allow concurrent readers without blocking the writer:

> \# In app/storage/db.py, after connect():
>
> conn.execute(\"PRAGMA journal_mode=WAL\")
>
> conn.execute(\"PRAGMA synchronous=NORMAL\")
>
> conn.execute(\"PRAGMA cache_size=-64000\") \# 64 MB cache
>
> conn.execute(\"PRAGMA temp_store=MEMORY\")

**6.4 Step E3 --- Fix PerformanceTracker O(N) Rebuild**

In app/ai/orchestrator.py PerformanceTracker.ingest_closed_trades(), cache the computed snapshot and only invalidate when the trade count changes:

> def ingest_closed_trades(self, trades):
>
> if len(trades) == self.\_last_count:
>
> return \# No new trades, skip rebuild
>
> self.\_last_count = len(trades)
>
> self.\_trades = \[float(t.get(\'realized_pnl_usd\', 0.0)) for t in trades\]
>
> self.\_snapshot_cache = None \# Invalidate
>
> def snapshot(self):
>
> if self.\_snapshot_cache: return self.\_snapshot_cache
>
> self.\_snapshot_cache = self.\_compute_snapshot()
>
> return self.\_snapshot_cache

**6.5 Step E4 --- Worker Queue Health Monitoring**

The /workers/health endpoint currently returns queue status as always \'active\'. Add real dead-letter queue (DLQ) monitoring. In workers/reporting.py, route failed Telegram notifications to a DLQ rather than swallowing:

> @dramatiq\.actor\(max_retries=3, queue_name=\'reporting\',
>
> on_failure=lambda msg, ex, \*\*kw: dlq.push(msg))
>
> def send_telegram_alert(message, priority=\'normal\'): \...
>
> \# In /workers/health endpoint, report DLQ depth:
>
> queues\[\"dlq\"\] = {\"pending\": redis.llen(\"dramatiq:\_\_dead_letters\_\_\")}

**6.6 Step E5 --- Reach GO Status (Trading Gate)**

Current state: Net PnL = -\$0.73, Profit Factor = 0.00. The paper GO/NO-GO gate requires all three criteria simultaneously. Actions needed to pass:

| **GO Criterion**    | **Current**    | **Action Required**                                                                         |
|---------------------|----------------|---------------------------------------------------------------------------------------------|
| Profit Factor ≥ 1.2 | 0.00 (FAIL)    | Raise BOT_BREAKOUT_RR_RATIO to 2.5+ (already done), enable London session filter            |
| Net PnL \> 0        | -\$0.73 (FAIL) | Reduce PAPER_RISK_PER_TRADE to 0.0075 (done), disable breakout strategy until edge recovers |
| Closed trades ≥ 30  | 171 (PASS)     | Already met --- maintain cycle frequency                                                    |

**7. Implementation Roadmap**

Execute in priority order. Each phase is independently deployable.

| **Phase**   | **Zone / Steps**                     | **Files to Change**                         | **Est. Time** |
|-------------|--------------------------------------|---------------------------------------------|---------------|
| P1 (Day 1)  | A1, A2 --- Auth hardening            | app/api/trading.py, app/infra/rate_limit.py | 2 hours       |
| P1 (Day 1)  | E2 --- SQLite WAL mode               | app/storage/db.py                           | 30 min        |
| P2 (Day 2)  | C4 --- Circuit breaker               | orchestrator/coordinator.py                 | 3 hours       |
| P2 (Day 2)  | C5 --- Remove MockExchange in prod   | app/ai/integration_wrapper.py               | 1 hour        |
| P2 (Day 2)  | B4 --- Persist SpendTracker to Redis | app/llm/spend_tracker.py                    | 2 hours       |
| P3 (Day 3)  | B1 --- HTTP connection pooling       | app/llm/provider.py                         | 2 hours       |
| P3 (Day 3)  | C2 --- Parallel agent stages         | app/ai/orchestrator.py                      | 3 hours       |
| P3 (Day 3)  | C3 --- Cache learning params         | app/learning/self_learning.py               | 1 hour        |
| P4 (Week 2) | D1 --- WS heartbeat                  | app/exchange/enhanced_websocket.py          | 4 hours       |
| P4 (Week 2) | D4 --- Replace pickle with orjson    | app/cache/three_tier_cache.py               | 2 hours       |
| P4 (Week 2) | E3 --- Fix PerformanceTracker O(N)   | app/ai/orchestrator.py                      | 2 hours       |
| P5 (Week 3) | E1 --- Activate PostgreSQL           | app/storage/db.py, .env                     | 1 day         |
| P5 (Week 3) | B3 --- LLM response cache            | app/api/llm_optimized.py                    | 3 hours       |
| P5 (Week 3) | A3 --- JWT deny-list                 | app/security/auth.py                        | 2 hours       |

**8. KPIs & Success Metrics**

| **KPI**                | **Current Baseline**     | **Target (Post-Opt)**        | **Measurement**            |
|------------------------|--------------------------|------------------------------|----------------------------|
| Bot cycle latency      | \~2--5 s (lazy init)     | \< 800 ms (eager + parallel) | orchestrator cycle_time_ms |
| LLM cost/day           | Unbounded (no persist)   | \< \$2/day tracked + capped  | spend_tracker.today_usd    |
| Exchange API calls/min | \~60+ (no burst control) | \< 20 (coalescer + cache)    | aggregator.\_metrics       |
| Auth bypass risk       | High (string compare)    | Zero (HMAC + deny-list)      | Security audit pass        |
| Paper Profit Factor    | 0.00                     | ≥ 1.2 (GO gate)              | /profit/snapshot PF        |
| Worker DLQ depth       | Unknown (not monitored)  | \< 5 (alert threshold)       | /workers/health dlq        |
| DB write contention    | Frequent BUSY (SQLite)   | 0 contention (PG WAL)        | DB error rate log          |

**8.1 Monitoring Endpoints to Add**

- GET /health/full --- aggregates all subsystem health (Redis ping, WS heartbeat age, DLQ depth, spend tracker state, GO/NO-GO)

- GET /metrics/llm --- returns cost by model tier for today, truncation count, cache hit ratio

- GET /metrics/pipeline --- returns last 10 cycle latencies, consecutive_failures count, circuit-breaker state

- POST /admin/reset-spend-day --- resets daily spend counter in Redis (protected by admin role)

**9. Quick-Start Commands**

Run these in order after applying code changes:

**Validate Database Migration**

> alembic upgrade head
>
> alembic current \# Should show latest revision hash

**Test Health Endpoints**

> curl http://localhost:8000/health
>
> curl http://localhost:8000/services/health
>
> curl http://localhost:8000/workers/health
>
> curl http://localhost:8000/llm-optimization/status

**Check GO/NO-GO Gate**

> curl \'http://localhost:8000/profit/snapshot?user_id=gold_bot\' \| jq .paper_validation

**Run Daily Optimization Script**

> python3 scripts/optimize_strategy_performance.py
>
> \# Output: profit_factor, win_rate, GO/NO-GO decision

**Validate LLM Model Routing**

> curl -X POST http://localhost:8000/llm-optimization/query-model \\
>
> -H \"Content-Type: application/json\" \\
>
> -d \'{\"task_type\":\"market_scan\",\"allow_premium\":false}\'

**Monitor Worker Queues**

> curl http://localhost:8000/workers/queues \| jq .queues

**Check Spend Tracker**

> curl http://localhost:8000/llm-optimization/usage \| jq .current_usage

**10. Future Trend & Evolution**

| **Trend**                | **Application to ALiVMassit**                                                                                  |
|--------------------------|----------------------------------------------------------------------------------------------------------------|
| AI inference at the edge | Run Gemini Flash locally (Ollama) for market_scan tasks --- zero API cost, \<50 ms latency                     |
| Streaming LLM responses  | Replace POST /llm/optimized-chat with SSE stream for real-time dashboard signals                               |
| Vector similarity search | Replace keyword strategy selection with embedding similarity (pgvector) for regime-aware matching              |
| Adaptive position sizing | Replace fixed PAPER_RISK_PER_TRADE with Kelly Criterion calculation fed from PerformanceTracker.expectancy_usd |
| FIX protocol integration | Replace REST exchange calls with FIX 4.4 over TCP for institutional-grade sub-millisecond execution            |

*ALiVMassit API Flow Optimization Plan --- Generated May 2026 --- Confidential*
