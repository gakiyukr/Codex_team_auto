# Codex 推薦邀請自動化工具

一套用於研究 SSO 工作區推薦邀請流程的自動化工具，支援 OIDC SSO 系統整合，可一條命令完成全流程。

## 功能特色

- **全自動流程**：一條命令完成 母號建立 → 母號登入 → 發送邀請 → 子號登入 → 子號激活
- **OIDC SSO 整合**：支援自訂 OIDC SSO 系統，自動註冊與登入
- **並發處理**：母號登入、邀請發送、子號登入均支援多執行緒並發
- **多種輸入格式**：支援 CSV、JSON（物件陣列）、純文字（每行一個郵箱）
- **自動備份**：邀請結果自動備份，避免覆蓋歷史記錄
- **代理支援**：所有 HTTP 請求均支援代理（預設 `http://127.0.0.1:7890`）

## 環境需求

- Python 3.8+
- 已部署的 OIDC SSO 系統（用於帳號註冊與登入）
- HTTP 代理（建議）

## 安裝

```bash
# 建立虛擬環境
python -m venv .venv

# 啟動虛擬環境
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```

## 快速開始

### 一條命令完成全流程

```bash
python codex_referral_flow.py \
  --auto-seeds 10 \
  --seeds-invite-code JOIN-2026 \
  --domain your-domain.com \
  --per-account 5 \
  --concurrency 10 \
  --oidc-sso-url https://your-sso.example.com \
  --oidc-sso-admin-token YOUR_ADMIN_TOKEN \
  --oidc-sso-invite-code JOIN-2026
```

這會自動：
1. 在 SSO 系統建立 10 個母號
2. 登入這 10 個母號到 OpenAI
3. 每個母號發送 5 個邀請（共 50 個子號）
4. 登入 50 個子號（自動在 SSO 註冊）
5. 激活所有子號

### Windows PowerShell 用法

PowerShell 使用反引號 `` ` `` 續行：

```powershell
python codex_referral_flow.py `
  --auto-seeds 10 `
  --seeds-invite-code JOIN-2026 `
  --domain your-domain.com `
  --per-account 5 `
  --concurrency 10 `
  --oidc-sso-url https://your-sso.example.com `
  --oidc-sso-admin-token YOUR_ADMIN_TOKEN `
  --oidc-sso-invite-code JOIN-2026
```

或寫成一行：

```powershell
python codex_referral_flow.py --auto-seeds 10 --seeds-invite-code JOIN-2026 --domain your-domain.com --per-account 5 --concurrency 10 --oidc-sso-url https://your-sso.example.com --oidc-sso-admin-token YOUR_ADMIN_TOKEN --oidc-sso-invite-code JOIN-2026
```

## 流程步驟說明

| 步驟 | 說明 | 對應腳本 |
|------|------|----------|
| 0 | 自動建立母號（在 SSO 系統註冊） | `codex_referral_flow.py` 內建 |
| 1 | 母號登入 OpenAI（透過 SSO OAuth） | `codex_protocol_login.py` |
| 2 | 母號發送邀請（生成隨機子號郵箱） | `codex_invitation_batch.py` |
| 3 | 子號登入（在 SSO 註冊 + OpenAI 建號） | `codex_protocol_login.py` |
| 4 | 子號激活（模擬 Codex 桌面端遙測） | `codex_activation_batch.py` |

## 參數說明

### `codex_referral_flow.py`（全自動流程）

| 參數 | 必填 | 說明 |
|------|------|------|
| `--auto-seeds N` | 三選一 | 自動建立 N 個母號 |
| `--seeds FILE` | 三選一 | 指定母號 JSON 文件 |
| `--use-existing-seeds` | 三選一 | 使用已存在的母號（讀取 `out-dir/auto_seeds.json`） |
| `--seeds-invite-code` | 條件 | 自動建立母號時使用的 SSO 邀請碼（`--auto-seeds` 時必填） |
| `--seeds-prefix` | 否 | 母號帳號前綴，預設 `seed` |
| `--domain` | 否 | 邀請郵箱域名，預設 `dfhdg.store` |
| `--per-account` | 否 | 每個母號邀請的子號數量，預設 `5` |
| `--concurrency` | 否 | 並發數（同時執行的母號數量），預設 `10` |
| `--out-dir` | 否 | 輸出目錄，預設 `./runs/auto` |
| `--proxy` | 否 | HTTP 代理，預設 `http://127.0.0.1:7890` |
| `--oidc-sso-url` | 是 | OIDC SSO 伺服器 URL |
| `--oidc-sso-admin-token` | 是 | SSO 系統的 ADMIN_TOKEN |
| `--oidc-sso-invite-code` | 是 | 子號註冊時使用的 SSO 邀請碼 |
| `--skip-seeds-login` | 否 | 跳過母號登入（假設已登入） |
| `--skip-invitations` | 否 | 跳過發送邀請（假設已發送） |
| `--skip-activation` | 否 | 跳過子號激活 |
| `--dry-run` | 否 | 只預檢，不實際發送邀請 |

### `codex_protocol_login.py`（登入腳本）

| 參數 | 說明 |
|------|------|
| `--email` / `--password` | 單帳號登入 |
| `--csv FILE` | CSV 批量登入（格式：`email,password`） |
| `--json FILE` | JSON 批量登入（支援物件陣列、字串陣列、純文字） |
| `--out` / `--out-dir` | 輸出路徑 |
| `--concurrency N` | 並發數，預設 `1` |
| `--retries N` | 失敗重試次數，預設 `2` |
| `--skip-existing` | 跳過已存在的帳號 |
| `--proxy URL` | 代理 URL |
| `--oidc-sso-url` | SSO 伺服器 URL |
| `--oidc-sso-admin-token` | SSO ADMIN_TOKEN |
| `--oidc-sso-invite-code` | SSO 邀請碼（有則走 `/api/register`，無則走 `/api/login`） |

### `codex_invitation_batch.py`（邀請腳本）

| 參數 | 說明 |
|------|------|
| `--auth-dir` | 母號憑證目錄 |
| `--domain` | 隨機郵箱域名，預設 `dfhdg.store` |
| `--per-account` | 每個母號邀請數量，預設 `5` |
| `--concurrency` | 並發母號數，預設 `5` |
| `--proxy` | 代理 URL |
| `--out` | 結果輸出 JSON 路徑 |
| `--dry-run` | 只預檢不發送 |
| `--save-back` | 刷新 token 後寫回原文件 |

### `codex_activation_batch.py`（激活腳本）

| 參數 | 說明 |
|------|------|
| `--auth-dir` | 子號憑證目錄 |
| `--concurrency` | 並發數，預設 `5` |
| `--proxy` | 代理 URL |
| `--save-back` | 刷新 token 後寫回原文件 |

## 使用情境

### 情境一：首次執行全流程

```bash
python codex_referral_flow.py \
  --auto-seeds 10 \
  --seeds-invite-code JOIN-2026 \
  --domain your-domain.com \
  --per-account 5 \
  --concurrency 10 \
  --oidc-sso-url https://your-sso.example.com \
  --oidc-sso-admin-token YOUR_ADMIN_TOKEN \
  --oidc-sso-invite-code JOIN-2026
```

### 情境二：邀請已發送，只需登入和激活子號

```bash
python codex_referral_flow.py \
  --use-existing-seeds \
  --domain your-domain.com \
  --per-account 5 \
  --concurrency 10 \
  --oidc-sso-url https://your-sso.example.com \
  --oidc-sso-admin-token YOUR_ADMIN_TOKEN \
  --oidc-sso-invite-code JOIN-2026 \
  --skip-seeds-login \
  --skip-invitations
```

### 情境三：使用已有的母號文件

```bash
python codex_referral_flow.py \
  --seeds my_seeds.json \
  --domain your-domain.com \
  --per-account 5 \
  --concurrency 10 \
  --oidc-sso-url https://your-sso.example.com \
  --oidc-sso-admin-token YOUR_ADMIN_TOKEN \
  --oidc-sso-invite-code JOIN-2026
```

### 情境四：只登入帳號（不發邀請）

```bash
# 母號登入（走 /api/login）
python codex_protocol_login.py \
  --json seeds.json \
  --out-dir ./seeds \
  --concurrency 10 \
  --oidc-sso-url https://your-sso.example.com \
  --oidc-sso-admin-token YOUR_ADMIN_TOKEN

# 子號登入（走 /api/register，帶邀請碼）
python codex_protocol_login.py \
  --json invitees.json \
  --out-dir ./invitees \
  --concurrency 10 \
  --oidc-sso-url https://your-sso.example.com \
  --oidc-sso-admin-token YOUR_ADMIN_TOKEN \
  --oidc-sso-invite-code JOIN-2026
```

## 輸入文件格式

### JSON 格式（推薦）

**字串陣列**（只有郵箱，密碼為空）：
```json
["alice@example.com", "bob@example.com", "charlie@example.com"]
```

**物件陣列**（帶密碼）：
```json
[
  {"email": "alice@example.com", "password": "optional"},
  {"email": "bob@example.com", "password": "optional"}
]
```

**純文字**（每行一個郵箱，`.txt` 或 `.json` 均可）：
```
alice@example.com
bob@example.com
charlie@example.com
```

### CSV 格式

```csv
alice@example.com,password
bob@example.com,password
```

## SSO 系統整合

本工具透過 OIDC 協議與自訂 SSO 系統整合：

- **母號登入**：呼叫 SSO 的 `/api/login`，帳號必須已存在於 SSO 系統
- **子號登入**：呼叫 SSO 的 `/api/register`（帶邀請碼），自動在 SSO 建立帳號
- **判斷邏輯**：有 `--oidc-sso-invite-code` 參數時走 `/api/register`，無則走 `/api/login`

### SSO 系統要求

你的 SSO 系統需要提供以下 API：

- `POST /api/login` — 登入已有帳號
- `POST /api/register` — 註冊新帳號（需要邀請碼）

所有 API 需要 `Authorization: Bearer <ADMIN_TOKEN>` 認證。

## 輸出目錄結構

```
runs/auto/
├── auto_seeds.json              # 自動建立的母號帳號列表
├── seeds/                       # 母號憑證（auth.json）
│   ├── seed_abc12345.json
│   └── seed_def67890.json
├── invite_results.json          # 最新邀請結果
├── invite_results_20260115_*.json  # 歷史邀請結果備份
├── invitees.txt                 # 被邀請的郵箱列表
└── invitees/                    # 子號憑證（auth.json）
    ├── sfvm3ta6b0lf99zhoapf.json
    └── 3y1or48la0x07sykisa3.json
```

## 常見問題

### Q: `--per-account` 和 `--concurrency` 分別代表什麼？

- `--per-account`：每個母號邀請多少個子號
- `--concurrency`：同時有多少個母號並發執行

例如 10 個母號、`--per-account 5`、`--concurrency 10`，會同時用 10 個母號各邀請 5 個子號，總共 50 個子號。

### Q: 母號和子號的邀請碼可以不同嗎？

可以。`--seeds-invite-code` 用於建立母號，`--oidc-sso-invite-code` 用於註冊子號，兩者可以不同。

### Q: 邀請結果會被覆蓋嗎？

不會。每次發送邀請前，如果 `invite_results.json` 已存在，會自動備份為 `invite_results_YYYYMMDD_HHMMSS.json`。

### Q: 代理一定要設定嗎？

預設使用 `http://127.0.0.1:7890`。如果你的代理位址不同，用 `--proxy` 指定。如果不需要代理，用 `--proxy ""` 停用。

### Q: SSO 系統需要怎麼配置？

你的 SSO 系統需要是 OIDC 提供者，並在 OpenAI 後台配置為 Custom OIDC。SSO 的 `ACCOUNT_DOMAIN` 必須與 `--domain` 參數一致。

## 各腳本說明

| 腳本 | 用途 |
|------|------|
| `codex_referral_flow.py` | 全自動流程（一條命令搞定） |
| `codex_protocol_login.py` | 純 HTTP 協議登入（支援 SSO） |
| `codex_invitation_batch.py` | 批量並發發送邀請 |
| `codex_invitation_helper.py` | 單帳號邀請助手 |
| `codex_activation_batch.py` | 批量並發激活子號 |
| `codex_activation_helper.py` | 單帳號激活模擬器 |
| `codex_sso_login.py` | 瀏覽器自動化登入（備用） |
| `sentinel.py` | Sentinel token 生成 |

## 資料安全

運行時資料已從 git 排除，請勿提交以下內容：

- 帳號憑證文件（`auth.json`）
- access_token / refresh_token / id_token
- 帳號 ID
- 郵箱密碼 CSV 文件
- 邀請結果
- 本地日誌

`.gitignore` 已封鎖：`accounts/`、`runs/`、`*.csv`、`*auth*.json`、`.venv/`、`*.log`
