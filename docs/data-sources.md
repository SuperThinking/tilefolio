# Data sources and broker APIs (research as of 2026-11-08)

Labels: **[verified]** means checked on the official page or with a live request on 2026-11-08. **[secondary]** means it comes
from a forum, blog or aggregator. **[unverified]** means it couldn't be confirmed. Prices and policies change often, so
re-check them before relying on them. Nothing here is legal advice: confirm regulatory points with Legal/Compliance.

## Headline: multi-user "click to connect" is not generally available
Under the SEBI/NSE retail-algo framework (full compliance around 1 Apr 2026 [secondary]), brokers bind API keys to
a single client and gate multi-user apps behind approval:
- **Upstox** has paused new multi-user "Business APIs" (staff post, 17 Mar 2026), even for read-only use.
  https://community.upstox.com/t/request-for-multi-user-api-access-read-only-pinbar-ai-integration/14415
- **Zerodha** Kite apps are restricted to a single user ID by default. Multi-user access needs a compliance review.
  https://kite.trade/forum/discussion/8340
- **Dhan** has a documented *partner* consent flow for multi-user apps (needs approval). https://dhanhq.co/docs/v2/authentication/

**Decision:** guided file import (CSV/XLSX + CAS PDF) is the universal path. BYO-key sync (each user brings
their own free Kite Personal or Upstox app) is the advanced path. Partner OAuth is a future option.

## Broker APIs
| Broker | Cost | Holdings | Auth / expiry | Notes |
|---|---|---|---|---|
| Zerodha Kite | Personal: free (no quotes/WS) [secondary]. Connect: ₹500/mo | `/portfolio/holdings`, `/mf/holdings` [verified] | redirect → request_token → SHA-256 checksum. Expires 6 AM | Implemented (BYO) |
| Upstox v2 | free [verified uplink page] | `/portfolio/long-term-holdings` | OAuth2 code. Expires ~3:30 AM, no refresh | Implemented (BYO) |
| Groww | Trade API ~₹499/mo [secondary] | `get_holdings_for_user` [verified] | key+secret (daily approval) or TOTP | Not planned (paid) |
| INDstocks (INDmoney) | [unverified] | `/portfolio/holdings` [verified] | in-app token | Candidate |
| Angel One SmartAPI | free [unverified] | `getHolding` | client code + PIN + TOTP | Candidate |
| Dhan | trading APIs free, data paid | yes | 24h token, or partner consent flow | Best multi-user candidate |
| Fyers v3 | free | yes | auth-code. Expires 6:30 AM | Candidate |
| ICICI Breeze | free incl. data | `get_demat_holdings` | session key, 24h | Candidate |
| 5paisa | free | `holdings()` | OAuth request token | Candidate |

## Mutual funds
- **casparser** (MIT, v1.4.1, 2026-08-30): parses CAMS/KFin detailed and summary CAS, and NSDL/CDSL CAS. It does not parse MF Central statements. https://github.com/codereverser/casparser
- **Account Aggregator**: the FIU must be RBI/SEBI/IRDAI/PFRDA-regulated, so it isn't feasible without a regulated partner.

## Prices
| Data | Primary | Fallback | Limits / caveats |
|---|---|---|---|
| NSE/BSE equities | Yahoo v8 chart `SYMBOL.NS` (direct HTTP, no yfinance/pandas) | — (future: broker quote API with user token) | Unofficial, personal-use ToS, may break. NSE's own API 403s (Akamai) from servers |
| US equities | Finnhub `/quote` (if `TF_FINNHUB_API_KEY`) | Yahoo | Finnhub free: 60 calls/min, personal use |
| MF NAV | AMFI `NAVAll.txt`, snapshotted every 6h into `nav_history` | mfapi.in `/mf/{code}` (history → prev NAV) | NAVAll has no previous NAV. Day change lags equities |
| USD/INR | Yahoo `INR=X` | Frankfurter (ECB daily) | — |
| Master data | NSE `EQUITY_L.csv` + `ind_nifty500list.csv` (industry) + AMFI schemes | cached files in data dir | Sector only covers the Nifty 500 |

Other US options considered: Twelve Data (800/day), Alpha Vantage (25/day, real-time is premium), Massive/Polygon (EOD
only on free), Tiingo (internal use only), FMP (250/day EOD).

## Licensing risk (before a commercial or public launch)
The Yahoo, Finnhub free and Tiingo free tiers are personal/non-commercial. Showing their data to many users likely
needs a commercial licence. Providers are isolated behind `app/prices/*` so they can be swapped.
Avoid GPL `nsepython` and the unlicensed `jugaad-data` if the code will be distributed.
